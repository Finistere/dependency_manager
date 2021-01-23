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
tree with :py:func:`.world.debug`. It will provide a summarized view like the following::

    f
    └── Static link: MovieDB -> IMDBMovieDB
        └── * IMDBMovieDB
            ├── ImdbAPI @ imdb_factory
            │   └── imdb_factory
            │       └── Lazy: Conf()  #yIlnAQ
            │           └── Singleton 'conf_path' -> '/etc/app.conf'
            └── Lazy: Conf()  #yImm
                └── Singleton 'conf_path' -> '/etc/app.conf'

    * = not singleton

:py:func:`~.world.debug` will not instantiate anything or run any user code. Hence it
won't work really well with :py:func:`.implementation` for example if it hasn't been called
once yet or if the implementation is not permanent. On top of providing the whole tree,
it also shows:

- Whenever a :code:`*` is present at th beginning, the dependency is not a singleton. In the previous
  example, :code:`IMDBMoveDB` is not a singleton. So a new instance is returned each time.
- Ambiguous dependencies, such as lazy ones, the id of the object will be specified like
  :code:`#yIlnAQ`. In the example, one can see that the two :code:`Lazy: Conf()` do not have
  the same id. This means that :code:`imdb_factory` and :code:`IMDBMovieDB` are not actually
  using the same object.