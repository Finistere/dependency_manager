*******
Recipes
*******


This is a collection of how to use certain features of Antidote or simply examples of
what can be done.



Use interfaces
==============


Antidote supports the distinction interface/implementation out of the box with the
function decorator :py:func:`~.implementation`. The result of the function will be the
retrieved dependency for the specified interface. Typically this means a class registered
as a service or one that can be provided by a factory.

.. testcode:: recipes_interface_implementation

    from antidote import implementation, Service, inject, Get
    from typing import Annotated
    # from typing_extensions import Annotated # Python < 3.9

    class Database:
        def __init__(self, host: str, name: str):
            self.host = host
            self.name = name

        @classmethod
        def with_conf(cls, host: str, name: str):
            return cls._with_kwargs(host=host, name=name)

    class PostgresDB(Service, Database):
        pass

    class MySQLDB(Service, Database):
        pass

    # permanent is True by default. If you want to choose each time which implementation
    # should be used, set it to False.
    @implementation(Database, permanent=True)
    def local_db(conn_str: Annotated[str, Get('db_conn_str')]):
        db, host, name = conn_str.split(':')
        if db == 'postgres':
            # Complex dependencies are supported
            return PostgresDB.with_conf(host, name)
        elif db == 'mysql':
            # But you can also simply return the class
            return MySQLDB
        else:
            raise RuntimeError(f"{db} is not a supported database")


.. doctest:: recipes_interface_implementation

    >>> from antidote import world
    >>> world.singletons.add('db_conn_str', 'postgres:localhost:my_project')
    >>> db = world.get[Database](Database @ local_db)
    >>> db
    <PostgresDB ...>
    >>> db.host
    'localhost'
    >>> db.name
    'my_project'



Lazily call a function
======================


Calling lazily a function can be done with :py:class:`.LazyCall` or
:py:class:`.LazyMethodCall` for methods. Both will pass any arguments passed on
and can either be singletons or not.


Function call
-------------

.. testsetup:: recipes_lazy

    import sys

    class DummyRequests:
        def get(url):
            return url

    sys.modules['requests'] = DummyRequests()

.. testcode:: recipes_lazy

    import requests
    from antidote import LazyCall, inject

    def fetch_remote_conf(name):
        return requests.get(f"https://example.com/conf/{name}")

    CONF_A = LazyCall(fetch_remote_conf)("conf_a")

    @inject(dependencies=(CONF_A,))
    def f(conf):
        return conf

Using :code:`CONF_A` as a representation of the result allows one to easily identify
where this dependency is needed. Moreover neither :code:`f` nor its caller needs to
be aware on how to call :code:`fetch_remote_conf`.


Method call
-----------

.. testcode:: recipes_lazy

    from antidote import LazyMethodCall, Service

    class ExampleCom(Service):
        def get(url):
            return requests.get(f"https://example.com{url}")

        STATUS = LazyMethodCall(get, singleton=False)("/status")

Lazily calling a method through :py:class:`.LazyMethodCall` requires the class
to be defined as a service. The class itself will only be instantiated when
necessary.

.. note::

    If you intend to define multiple constants lazily, consider using
    :py:class:`.Constants` instead.



Abstract Service / Factory
==========================

It is possible to define an abstract service or factory by simply adding
:code:`abstract=True` as a metaclass argument:

.. testcode:: recipes_abstract

    from antidote import Service, Factory, Tag

    tag = Tag()

    class AbstractService(Service, abstract=True):
        # Change default configuration
        __antidote__ = Service.Conf(tags=[tag])

    class AbstractFactory(Factory, abstract=True):
        pass

Abstract classes will not be registered, neither wired:

.. doctest:: recipes_abstract

    >>> from antidote import world
    >>> world.get[AbstractService]()
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
    DependencyNotFoundError
    >>> world.get[AbstractFactory]()
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
    DependencyNotFoundError

In the actual implementation you only need to use :code:`copy()` on the configuration
to use the newly defined defaults:

.. testcode:: recipes_abstract

    class MyService(AbstractService):
        # Change default configuration
        __antidote__ = AbstractService.__antidote__.copy(singleton=False)




Use tags to retrieve multiple dependencies
==========================================


Tags are a way to retrieve a list of services, such as plugins, extensions, etc... In
Antidote tags are instance of :py:class:`.Tag`. Dependencies tagged with this instance
can simply be retrieved by requesting this specific tag from Antidote. You'll get a
:py:class:`.Tagged` instances containing both your dependencies and their associated
instance of :py:class:`.Tag`.

.. testcode:: recipes_tags

    from antidote import Service, Tag

    tag = Tag()

    # Specifying abstract tells Antidote to NOT register Plugin. It's considered
    # to be an abstract class.
    class Plugin(Service, abstract=True):
        pass

    class PluginA(Plugin):
        __antidote__ = Service.Conf(tags=[tag])

    class PluginB(Plugin):
        __antidote__ = Service.Conf(tags=[tag])

.. doctest:: recipes_tags

    >>> from antidote import world, Tagged
    >>> tagged = world.get[Tagged](Tagged.with_(tag))
    >>> list(sorted(tagged.values(), key=lambda plugin: type(plugin).__name__))
    [<PluginA ...>, <PluginB ...>]

Antidote will always return a :py:class:`.Tagged`, whether there are tagged instances or
not.

.. note::

    :py:class:`.Tagged` has two generic parameters :code:`T` and :code:`D` which
    respectfully represent the tag type and the dependency type.



Create a stateful factory
=========================


Antidote supports stateful factories simply by using defining a class as a factory:

.. testcode:: recipes_stateful_factory

    from antidote import Factory

    class ID:
        def __init__(self, id: str):
            self.id = id

        def __repr__(self):
            return "ID(id='{}')".format(self.id)

    class IDFactory(Factory):
        __antidote__ = Factory.Conf(singleton=False).with_wiring(use_names=True)

        def __init__(self, id_prefix: str):
            self._prefix = id_prefix
            self._next = 1

        def __call__(self) -> ID:
            id = ID("{}_{}".format(self._prefix, self._next))
            self._next += 1
            return id

.. doctest:: recipes_stateful_factory

    >>> from antidote import world
    >>> world.singletons.add('id_prefix', "example")
    >>> world.get[ID](ID @ IDFactory)
    ID(id='example_1')
    >>> world.get[ID](ID @ IDFactory)
    ID(id='example_2')


In this example we choose to inject :code:`id_prefix` in the :code:`__init__()`, but we
also could have done it in the :code:`__call__()`. Both are injected by default, but they
have different use cases. The factory itself is always a singleton, so static dependencies
should be injected through :code:`__init__()`. If you need dependencies that changes, get
them through :code:`__call__()`. Obviously you can change that behavior through the
:py:class:`.Factory.Conf`: defined in :code:`__antidote__`.


.. note::

    Stateful factories can also be used to provide dependencies that have a more complex
    scope than Antidote provides (singleton or not). Although, if you need to handle some
    scope for multiples dependencies it might be worth just extending Antidote through a
    :py:class:`.Provider`.



Configuration
=============

Here are some examples on how to use :py:class:`.Constants` to handle configuration coming
from different sources.


From the environment
--------------------

.. testcode:: recipes_configuration_environment

    import os
    from antidote import Constants, const

    class Env(Constants):
        SECRET = const[str]('SECRET')

        def get(self, value):
            return os.environ[value]

.. doctest:: recipes_configuration_environment

    >>> from antidote import world
    >>> os.environ['SECRET'] = 'my_secret'
    >>> world.get[str](Env.SECRET)
    'my_secret'


From a dictionary
-----------------

Configuration can be stored in a lot of different formats, or even be retrieved on a
remote endpoint at start-up. Most of the time you would be able to easily convert it
to a dictionary and use the following:

.. testcode:: recipes_configuration_environment

    import os
    from antidote import Constants, const

    class Conf(Constants):
        HOST = const[str]('host')
        AWS_API_KEY = const[str]('aws.api_key')

        def __init__(self):
            # Load your configuration into a dictionary
            self._raw_conf = {
                "host": "localhost",
                "aws": {
                    "api_key": "my key"
                }
            }

        def get(self, key):
            from functools import reduce
            return reduce(dict.get, key.split('.'), self._raw_conf)  # type: ignore

.. doctest:: recipes_configuration_environment

    >>> from antidote import world
    >>> world.get[str](Conf.HOST)
    'localhost'
    >>> world.get(Conf.AWS_API_KEY)
    'my key'


Specifying a type / Using Enums
-------------------------------

You can specify a type when using :py:func:`.const`. It's main purpose is to provide
a type for Mypy when the constants are directly accessed from an instance. However
:py:class:`.Constants` will also automatically force the cast  if the type is one
of :code:`str`, :code:`float` or :code:`int`. You can control this behavior with
the :code:`auto_cast` argument of :py:attr:`~.Constants.Conf`. A typical use case
would be to support enums as presented here:


.. testcode:: recipes_configuration_specify_type

    from enum import Enum
    from antidote import Constants, const

    class Env(Enum):
        PROD = 'prod'
        PREPRDO = 'preprod'

    class Conf(Constants):
        __antidote__ = Constants.Conf(auto_cast=[int, Env])

        DB_PORT = const[int]('db.port')
        ENV = const[Env]('env')

        def get(self, key):
            return {'db.port': '6789', 'env': 'prod'}[key]


.. doctest:: recipes_configuration_specify_type

    >>> from antidote import world
    >>> Conf().DB_PORT # will be treated as an int by Mypy
    6789
    >>> # will be treated as a Env instance by Mypy even
    ... Conf().ENV
    <Env.PROD: 'prod'>
    >>> world.get[int](Conf.DB_PORT)
    6789
    >>> world.get[Env](Conf.ENV)
    <Env.PROD: 'prod'>

The goal of this is to simplify common operations when manipulating the environment
or configuration files. If you need complex behavior, consider using a service for this
or define your Configuration class as :code:`public=True` in :py:attr:`~.Constants.Conf`
and use it as a one.

.. warning::

    They are two "cast" to differentiate here. When using :code:`ENV = const[T]('env')`
    there is a first cast done by :py:func:`.const` that will make mypy consider
    :code:`Conf().ENV` to be a :code:`T` instance whether this is the case or not. It is
    up to you to guarantee it. This only gives the necessary type hints to Mypy for it to
    work as :code:`ENV` will be transformed to a descriptor. Hence Mypy can't infer the
    actual return type.
    The second cast is done by :py:class:`.Constants`, controlled by :code:`auto_cast`.
    This will do an actual cast, which provides a nice syntactic sugar to cast integers or
    floats typically as configuration may be stored as a string.


Default values
--------------

Default values can be specified in :py:func:`.const`:

.. testcode:: recipes_configuration_default

    import os
    from antidote import Constants, const

    class Env(Constants):
        HOST = const[str]('HOST', default='localhost')

        def get(self, value):
            return os.environ[value]

It will be use if :code:`get` raises a py:exec:`KeyError`. For more complex behavior,
using a :py:class:`collections.ChainMap` which loads your defaults and the user is a good
alternative:

.. testcode:: recipes_configuration_default

    from collections import ChainMap
    from antidote import Constants, const

    class Configuration(Constants):
        def __init__(self):
            user_conf = dict()  # load conf from a file, etc..
            default_conf = dict()
            # User conf will override default_conf
            self._raw_conf = ChainMap(user_conf, default_conf)

An alternative to this would be using a configuration format that supports overrides, such
as HOCON.



Scopes
======


A dependency may be associated with a scope. If so it'll cached for as along as the scope is
valid. The most common scope being the singleton scope where dependencies are cached forever.
When the scope is set to :py:obj:`None`, the dependency value will be retrieved each time.
Scopes can be create through :py:func:`.world.scopes.new`. The name is only used to
have a friendly identifier when debugging.

.. doctest:: recipes_scope

    >>> from antidote import world
    >>> REQUEST_SCOPE = world.scopes.new('request')

To use the newly created scope, use :code:`scope` parameters:

.. doctest:: recipes_scope

    >>> from antidote import Service
    >>> class Dummy(Service):
    ...     __antidote__ = Service.Conf(scope=REQUEST_SCOPE)

As :code:`Dummy` has been defined with a custom scope, the dependency value will
be kep as long as :code:`REQUEST_SCOPE` stays valid. That is to say, until you reset
it with :py:func:`.world.scopes.reset`:

.. doctest:: recipes_scope

    >>> dummy = world.get[Dummy]()
    >>> dummy is world.get(Dummy)
    True
    >>> world.scopes.reset(REQUEST_SCOPE)
    >>> dummy is world.get(Dummy)
    False

In a Flask app for example you would then just reset the scope after each request:


.. code-block:: python

    from flask import Flask

    app = Flask(__name__)

    @app.after_request
    def reset_request_scope():
        world.scopes.reset(REQUEST_SCOPE)

