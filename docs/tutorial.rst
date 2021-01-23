***************
Getting started
***************

This is a beginner friendly tutorial on how to use Antidote features to write better code.
It is a series of steps to show what can be done easily. It will focus on how to declare
services and configuration. Note that Antidote can do a lot more than presented here,
don't hesitate to check out the recipes and references for more in depth documentation.


1. World
========

First of all, let's start with a quick example:

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
By default it'll rely on the type hints and try to find any *missing* arguments.
*Missing* ? Yes ! You can still call :code:`f` normally:

.. doctest:: tutorial_overview

    >>> f(MyService())
    <MyService object at ...>

.. note::

    :py:func:`.inject` being one of the core mechanism of Antidote, it is designed to be
    very flexible. Hence it supports multiple ways to define which dependencies should be
    injected for each argument. You'll encounter some of them later in this tutorial, but
    don't hesitate to check out its documentation by clicking on :py:func:`.inject` !

You surely noticed the declaration of :code:`MyService` with:

.. code-block:: python

    world.singletons.add(MyService, MyService())

This declares a new singleton, :code:`MyService` (the class) pointing to a instance of
itself. A singleton is a dependency that never changes, it always returns the same object.
Hence requesting the dependency :code:`MyService` will return this instance from now on.
It also means that you cannot redefine an existing singleton:

.. doctest:: tutorial_overview

    >>> from antidote.exceptions import DuplicateDependencyError
    >>> try:
    ...     world.singletons.add(MyService, MyService())
    ... except DuplicateDependencyError:
    ...     print("Error raised !")
    Error raised !

If you need to declare multiple of them :py:mod:`.world` provides a shortcut
:py:func:`.world.singletons.add_all` :

.. doctest:: tutorial_overview

    >>> world.singletons.add({'favorite number': 11})

        And on top of that, you can retrieve dependencies directly with :py

    And on top of that, you can retrieve dependencies directly with :py

    And on top of that, you can retrieve dependencies directly with :py

And on top of that, you can retrieve dependencies directly with :py:mod:`.world.get`:

.. doctest:: tutorial_overview

    >>> world.get('favorite number')
    11

As :py:mod:`~.world.get` can return anything, we unfortunately lose any type information
for Mypy and your IDE for auto completion. To avoid this, you can specify a cast:

.. doctest:: tutorial_overview

    >>> world.get[int]('favorite number')  # will be considered as a `int`
    11
    >>> world.get[MyService](MyService)  # Mypy will understand that this returns a MyService
    <MyService object at ...>
    >>> # As repeated `MyService` is redundant when we're casting to a class
    ... # we're requesting, you can omit it:
    ... world.get[MyService]()
    <MyService object at ...>

The cast follows the same philosophy as Mypy, it won't actually check the type.
In the next steps we will take a look a the different kind of dependencies Antidote
provides out of the box.


2. Services
===========

We declared :code:`MyService` before as a singleton by hand, but Antidote provides a
better way to do this, defining a :py:class:`.Service` ! A service is a class which
provides some sort of functionality. A common example is a class serving as an interface
to some external service like a database:

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

But that's just the tip of the iceberg ! By default it'll also auto wire
:code:`__init__()`. Auto-wiring meaning roughly automatically applying
:py:func:`.inject` on predefined methods. Here after is a different example relying on
:code:`Database`:

.. testcode:: tutorial_services

    class UserAPI(Service):
        def __init__(self, database: Provide[Database]):
            self.database = database

        def get_user_count(self):
            return len(self.database.users)

.. doctest:: tutorial_services

    >>> from antidote import world
    >>> world.get[UserAPI]().get_user_count()
    1

Another important default is that :py:class:`.Service` are singletons by default:

.. doctest:: tutorial_services

    >>> from antidote import world
    >>> world.get[UserAPI]() is world.get[UserAPI]()
    True

To suits your needs Antidote provides a simple, static typing friendly, way to configure
your :py:class:`.Service` with a custom :py:class`.Service.Conf` to be defined in
:code:`__antidote__`:

.. testcode:: tutorial_services

    class MetricAccumulator(Service):
        # Check out the documentation for more information on configuration
        # parameters !
        __antidote__ = Service.Conf(singleton=False)

        def __init__(self, database: Provide[Database], name: str = 'my_metric'):
            self.name = name
            self._database = database
            self._buffer = []

        def add(self, value: int):
            self._buffer.append(value)

        def flush(self):
            """flushes buffer to database"""

.. doctest:: tutorial_services

    >>> # A different instance is returned each time
    ... world.get[MetricAccumulator]() is world.get[MetricAccumulator]()
    False
    >>> # By default name will be 'my_metric'
    ... world.get[MetricAccumulator]().name
    'my_metric'
    >>> # But you can also provide keyword arguments to customize your services
    ... count_metric = world.get[MetricAccumulator](MetricAccumulator.with_kwargs(name='count'))
    >>> count_metric.name
    'count'
    >>> # A different instance will always be returned nonetheless. However for singletons
    ... # the same instance would be returned for the same keyword arguments.
    ... count_metric is world.get(MetricAccumulator.with_kwargs(name='count'))
    False

We've seen another feature of :py:class:`.Service`: you can specify by some keyword arguments
explicitly when requesting it ! To stay consistent, the same instance will always be
returned when the :py:class:`.Service` is declared as a singleton and the same keyword
arguments are specified.

.. note::

    If you cannot inherit from :py:class:`.Service`, Antidote provides a backup method,
    the class decorator py:func:`.register`:

    .. doctest:: tutorial_services_alternative

        >>> from antidote import service, world
        >>> @service  # backup method if cannot inherit Service for whatever reason
        ... class Database:
        ...     pass
        >>> world.get[Database]()
        <Database ...>

    However Antidote won't be able to provide all the features of :py:class:`.Service`,
    hence prefer the latter whenever you can.

    You SHOULD ONLY use it to register your own classes. If you want to register external
    classes in Antidote, you should rely on


3. Injection & Wiring
=====================

As seen in the previous sections, injection is done with the decorator :py:func:`.inject`.
By default it relies on type hints to determine what must be injected but you it supports
a lot more. Here are a few examples:

.. testcode:: tutorial_injection

    from antidote import inject

    @inject(use_names=True)  # Argument names will be the dependency
    def get_country(country: str) -> str:
        return country

    # you can also specify the dependency explicitly with a mapping of the argument
    # names to their respective dependencies.
    @inject(dependencies=dict(name='app:name'))
    def get_app_name(name: str) -> str:
        return name

    # or simply through sequence of dependencies. Arguments are matched through their
    # position
    @inject(dependencies=['timezone'])
    def get_timezone(t: str) -> str:
        return t

.. doctest:: tutorial_injection

    >>> from antidote import world
        >>> world.singletons.add({'country': 'FR',
        ...                           'app:name': "Hello World !",
        ...                           'timezone': 'UTC'})
        >>> get_country()
        'FR'
        >>> get_app_name()
        'Hello World !'
        >>> get_timezone()
        'UTC'


An important thing to keep in mind is that Antidote has a specific priority:

1. Dependencies declared explicitly if any declared with :code:`dependencies`.
2. Type hints (unless deactivated through :code:`use_type_hints`)
3. Argument names if specified with :code:`use_names`

Antidote will only try to retrieve dependencies for an argument when it's missing. If
found, it'll be injected. If not, a :py:exc:`.exceptions.DependencyNotFoundError` will
be raised if and only if there is no default argument.

.. note::

    There are still more possibilities than presented here for greater flexibility, check
    the documentation :py:func:`.inject` for more examples !

When declaring a service with :py:class:`.Service` we've seen that the :code:`__init__()`
will be automatically wired. Auto-wiring refers to the automatic injection with
:py:func:`.inject` of certain methods/functions done under the hood. All of it
is defined in the class :py:class`.Wiring` which you can customize easily:

.. testcode:: tutorial_wiring

    from antidote import Service, Wiring

    class CustomWiring(Service):
        __antidote__ = Service.Conf(wiring=Wiring(methods=['get'], use_names=True))

        def get(self, host_name: str) -> str:
            return host_name

.. doctest:: tutorial_wiring

    >>> from antidote import world
    >>> world.singletons.add('host_name', 'localhost')
    >>> world.get[CustomWiring]().get()
    'localhost'

As this overrides any default wiring, :py:class:`.Service.Conf` provides another way of
customizing the wiring:

.. testcode:: tutorial_wiring

    class KeepAutoWiring(Service):
        # Only use_names is changed, so __init__() is still injected as by default.
        __antidote__ = Service.Conf().with_wiring(use_names=True)

        def __init__(self, host_name: str):
            self.host_name = host_name

.. doctest:: tutorial_wiring

    >>> world.get[KeepAutoWiring]().host_name
    'localhost'

If you don't want any wiring at all, you just have to set it to :py:obj:`None`:

.. testcode:: tutorial_wiring

    class NoWiring(Service):
        # No wiring, no method will be injected.
        __antidote__ = Service.Conf(wiring=None)


The primary goal of :py:class:`.Wiring` is to have a quick way to wire methods in a class.
Underneath it's only applying :py:func:`.inject`. Hence injection configuration is common
for all methods that have be to wired:

.. testcode:: tutorial_wiring

    from antidote import inject

    class MultiWiring(Service):
        __antidote__ = Service.Conf().with_wiring(methods=['__init__', 'get'],
                                                  # Used for both __init__() and get()
                                                  dependencies=dict(host='host_name'))

        def __init__(self, host: str):
            self.host = host

        def get(self, host: str) -> str:
            return host

        # When you can't share everything you have to fallback to injecting by hand
        @inject(dependencies=dict(host='different_host'))
        def different(self, host: str) -> str:
            return host

.. doctest:: tutorial_wiring

    >>> world.singletons.add('different_host', 'different')
    >>> x = world.get[MultiWiring]()
    >>> x.host == x.get()
    True
    >>> x.different()
    'different'


.. note::

    If you want to wire a class outside of Antidote, you can use the class
    :py:func:`.wire` or use :py:class:`.Wiring.wire` of an existing instance.


4. Configuration
================

Antidote main goal for configuration is to enable you to trace back where it comes from
easily, like a service where you only need to go to the class definition.

.. testcode:: tutorial_conf

    from antidote import Constants, inject, const

    class Config(Constants):
        PORT = const[int]('port')   # value will be passed on to get()
        DOMAIN = const('domain')  # type is not required

        # Like Service, __init__() will be auto-wired by default.
        def __init__(self):
            self._data = dict(domain='example.com', port='3000')

        # Method called to actually retrieve the configuration.
        def get(self, key):
            return self._data[key]

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
It is then treated as a singleton, and hence will only be called once at most. To let you
test easily all of this, you still access constants directly on a instance as shown before.

This might seem a bit overkill for simple configuration, but this provides some big
advantages:

- Configuration is lazily injected, even the class :code:`Config` will only be instantiated
  whenever necessary.
- Clear separation of what you need and how you get it, you don't need to know where
  :code:`Config.DOMAIN` comes from. You just state that you need it.
- It is still easy to trace back to the definition of the configuration, you just have to
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
with :py:class:`.Constants.Conf.auto_cast`.


5. Factories & External dependencies
====================================

Factories can be used for a lot more, but they're the best way to handle external
dependencies which you don't own, like library classes.

.. testcode:: tutorial_factory

    from antidote import factory, inject

    # Suppose we don't own the class code, hence we can't define it as a Service
    class Database:
        def __init__(self, url: str):
            self.url = url


    @factory
    @inject(use_names=True)
    def default_db(url: str) -> Database:  # return type MUST be specified
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
intend to provide. You're probably wondering about the custom syntax of
:code:`Database @ default_db`, no ? It provides some very nice properties

- You can trace back how :code:`Database` is instantiated.
- The factory :code:`default_db` will always be loaded by Python before using
  :code:`Database`.

If you need more complex factories, you can use a class instead:

.. testcode:: tutorial_factory_v2

    from antidote import Factory

    class Database:
        def __init__(self, url: str):
            self.url = url

    class DefaultDB(Factory):
        # Both __init__() and __call__() are auto-wired by default.
        __antidote__ = Factory.Conf().with_wiring(use_names=True)

        def __init__(self, url: str):
            self.url = url

        # Will be called to instantiate Database
        def __call__(self) -> Database:
            return Database(url)


6. Test & Debug
===============

You've seen until now that Antidote's :py:func:`.inject` does not force you to rely on
the injection to be used:

.. testcode:: tutorial_test_debug

    from antidote import Service, inject, Provide

    class MyService(Service):
        pass

    @inject
    def f(my_service: Provide[MyService]):
        pass

    # injection
    f()

    # but you can still do either:
    f(MyService())
    f(my_service=MyService())

But Antidote provides more than that to let you test more easily your code. Each time
an injection must be done, :py:func:`.inject` will retrieve :py:mod:`.world` where every
dependency has been defined and retrieve whatever necessary. This global state can be
controlled in your tests through :py:mod:`.world.test`:

.. doctest:: tutorial_test_debug

    >>> from antidote import world
    >>> # Creating an new world, previously declared dependencies are not present anymore
    ... with world.test.new():
    ...     f()
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
    DependencyNotFoundError

:py:func:`.world.test.new` will create a new world in which you can test anything you'd
like without impacting the rest. Typically this lets you test things in isolation:

.. doctest:: tutorial_test_debug

    >>> with world.test.new():
    ...     class TestOnlyService(Service):
    ...         pass
    ...     assert isinstance(world.get[TestOnlyService](), TestOnlyService)
    >>> # Once outside of this test world, TestOnlyService won't exist as a service:
    ... world.get[TestOnlyService]()
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
    DependencyNotFoundError

But what if you actually need :code:`MyService` ? Re-declaring it each time would be
cumbersome at best ! In this case you should use :py:func:`.world.test.clone`. It'll
clone the current world and won't propagate back any changes:

.. doctest:: tutorial_test_debug

    >>> with world.test.clone():
    ...     # this works !
    ...     f()

:py:func:`~.world.test.clone` will have the same dependencies, except for singletons. By
default they are NOT kept, but you can change that behavior:

.. doctest:: tutorial_test_debug

    >>> my_service = world.get[MyService]()  # Getting the real service instance
    >>> with world.test.clone():
    ...     # As existing singletons are NOT propagated to the test world, hence
    ...     # when requesting MyService, Antidote needs to create a new instance.
    ...     assert world.get[MyService]() is not my_service
    >>> # But if you prefer you can keep existing singletons:
    ... with world.test.clone(keep_singletons=True):
    ...     assert world.get[MyService]() is my_service
    >>> # Be careful with it ! any changes on the singletons themselves WILL be propagated
    ... # back
    ... world.singletons.add("languages", ["en"])
    >>> with world.test.clone(keep_singletons=True):
    ...     world.get[list]("languages").append("fr")
    >>> world.get("languages")
    ['en', 'fr']


While Antidote does not support overriding dependencies, you may do it in tests:

.. doctest:: tutorial_test_debug

    >>> with world.test.clone():
    ...     # This fails because new dependencies cannot be defined inside clone()
    ...     world.singletons.add("test", 1)
    Traceback (most recent call last):
    ...
    FrozenWorldError
    >>> with world.test.clone():
    ...     test_service = MyService()
    ...     world.test.override.singleton(MyService, test_service)
    ...     assert world.get[MyService]() is test_service



