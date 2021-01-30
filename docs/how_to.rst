******
How to
******



be compatible with Mypy
=======================


Antidote passes the strict Mypy check and exposes its type information (PEP 561).
Unfortunately static typing for decorators is limited to simple cases, hence Antidote :code:`@inject` will just
return the same signature from Mypys point of view. The best way, currently that I know of, is to
define arguments as optional as shown below:

.. testcode:: how_to_mypy

    from antidote import inject, Service, Provide

    class MyService(Service):
        pass

    @inject
    def f(my_service: Provide[MyService] = None) -> MyService:
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
    def g(my_service: Provide[MyService] = None) -> MyService:
        assert my_service is not None
        return my_service


    s2: MyService = g()




Note that any of this is only necessary if you're calling _explicitly_ the function, if only
instantiate :code:`MyService` through Antidote for example, you won't need this for its
:code:`__init__()` function typically. You could also use a :code:`Protocol` to define
a different signature, but it's more complex.



debug dependency issues
=======================


If you encounter dependency issues or cycles, you can take a look at the whole dependency
tree with :py:func:`.world.debug`:

.. testcode:: how_to_debug

    from antidote import world, Service, inject, Provide

    class MyService(Service):
        pass

    @inject
    def f(s: Provide[MyService]):
        pass

    print(world.debug(f))

It will output:

.. testoutput:: how_to_debug
    :options: +NORMALIZE_WHITESPACE

    f
    └── MyService

    Singletons have no scope markers.
    <∅> = no scope (new instance each time)
    <name> = custom scope


.. note::

    If you're not using scopes, you only need to remember that :code:`<∅>` is equivalent
    to :code:`singleton=False`.


Now wit the more complex example presented in the home page of Antidote we have:

.. code-block:: text

    f
    └── Permanent implementation: MovieDB @ current_movie_db
        └──<∅> IMDBMovieDB
            └── ImdbAPI @ imdb_factory
                └── imdb_factory
                    ├── Const: Conf.IMDB_API_KEY
                    │   └── Conf
                    │       └── Singleton: 'conf_path' -> '/etc/app.conf'
                    ├── Const: Conf.IMDB_PORT
                    │   └── Conf
                    │       └── Singleton: 'conf_path' -> '/etc/app.conf'
                    └── Const: Conf.IMDB_HOST
                        └── Conf
                            └── Singleton: 'conf_path' -> '/etc/app.conf'

    Singletons have no scope markers.
    <∅> = no scope (new instance each time)
    <name> = custom scope


If you ever encounter a cyclic dependency, it will be present with a:

.. code-block:: text

    /!\\ Cyclic dependency: X

Ambiguous dependencies, which cannot be identified uniquely through their name, such as tags,
will have their id added to help differentiate them:

.. testcode:: how_to_debug

    from antidote import Tag, Tagged

    dummy_tag = Tag('dummy')
    dummy_tag2 = Tag('dummy')

    print(world.debug(Tagged.with_(dummy_tag)))
    print(world.debug(Tagged.with_(dummy_tag2)))

will output the following

.. testoutput:: how_to_debug
    :options: +NORMALIZE_WHITESPACE

    No dependencies tagged with Tag('dummy')#...
    No dependencies tagged with Tag('dummy')#...

.. code-block:: text

    No dependencies tagged with Tag('dummy')#QIKUBw
    No dependencies tagged with Tag('dummy')#wCqrBw

