********
Antidote
********


.. image:: https://img.shields.io/pypi/v/antidote.svg
  :target: https://pypi.python.org/pypi/antidote

.. image:: https://img.shields.io/pypi/l/antidote.svg
  :target: https://pypi.python.org/pypi/antidote

.. image:: https://img.shields.io/pypi/pyversions/antidote.svg
  :target: https://pypi.python.org/pypi/antidote

.. image:: https://travis-ci.org/Finistere/antidote.svg?branch=master
  :target: https://travis-ci.org/Finistere/antidote

.. image:: https://codecov.io/gh/Finistere/antidote/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/Finistere/antidote

.. image:: https://readthedocs.org/projects/antidote/badge/?version=latest
  :target: http://antidote.readthedocs.io/en/stable/?badge=stable

Antidotes is a dependency injection micro-framework for Python 3.6+. It is designed on two core ideas:

- Keep dependency declaration close to the actual code as it's deeply related. Dependency injection
  is about removing the responsibility of building dependencies from their clients. Not separating
  how a dependency is built from its implementation.
- It should help creating maintainable code in a straightforward way and offer effortless integration.
  One must be able to integrate it partially.

It provides the following features:

- Ease of use
    - injection anywhere you need through a decorator `@inject`, be it static methods, functions, etc..
      By default it will only rely on type hints, but it supports a lot more !
    - no \*\*kwargs arguments hiding actual arguments and fully mypy typed, helping you and your IDE.
    - documented, see `<https://antidote.readthedocs.io/en/stable>`_. If you don't find what you need, open an issue ;)
    - thread-safe, cycle detection
- Flexibility
    - A rich ecosystem of dependencies out of the box: services, configuration, factories, interface/implementation, tags.
    - All of those are implemented on top of the core implementation. If Antidote doesn't provide what you need, there's
      a good chance you can implement it yourself quickly.
- Maintainability
    - The different kind of dependencies are designed to be easy to track back. Finding where a
      dependency is defined is easy.
    - Overriding dependencies (duplicates) and injecting twice will raise an exception.
    - Dependencies can be frozen, which blocks any new definitions.
- Testability
    - `@inject` lets you override any injections by passing explicitly the arguments.
    - Change dependencies locally within a context manager.
- Performance
    - Antidote has two implementations: the pure Python one which is the reference and the
      Cython one which is heavily tuned for fast injection. Injection is roughly 10x times faster
      than with the pure Python. It allows using injections without impact on most functions.
      See `injection benchmark <https://github.com/Finistere/antidote/blob/master/benchmark.ipynb>`_


Installation
============

To install Antidote, simply run this command:

.. code-block:: bash

    pip install antidote


Quick Start
===========

How does injection looks like ? Here is a simple example:

.. code-block:: python

    from antidote import inject, Service, Constants, const, world

    class Conf(Constants):
        DB_HOST = const[str]('host')
        DB_HOST_UNTYPED = const('host')

        def __init__(self):
            self._data = {'host': 'localhost:6789'}

        # Used to retrieve lazily the const, so injecting Conf.DB_HOST is equivalent
        # Conf().get('host')
        def get(self, key: str):
            return self._data[key]

    class Database(Service):  # Defined as a Service, so injectable.
        @inject(dependencies=dict(host=Conf.DB_HOST))
        def __init__(self, host: str):
            self._host = host  # <=> Conf().get('host')

    @inject # By default only type annotations are used.
    def f(db: Database = None):
        # Defaulting to None allows for MyPy compatibility but isn't required to work.
        assert db is not None
        pass

    f()  # Service will be automatically injected if not provided
    f(Database('localhost:6789'))  # but you can still use the function normally

    # You can also retrieve dependencies by hand
    world.get(Conf.DB_HOST)
    world.get[str](Conf.DB_HOST) # with type hint
    # if the dependency is the type itself, you may omit it:
    world.get[Database]()

    # If you need to handle multiple different host for some reason you can
    # specify them in the dependency itself. As Database returns, by default,
    # a singleton this will also be the case here. Using the same host, will
    # return the same instance.
    world.get[Database](Database.with_kwargs(host='XX'))


Want more ? Here is an over-engineered example to showcase a lot more features:

.. code-block:: python


    """
    Simple example where a MovieDB interface is defined which can be used
    to retrieve the best movies. In our case the implementation uses IMDB
    to dot it.
    """
    from antidote import Constants, factory, Implementation, inject, world, const

    class MovieDB:
        """ Interface """

        def get_best_movies(self):
            pass

    class ImdbAPI:
        """ Class from an external library. """

        def __init__(self, *args, **kwargs):
            pass

    world.singletons.add('conf_path', '/etc/app.conf')

    class Conf(Constants):
        IMDB_HOST = const[str]('imdb.host')
        # Constants will by default automatically enforce the cast to int,
        # float and str. Can be removed or extended to support Enums.
        IMDB_PORT = const[int]('imdb.port')
        IMDB_API_KEY = const[str]('imdb.api_key')

        @inject(use_names=True)  # injecting world.get('conf_path')
        def __init__(self, conf_path: str):
            """ Load configuration from `conf_path` """
            self._raw_conf = {
                'imdb': {
                    'host': 'dummy_host',
                    'api_key': 'dummy_api_key',
                    'port': '80'
                }
            }

        def get(self, key: str):
            from functools import reduce
            # self.get('a.b') <=> self._raw_conf['a']['b']
            return reduce(dict.get, key.split('.'), self._raw_conf)  # type: ignore

    # Provides ImdbAPI, as defined by the return type annotation.
    @factory(dependencies=(Conf.IMDB_HOST, Conf.IMDB_PORT, Conf.IMDB_API_KEY))
    def imdb_factory(host: str, port: int, api_key: str) -> ImdbAPI:
        # Here host = Conf().get('imdb.host')
        return ImdbAPI(host=host, port=port, api_key=api_key)

    # When requesting MovieDB, a IMDBMovieDB instance will be provided.
    class IMDBMovieDB(MovieDB, Implementation):
        # New instance each time
        __antidote__ = Implementation.Conf(singleton=False)

        @inject(dependencies={'imdb_api': ImdbAPI @ imdb_factory})
        def __init__(self, imdb_api: ImdbAPI):
            self._imdb_api = imdb_api

        def get_best_movies(self):
            pass

    @inject
    def f(movie_db: MovieDB = None):
        assert movie_db is not None  # for Mypy
        pass

    f()

That looks all good, but what about testability ?

.. code-block:: python

    # You can still explicitly pass the arguments to override
    # injection.
    conf = Conf('/path')
    f(IMDBMovieDB(imdb_factory(
        # The class attributes will retrieve the actual value when called on a instance.
        # Hence this is equivalent to conf.get('imdb.host'), making your tests easier.
        host=conf.IMDB_HOST,
        port=conf.IMDB_PORT,
        api_key=conf.IMDB_API_KEY,  # <=> conf.get('imdb.api_key')
    )))

    # When testing you can also override locally some dependencies:
    with world.test.clone(overridable=True, keep_singletons=True):
        world.test.override.singleton({
            Conf.IMDB_HOST: 'other host'
        })
        f()

If you ever need to debug your dependency injections, Antidote also provides a tool to
have a quick summary of what is actually going on. This would be especially helpful if
you encounter cyclic dependencies for example.

.. code-block:: python

    world.debug(f)
    # will output:
    """
    f
    └── Static link: MovieDB -> IMDBMovieDB
        └── IMDBMovieDB
            └── ImdbAPI @ imdb_factory
                └── imdb_factory
                    ├── Const: Conf.IMDB_API_KEY
                    │   └── Lazy: Conf()  #0BjHAQ
                    │       └── Singleton 'conf_path' -> '/...'
                    ├── Const: Conf.IMDB_HOST
                    │   └── Lazy: Conf()  #0BjHAQ
                    │       └── Singleton 'conf_path' -> '/...'
                    └── Const: Conf.IMDB_PORT
                        └── Lazy: Conf()  #0BjHAQ
                            └── Singleton 'conf_path' -> '/...'
    """

    # For example suppose we don't have the singleton `'conf_path'`
    with world.test.clone(keep_singletons=False):
        world.debug(f)
        # As you can see, 'conf_path` is not found. Hence when Conf will be instantiated
        # it will fail.
        """
        f
        └── Static link: MovieDB -> IMDBMovieDB
            └── IMDBMovieDB
                └── ImdbAPI @ imdb_factory
                    └── imdb_factory
                        ├── Const: Conf.IMDB_API_KEY
                        │   └── Lazy: Conf()  #0BjHAQ
                        │       └── /!\\ Unknown: 'conf_path'
                        ├── Const: Conf.IMDB_HOST
                        │   └── Lazy: Conf()  #0BjHAQ
                        │       └── /!\\ Unknown: 'conf_path'
                        └── Const: Conf.IMDB_PORT
                            └── Lazy: Conf()  #0BjHAQ
                                └── /!\\ Unknown: 'conf_path'
        """


Hooked ? Check out the documentation ! There are still features not presented here !


Cython
======

The cython implementation is roughly 10x faster than the Python one and strictly follows the
same API than the pure Python implementation. This implies that you cannot depend on it in your
own Cython code if any. It may be moved to another language.

If you encounter any inconsistencies, please open an issue !
You can avoid the Cython version from PyPI with the following:

.. code-block:: bash

    pip install --no-binary antidote

Note that PyPy is tested with the pure Python version, not the Cython one.

Mypy
====

Antidote passes the strict Mypy check and exposes its type information (PEP 561).
Unfortunately static typing for decorators is limited to simple cases, hence Antidote :code:`@inject` will just
return the same signature from Mypys point of view. The best way, currently that I know of, is to
define arguments as optional as shown below:

.. code-block:: python

    from antidote import inject, Service

    class MyService(Service):
        pass

    @inject
    def f(my_service: MyService = None) -> MyService:
        # We never expect it to be None, but it Mypy will now
        # understand that my_service may not be provided.
        assert my_service is not None
        return my_service


    s: MyService = f()

    # You can also overload the function, if you want a more accurate type definition:
    from typing import overload

    @overload
    def g(my_service: MyService) -> MyService: ...

    @overload
    def g() -> MyService: ...

    @inject
    def g(my_service: MyService = None) -> MyService:
        assert my_service is not None
        return my_service


    s2: MyService = g()




Note that any of this is only necessary if you're calling _explicitly_ the function, if only
instantiate :code:`MyService` through Antidote for example, you won't need this for its
:code:`__init__()` function typically. You could also use a :code:`Protocol` to define
a different signature, but it's more complex.


Issues / Feature Requests / Questions
=====================================

Feel free to open an issue on Github for questions, requests or issues ! ;)


How to Contribute
=================

1. Check for open issues or open a fresh issue to start a discussion around a
   feature or a bug.
2. Fork the repo on GitHub. Run the tests to confirm they all pass on your
   machine. If you cannot find why it fails, open an issue.
3. Start making your changes to the master branch.
4. Writes tests which shows that your code is working as intended. (This also
   means 100% coverage.)
5. Send a pull request.

*Be sure to merge the latest from "upstream" before making a pull request!*

If you have any issue during development or just want some feedback, don't hesitate
to open a pull request and ask for help !

Pull requests **will not** be accepted if:

- classes and non trivial functions have not docstrings documenting their behavior.
- tests do not cover all of code changes (100% coverage).
