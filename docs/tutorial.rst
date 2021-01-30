***************
Getting started
***************

This is a beginner friendly tutorial on how to use Antidote.
It is a series of steps to show what can be done easily. Note that Antidote can do a lot
more than presented here, don't hesitate to check out the recipes and references for
more in depth documentation.



1. World
========


Let's start with a quick example:

.. testcode:: tutorial_overview

    from antidote import inject, world, Provide

    class MyService:
        pass

    world.singletons.add(MyService, MyService())

    @inject
    def f(service: Provide[MyService]):
        # doing stuff
        return service

.. doctest:: tutorial_overview

    >>> f()
    <MyService object at ...>

Now you don't need to provide :code:`MyService` anymore ! Let's start with the basics to
understand what's going on. To simplify a bit, Antidote works this way ::

                 +-----------+
          +----->|   world   +------+
          |      +-----------+      |

     declaration                 @inject

          |                         |
          |                         v
    +-----+------+             +----------+
    | Dependency |             | Function |
    +------------+             +----------+

Dependencies are declared and become part of :py:mod:`.world`. It works somewhat like a
big dictionary of dependencies mapping to their value. From there on you can either
retrieve them yourself or let Antidote inject them for you with :py:func:`.inject`.
By default it'll only rely on annotated type hints (see :py:obj:`typing.Annotated`
and PEP-593). Here we specify with :py:obj:`.Provide` that the type hint itself is the
dependency. Only missing arguments will be injected, hence you can always use the function
normally:

.. doctest:: tutorial_overview

    >>> f(MyService())
    <MyService object at ...>

.. note::

    :py:func:`.inject` is designed to be very flexible. It supports multiple ways to link
    an argument to its dependency if any. You'll encounter some of them later in this
    tutorial, but don't hesitate to check out its documentation by clicking on
    :py:func:`.inject` !

    In this tutorial we will rely on annotated type hints, but you can do without them:

    .. testcode:: tutorial_overview

            @inject(auto_provide=True)
            def f(service: MyService):
                return service

    :code:`auto_provide` specifies that all class type hints will be treated as dependencies,
    as if we used :py:obj:`.Provide`. As this would be cumbersome for codebases not relying
    on annotated type hints at all, one can use the :py:func:`.auto_provide` alias:

    .. testcode:: tutorial_overview

            from antidote import auto_provide

            @auto_provide
            def f(service: MyService):
                return service


You surely noticed the declaration of :code:`MyService` with:

.. code-block:: python

    world.singletons.add(MyService, MyService())

This declares a new singleton, :code:`MyService`, the class, pointing to a instance of
itself. A singleton is a dependency that never changes, it always returns the same object.
As such you cannot redefine an existing one:

.. doctest:: tutorial_overview

    >>> world.singletons.add(MyService, MyService())
    Traceback (most recent call last):
    ...
    DuplicateDependencyError: <class 'MyService'>

You can declare multiple singletons by passing a dictionary mapping dependencies to
their value:

.. doctest:: tutorial_overview

    >>> world.singletons.add({'favorite number': 11})

To retrieve our new singleton with :py:func:`.inject` we could do:

.. testcode:: tutorial_overview

    from typing import Annotated
    # from typing_extensions import Annotated # Python < 3.9

    from antidote import Get

    @inject
    def get_favorite_number(number: Annotated[int, Get("favorite number")]):
        return number

    # Or without annotated type hints we explicitly declare a mapping between
    # argument names and their dependency.
    @inject(dependencies=dict(number='favorite number'))
    def get_favorite_number(number: int):
        return number

    # Or with auto_provide which simply adds auto_provide=True in @inject
    # (See previous note)
    @auto_provide(dependencies=dict(number='favorite number'))
    def get_favorite_number(number: int):
        return number

.. doctest:: tutorial_overview

    >>> get_favorite_number()
    11

Having to create a function :code:`get_favorite_number` to retrieve a simple singleton
would lead to a very bloated code. So for this you can use :py:func:`.world.get`:

.. doctest:: tutorial_overview

    >>> world.get('favorite number')
    11

Any dependency can be retrieved with it, not just singletons. Unfortunately, contrary
to :code:`get_favorite_number` we lose type information for Mypy and your IDE for
auto completion. To avoid this, Antidote provides a syntax similar to static languages:

.. doctest:: tutorial_overview

    >>> world.get[int]('favorite number')  # will be considered as a `int` by Mypy
    11
    >>> world.get[MyService](MyService)  # Mypy will understand that this returns a MyService
    <MyService object at ...>
    >>> # As `MyService` is redundant here, you can omit it:
    ... world.get[MyService]()
    <MyService object at ...>

The type information will be used to cast the result to the right type. The cast follows
the same philosophy as Mypy, it won't actually check the type. Specifying the wrong type
will not raise an error:

.. doctest:: tutorial_overview

    >>> world.get[str]('favorite number')  # will be considered as a `str` by Mypy
    11

It'll only confuse Mypy and your IDE.

.. note::

    While you're free to use :py:func:`.world.get` anywhere you want, better use
    :py:func:`.inject`:

    .. testcode:: tutorial_overview

        @inject
        def good_function(service: Provide[MyService]):
            return service

        def bad_function():
            """
            We're not doing any dependency injection anymore ! We only use Antidote to
            manage dependencies, not more. This makes bad_function() *a lot harder* to
            test !
            """
            service = world.get[MyService]()
            return service

    Furthermore :code:`good_function` is actually faster ! This even more true when using
    the compiled version of Antidote (with Cython), making :code:`good_function` 10x faster.

    The compiled version of Antidote is heavily tuned to have best performance
    with :py:func:`.inject`. You can check whether you're using the compiled version
    with :py:func:`.is_compiled`. Pre-built wheels are only available for Linux currently.



2. Services
===========


We declared :code:`MyService` before as a singleton by hand, but Antidote provides a
better way to do this, defining a :py:class:`.Service` ! A service is a class which
provides some sort of functionality. A common example is a class serving as an interface
to some external system like a database:

.. testcode:: tutorial_services

    from antidote import inject, Service, Provide

    # Automatically declared by inheriting Service
    class Database(Service):
        def __init__(self):
            self.users = [dict(name='Bob')]

    @inject
    def get_user_count(db: Provide[Database]):
        return len(db.users)

.. doctest:: tutorial_services

    >>> get_user_count()
    1

By default :py:class:`.Service`\ s are singletons, they are only instantiated once:

.. doctest:: tutorial_services

    >>> from antidote import world
    >>> world.get[Database]() is world.get[Database]()
    True

As services will depend on each other, all methods are wired with :py:func:`.inject`
by default, including :code:`__init__()`. Meaning that you can use annotated type
hints anywhere and they will be taken into account as shown hereafter:

.. testcode:: tutorial_services

    class UserAPI(Service):
        # We didn't need to specify @inject as UserAPI is a Service
        def __init__(self, database: Provide[Database]):
            self.database = database

        def get_user_count(self):
            return len(self.database.users)

.. doctest:: tutorial_services

    >>> from antidote import world
    >>> world.get[UserAPI]().get_user_count()
    1

Those default behaviors can be changed easily with a custom
:py:class:`.Service.Conf` in your :py:class:`.Service`. For example you could create
a non singleton service which uses :code:`auto_provide=True` by default:

.. testcode:: tutorial_services

    class QueryBuilder(Service):
        __antidote__ = Service.Conf(singleton=False).auto_provide()

        def __init__(self, database: Database):
            self.database = database

.. doctest:: tutorial_services

    >>> world.get[QueryBuilder]() is world.get[QueryBuilder]()
    False

.. note::

    Here :py:meth:`.Service.Conf.auto_provide` is a simplification like the decorator
    :py:func:`.auto_provide`. Underneath it's actually using
    :py:meth:`.Service.Conf.with_wiring` which configures the whole :py:class:`.Wiring` of
    the service, meaning how and which methods are injected. More information on it
    the next section !

You may also find yourself in situations where a single service should be used with
different parameters. For example, let's create a simple service which accumulates metrics
during the application lifetime and flushes it to the database. We could create subclasses
for each possible metric, but that would obviously be cumbersome. Hence Antidote allows
you to specify constructor arguments when requesting a :py:class:`.Service`:

.. testcode:: tutorial_services

    class MetricAccumulator(Service):
        def __init__(self, name: str, database: Provide[Database]):
            self.name = name
            self._database = database
            self._buffer = []

        @classmethod
        def of(cls, name: str):
            """
            Wrapping _with_kwargs() to provide a cleaner interface with arguments and type
            hints and not just **kwargs.
            """
            return cls._with_kwargs(name=name)

        def add(self, value: int):
            self._buffer.append(value)

        def flush(self):
            """flushes buffer to database"""

.. doctest:: tutorial_services

    >>> count_metric = world.get[MetricAccumulator](MetricAccumulator.of('count'))
    >>> count_metric.name
    'count'
    >>> # The same instance is returned because `MetricAccumulator` is defined as a singleton.
    ... count_metric is world.get(MetricAccumulator.of('count'))
    True

When the same arguments are specified, the same service instance will be returned if the
service is defined as a singleton. Simple, yet effective when you need the same service
with different configuration at the same time. With annotated type hints, it would look
like this:


.. testcode:: tutorial_services

    from typing import Annotated
    # from typing_extensions import Annotated # Python < 3.9

    from antidote import Get

    CountMetricAccumulator = Annotated[MetricAccumulator,
                                       Get(MetricAccumulator.of('count'))]

    @inject
    def f(count_metric: CountMetricAccumulator):
        pass

    # Or without annotated type hints. Here we're passing a list of dependencies, so
    # its mapped to the arguments through their position.
    @inject(dependencies=[MetricAccumulator.of('count')])
    def f(count_metric: MetricAccumulator):
        pass

.. note::

    If you cannot inherit from :py:class:`.Service`, you can use the class decorator
    py:func:`.service`:

    .. doctest:: tutorial_services_alternative

        >>> from antidote import service, world
        >>> @service
        ... class Database:
        ...     pass
        >>> world.get[Database]()
        <Database ...>

    However Antidote will only declare as it as a dependency, nothing more. If you want
    some method wiring, check out :py:func:`.wire`.

    You SHOULD ONLY use it to register your own classes. If you want to register external
    classes in Antidote, you should rely on a factory instead presented later.



3. Injection & Wiring
=====================


Function
--------

Injection is done with the decorator :py:func:`.inject`. Everything else,
:py:func:`.auto_provide`, :py:func:`.wire` and auto-wiring of :py:class:`Service`
through :py:class:`Wiring` relies on it. As such they mostly have the same arguments with
the same behavior. Their differences are present a bit later.

By default :py:func:`.inject` relies only on annotated type hints to determine what must
be injected it supports also supports :code:`auto_provide`, :code:`use_names`
and :code:`dependencies`. As they conflict with each other, the most explicit one is always
used first:

1.  Annotated type hints.

    .. testcode:: tutorial_injection

        from antidote import inject, Service, Provide

        class MyService(Service):
            pass

        @inject
        def f(my_service: Provide[MyService]):
            pass

2.  :code:`dependencies` Defines explicitly which dependency to associate with which
    argument. The most common usage are either with a dictionary:

    .. testcode:: tutorial_injection

        from antidote import world

        world.singletons.add('host', 'localhost')

        @inject(dependencies=dict(my_service=MyService, host='host'))
        def f(my_service: MyService, host: str):
            pass

    Or with an iterable of dependencies. In this case the ordering of the dependencies
    is used to

    .. testcode:: tutorial_injection

        from antidote import world

        # When needed None can be used a placeholder for argument that should be ignored.
        @inject(dependencies=[MyService, 'host'])
        def f(my_service: MyService, host: str):
            pass

3.  :code:`auto_provide`: When set to :py:obj:`True`, class type hints will be treated
    as dependencies. You can restrict this behavior by specifying a list of classes for
    which it should be used:

    .. testcode:: tutorial_injection

        class MyService(Service):
            pass

        @inject(auto_provide=True)
        def f(my_service: MyService):
            pass

        @inject(auto_provide=[MyService])
        def f(my_service: MyService):
            pass

    For simplicity, Antidote provides :py:func:`.auto_provide` which simply sets
    :code:`auto_provide=True` in :py:func:`.inject`. Annotated type hints and other
    arguments, :code:`dependencies` and :code:`use_names`, can still be used  with it.

4.  :code:`use_names`: When set to :py:obj:`True`, the argument names will be used as their
    dependency. You can restrict this behavior by specifying a list of argument names for
    which it should be used:

    .. testcode:: tutorial_injection

        world.singletons.add('a', 'something')

        @inject(use_names=True)
        def f(a: str):
            pass

        @inject(use_names=['a'])
        def f(a: str):
            pass


Antidote will only try to retrieve dependencies for an argument when it's missing. If
found, it'll be injected. If not, a :py:exc:`~.exceptions.DependencyNotFoundError` will
be raised if there is no default argument.


Class
-----

When declaring a service with :py:class:`.Service` we've seen that methods, such
as :code:`__init__()` will be automatically wired. Underneath it relies on :py:class:`.Wiring`
which will by default inject all methods. It supports the same arguments as :py:func:`.inject`,
namely :code:`auto_provide`, :code:`dependencies` and :code:`use_names`. Those will be used
for all injected methods. You can also specify explicitly which methods to inject with
:code:`methods`:

.. testcode:: tutorial_wiring

    from antidote import Service, Wiring, Provide

    class MyService(Service):
        pass

    class CustomWiring(Service):
        # Only get_host() will be injected with use_names=True
        __antidote__ = Service.Conf(wiring=Wiring(methods=['get_host'], use_names=True))

        # Annotated type hints works like for @inject
        def get_host(self, host_name: str, my_service: Provide[MyService]) -> str:
            return host_name

.. doctest:: tutorial_wiring

    >>> from antidote import world
    >>> world.singletons.add('host_name', 'localhost')
    >>> world.get[CustomWiring]().get_host()
    'localhost'

If you don't want any wiring at all, you just have to set it to :py:obj:`None`:

.. testcode:: tutorial_wiring

    class NoWiring(Service):
        # No wiring, nothing will be injected not even annotated type hints.
        __antidote__ = Service.Conf(wiring=None)

You can also :py:func:`.inject` with :py:class:`.Wiring`:

.. testcode:: tutorial_wiring

    from antidote import inject

    class MultiWiring(Service):
        __antidote__ = Service.Conf(wiring=Wiring(dependencies=dict(host='host_name')))

        def __init__(self, host: str):
            self.host = host

        def get_host(self, host: str) -> str:
            return host

        # Wiring will not override any injection made explicitly.
        @inject(dependencies=dict(host='different_host'))
        def different_host(self, host: str) -> str:
            return host

.. doctest:: tutorial_wiring

    >>> world.singletons.add('different_host', 'different')
    >>> x = world.get[MultiWiring]()
    >>> x.host == x.get_host()
    True
    >>> x.different_host()
    'different'

For conciseness, Antidote provides some shortcuts:

-   :py:meth:`~.Service.Conf.with_wiring`: allows to keep existing :py:class:`.Wiring`
    configuration and only change some parameters:

    .. testcode:: tutorial_wiring

        class UseNamesWiring(Service):
            __antidote__ = Service.Conf().with_wiring(use_names=True)

            def __init__(self, host_name: str):
                self.host_name = host_name

    .. doctest:: tutorial_wiring

        >>> world.get[UseNamesWiring]().host_name
        'localhost'

-   :py:meth:`~.Service.Conf.auto_provide`: Use :code:`auto_provide=True` by default, in
    the same spirit of :py:func:`.auto_provide`:

    .. testcode:: tutorial_wiring

        class AutoProvidedWiring(Service):
            __antidote__ = Service.Conf().auto_provide()  # equivalent to with_wiring(auto_provide=True)

            def __init__(self, my_service: MyService):
                self.my_service = my_service

    .. doctest:: tutorial_wiring

        >>> world.get[AutoProvidedWiring]().my_service is world.get[MyService]()
        True

-   If you want to wire classes outside of Antidote, you can use the class decorator
    :py:func:`.wire` which has the same arguments as :py:class:`.Wiring`:

    .. testcode:: tutorial_wiring

        from antidote import wire

        @wire
        class Dummy:
            def get(self, my_service: Provide[MyService]):
                return my_service

    .. doctest:: tutorial_wiring

        >>> Dummy().get() is world.get[MyService]()
        True


4. Configuration
================


Antidote main goal for configuration is to enable you to trace back where it comes from
easily, like a service where you only need to go to the class definition.

.. testcode:: tutorial_conf

    from typing import Annotated
    # from typing_extensions import Annotated # Python < 3.9

    from antidote import Constants, inject, const, Get

    class Config(Constants):
        PORT = const[int]('port')   # value will be passed on to get()
        DOMAIN = const('domain')  # type is not required

        # Like Service, all methods are injected by default.
        def __init__(self):
            self._data = dict(domain='example.com', port='3000')

        # Method called to actually retrieve the configuration.
        def get(self, key):
            return self._data[key]

    @inject
    def absolute_url(path: str,
                     domain: Annotated[str, Get(Config.DOMAIN)],
                     port: Annotated[int, Get(Config.PORT)]):
        return f"https://{domain}:{port}{path}"

    # Or without any annotated type hints.
    # Here None is simply a placeholder, nothing will be injected.
    @inject(dependencies=(None, Config.DOMAIN, Config.PORT))
    def absolute_url(path: str, domain: str, port: int):
        return f"https://{domain}:{port}{path}"

.. doctest:: tutorial_conf

    >>> absolute_url("/user/1")
    'https://example.com:3000/user/1'
    >>> absolute_url('/dog/2', port=80)
    'https://example.com:80/dog/2'
    >>> # For easier testing you can also use a Config instance directly
    ... Config().DOMAIN
    'example.com'

All attributes defined with :py:func:`.const` are lazy constants. Their associated value
is passed on to :py:meth:`~.Constants.get` and the result is the actual dependency value.
It is then treated as a singleton, and so will only be called once at most. To let you
test easily all of this, you still access constants directly on a instance as shown before.

This might seem a bit overkill for simple configuration, but this provides some big
advantages:

- Configuration is lazily injected, even the class :code:`Config` will only be instantiated
  whenever necessary.
- Clear separation of what you need and how you get it, you don't need to know where
  :code:`Config.DOMAIN` comes from. You just state that you need it.
- It is still easy to trace back to the actual configuration code, you just have to
  go to the definition of the attribute.

You probably noticed that :code:`Config.PORT` is declared to be an integer, even though
it's stored as an string ! So what's the actual value ?

.. doctest:: tutorial_conf

    >>> from antidote import world
    >>> port = world.get(Config.PORT)
    >>> port
    3000
    >>> type(port)
    <class 'int'>

This is one of the few cases where Antidote does use magic: :py:class:`.Constants` will,
by default, automatically cast integers, floats and strings. You can control that behavior
with :py:class:`.Constants.Conf.auto_cast`. Additional examples can be found in :doc:`./recipes`



5. Factories & External dependencies
====================================


Factories are ideal to deal with external dependencies which you don't own,
like library classes. The simplest way to declare a factory, is simply to use the function
decorator :py:func:`.factory.factory`:

.. testcode:: tutorial_factory

    from typing import Annotated
    # from typing_extensions import Annotated # Python < 3.9

    from antidote import factory, inject, ProvideArgName, From

    # Suppose we don't own the class code, hence we can't define it as a Service
    class Database:
        def __init__(self, url: str):
            self.url = url


    @factory
    def default_db(url: ProvideArgName[str]) -> Database:
        return Database(url)

    @inject
    def f(db: Annotated[Database, From(default_db)]) -> Database:
        return db

    # Or without annotated type hints
    @factory
    @inject(use_names=True)
    def default_db(url: str) -> Database:
        return Database(url)

    @inject(dependencies=[Database @ default_db])
    def f(db: Database) -> Database:
        return db

.. doctest:: tutorial_factory

    >>> from antidote import world
    >>> world.singletons.add('url', 'localhost:5432')
    >>> f()
    <Database ...>
    >>> world.get[Database](Database @ default_db)
    <Database ...>


The return type MUST always be specified, this is how Antidote knows which dependency you
intend to provide. :py:func:`.factory.factory` will apply :py:func:`.inject` on the function if not
done already. Hence you can use annotated type hints out of the box but no more without
injecting explicitly. You're probably wondering about the custom syntax when not using
annotated type hints :code:`Database @ default_db`. It provides some very nice properties

- You can trace back how :code:`Database` is instantiated.
- The factory :code:`default_db` will always be loaded by Python before using
  :code:`Database`.

If you need more complex factories, you can use a class instead by inheriting :py:class:`.Factory`:

.. testcode:: tutorial_factory_v2

    from typing import Annotated
    # from typing_extensions import Annotated # Python < 3.9

    from antidote import Factory, ProvideArgName

    class Database:
        def __init__(self, url: str):
            self.url = url

    class DefaultDB(Factory):
        def __init__(self, url: ProvideArgName[str]):
            self.url = url

        # Will be called to instantiate Database
        def __call__(self) -> Database:
            return Database(url)

:py:class:`.Factory` has more or less the same configuration parameters than :py:class:`.Service`:

- :py:class:`.Factory.Conf` like :py:class:`.Service.Conf`
- :py:class:`.Factory._with_kwargs` like :py:class:`.Service._with_kwargs`



6. Tests
========


You've seen until now that Antidote's :py:func:`.inject` does not force you to rely on
the injection to be used:

.. testcode:: tutorial_test

    from antidote import Service, inject, Provide

    class MyService(Service):
        pass

    @inject
    def f(my_service: Provide[MyService]) -> MyService:
        return my_service

    # injection
    f()

    # but you can still do either:
    f(MyService())
    f(my_service=MyService())

This allows to test easily individual components in unit-tests easily. But that's not always
enough in more complex tests or integration tests. Don't worry, Antidote got you covered !
In the first section Antidote was roughly described as working as follows::

                 +-----------+
          +----->|   world   +------+
          |      +-----------+      |

     declaration                 @inject

          |                         |
          |                         v
    +-----+------+             +----------+
    | Dependency |             | Function |
    +------------+             +----------+

But that's not really what is happening, in reality we have::

                 +-----------+
                 |   world   |
                 +-----+-----+
                       |
                       +
                    controls
                       +
                       |
                       v
                +------+------+
          +---->+  container  +-----+
          |     +-------------+     |
          +                         +
     declaration                 @inject
          +                         +
          |                         |
    +-----+------+                  v
    | Dependency |             +----+-----+
    +------------+             | Function |
                               +----------+


The container handles all of the state of Antidote such as singletons. The good news is
that :py:mod:`.world` does provide to you the tools to control it in :py:mod:`.world.test`.
Allowing you to override dependencies or test in isolated environments. The most important
one is :py:func:`.world.test.clone`. It'll keep all of your dependency declaration and
isolate you from the outside world:

.. doctest:: tutorial_test

    >>> from antidote import world
    >>> with world.test.clone():
    ...     # This works as expected !
    ...     my_service = f()
    >>> # but it's isolated from the rest
    ... my_service is world.get(MyService)
    False


It'll also apply :py:func:`.world.freeze` the local world, meaning that no new dependencies
cannot be added. It ensures that you cannot change the wiring of your dependencies which you
intend to test.

.. doctest:: tutorial_test

    >>> with world.test.clone():
    ...     world.singletons.add('test', 1)
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
    FrozenWorldError


Doesn't sound very helpful by itself, but you can use :py:mod:`.world.test.override` to
override any dependency in it:

.. doctest:: tutorial_test

    >>> with world.test.clone():
    ...     world.test.override.singleton(MyService, 'dummy')
    ...     f()
    'dummy'

:py:mod:`.world.test.override` exposes three ways to override dependencies:

-   :py:func:`~.world.test.override.singleton`

    .. doctest:: tutorial_test

        >>> # Use either world.test.override or override directly
        ... from antidote.world.test import override
        >>> with world.test.clone():
        ...     override.singleton(MyService, 'dummy')
        ...     # Can be redefined
        ...     override.singleton(MyService, 'dummy')
        ...     # Multiple dependencies can be declared with a dict
        ...     override.singleton({MyService: 'dummy'})
        ...     f()
        'dummy'

-   :py:func:`~.world.test.override.factory`

    .. doctest:: tutorial_test

        >>> with world.test.clone():
        ...     @override.factory()
        ...     def override_my_service() -> MyService:
        ...         return 'dummy'
        ...     # Can be redefined and will remove any existing instance
        ...     # (if singleton for example)
        ...     @override.factory()
        ...     def override_my_service() -> MyService:
        ...         return 'dummy'
        ...     f()
        'dummy'

-   :py:func:`~.world.test.override.provider`

    .. doctest:: tutorial_test

        >>> from antidote.core import DependencyValue
        >>> with world.test.clone():
        ...     @override.provider()
        ...     def dummy_provider(dependency):
        ...         if dependency is MyService:
        ...             return DependencyValue('dummy')
        ...     f()
        'dummy'

    The decorated function will be called each time a dependency is needed. If it can be
    provided it should be returned wrapped by a :py:class:`~.core.DependencyValue` which also
    defines whether the dependency value is a singleton or not.

    .. warning::

        Beware of :py:func:`~.world.test.override.provider`, it can conflict with
        :py:func:`~.world.test.override.factory` and :py:func:`~.world.test.override.singleton`.
        Dependencies declared with :py:func:`~.world.test.override.singleton` will hide
        :py:func:`~.world.test.override.provider`. And :py:func:`~.world.test.override.provider`
        will hide :py:func:`~.world.test.override.factory`.

:py:func:`.world.test.clone` will not keep any existing singleton by default, but you may change
it:

.. doctest:: tutorial_test

    >>> world.singletons.add('hello', 'world')
    >>> with world.test.clone():
    ...     world.get('hello')
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
    DependencyNotFoundError: 'hello'
    >>> with world.test.clone(keep_singletons=True):
    ...     world.get('hello')
    'world'

.. warning::

    Beware. keeping singletons will re-use the same object:

    .. doctest:: tutorial_test

        >>> world.singletons.add('buffer', [])
        >>> with world.test.clone(keep_singletons=True):
        ...     world.get('buffer').append(1)
        >>> world.get('buffer')  # We changed the singleton of the outside world.
        [1]

:py:mod:`.world.test` provides additional utilities when extending Antidote or defining abstract
factories / services.


