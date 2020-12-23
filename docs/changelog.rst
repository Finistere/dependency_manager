*********
Changelog
*********

Status
======

Overall satisfied with the API, will take some time (weeks) to see what examples may be
missing or what could be removed/simplified before making a v1.0.



0.10.0 (2020-12-24)
===================


Breaking change
---------------

- In :py:class:`.Wiring`, :code:`ignore_missing_methods` has been replaced by
  :code:`attempt_methods`.


Bug fix
-------

- Using :py:meth:`.inject` on :code:`__init__()` of a :py:class:`.Service`, or any methods
  injected by default by Antidote, will not raise a double injection error anymore.



0.9.0 (2020-12-23)
==================


Features
--------

- Antidote exposes its type information (PEP 561) and passes strict Mypy (with implicit optionals).


Breaking changes
----------------

- Antidote exceptions have no public attributes anymore.
- Injecting twice the same function/method will raise an error.
- :py:class:`.Constants` has been simplified, :py:func:`.const` is now simply always required
  to define a constant.


Changes
-------

- Better, simpler :code:`DependencyInstantiationError` when a deeply nested dependency fails.
- Cleaner packaging: Antidote will only try to compile Cython when the environment variable
  :code:`ANTIDOTE_COMPILED` is set to :code:`true` and doesn't require Cython to be pre-installed
  to do so. Antidote's version is also hardcoded at publish time.
- Added a Scope example in the documentation. It is a bit more complicated than I would like,
  but scopes are hard



0.8.0 (2020-12-09)
==================


Features
--------

- Reworked entirely :code:`world`:
    - Cleaner singletons declarations in :py:mod:`.world.singletons`
    - Test utilities in :py:mod:`.world.test`. Those allow you to change locally, withing a
      context manager, dependencies declarations. Hence you can replace an existing
      dependency by a mock for example.
    - Override utilities in :py:mod:`.world.test.override` to be used in tests.
    - Debug utility :py:func:`.world.debug` which returns a tree of all the dependencies
      that will/may be retrieved by Antidote.
    - Add type hints to :py:func:`.world.get` which can now be used like :code:`world.get[<class>]("x")`
    - Add :py:func:`.world.lazy` for dependencies to retrieve dependencies lazily.
- :py:func:`.implementation` is more flexible than :code:`@implements` and supports changing the
  implementation at runtime for example.
- :py:class:`.Service` and :py:class:`.Factory` expose a handy class method
  :py:meth:`~.Service.with_kwargs` which allows you to specify some key word argument to
  customize the service you're retrieving. Typically you would have only one database
  service class but use this feature to have two different dependencies which each point to
  different database.
- :py:class:`.Constants`, formerly :code:`LazyConstantsMeta`, supports a new of defining constants:
  :py:func:`.const`. It has two purposes, explicitly define constants and optionally specify
  the actual type.
- Added :py:func:`.world.freeze` which will prevent any new dependencies to be added.


Breaking changes
----------------

- Drop support of Python 3.5.
- Singletons do check for duplicates now. Hence one cannot redefine an existing singleton
  through :code:`world`.
- :code:`world.update_singletons` does not exists anymore, use :py:func:`.world.singletons.add_all` or
  :py:func:`.world.singletons.add` instead.
- :code:`@register` is now replaced by the class :py:class:`.Service` and provides mostly the same
  features. The only corner cases are service that used factories, those should now
  really use a factory, namely :py:class:`.Factory` or :py:class:`.factory`. If you cannot
  inherit the super class for some reason, you may fallback to the class decorator
  :py:func:`.service`.
- :code:`@factory` for functions behaves the same way, however for factory classes the super
  class :py:class:`.Factory` must be used. The dependency identifier has also been to changed,
  the factory must now be specified like :code:`dependency @ factory` instead of :code:`dependency`.
- :code:`LazyConstantsMeta` has been replaced by the class :py:class:`.Constants`. One cannot
  choose the lazy method anymore, but it is more flexible regarding definition of constants.
- :code:`@implements` has been entirely reworked and split into :py:func:`.implementation` and
  :py:class:`.Implementation`. The latter can be used for straightforward cases where only
  one implementation exists. The first lets you handle all other cases with multiple
  implementations which can vary during runtime or not.
- :code:`@provider` has been replaced by the class decorator :py:func:`.world.provider`.
- Everything related to the container management has been removed for the public interface.


Changes
-------

- Add Python 3.9 support.
- public APIs are clearly defined as such, marked by :code:`@API.public`. Overall public API
  is also better defined.
- Improved Cython performance



0.7.2 (2020-04-21)
==================


Bug fixes
---------

- The wrapper of the injection function didn't behave exactly like a proxy for the 
  all of the wrapped functions attributes. Furthermore the Cython version didn't 
  support setting dynamically attributes at all.



0.7.0 (2020-01-15)
==================


Breaking changes
----------------

- :code:`@register` does not wire :code:`__init__()` anymore if a function is provided as a factory.
  This didn't make a lot of sense, :code:`__init__()` is wrapped automatically if and only if
  it is treated as the "factory" that creates the object.
- Now when using :code:`dependencies` argument with a sequence (matching dependencies with arguments
  through their position), the first argument will be ignored for methods (`self`) and 
  classmethod (`cls`). So now you can write:

  .. code-block:: python

      from antidote import inject, service

      class Service:
          @inject(dependencies=('dependency',))
          def method(self, arg1):
              ...

          @inject(dependencies=('dependency',))
          @classmethod
          def method(cls, arg1):
              ...

      @service(dependencies=('dependency',))
      class Service2:
          def __init__(self, arg1):
              ...

  Hence all other decorators profit from this. No need anymore to explicitly ignore :code:`self`.


Bug fixes
---------

- Prevent double :code:`LazyMethodCall` wrapping in :code:`LazyConstantsMeta` (Thanks @keelerm84)
- :code:`@inject` cannot be applied on classes. This was never intended as it would not
  return a class. Use :code:`@wire` instead if you relied on this.
- :code:`@inject` returned :code:`ValueError` instead of :code:`TypeError` in with erroneous types.
- :code:`@register` now raises an error when using a method as a factory that is neither a
  classmethod nor a staticmethod. It was never intended to use methods, as it would not
  make sense.


Changes
-------

- When wrapping multiple methods, :code:`@wire` used to raise an error if a sequence was
  provided for :code:`dependencies`. This limitation has been removed.



0.6.1 (2019-12-01)
==================


- Add support for Python 3.8



0.6.0 (2019-05-06)
==================


Features
--------

- Add :code:`@implements` to define service implementing an interface.
- Add :code:`IndirectProvider()` which supports :code:`@implements`.
- Add :code:`Container.safe_provide()` which does the same as
  :code:`Container.provide()` except that it raises an error if
  the dependency cannot be found instead of returning None.


Breaking changes
----------------

- :code:`Container.provide()` returns a :code:`DependencyInstance` not the
  instance itself anymore.
- Rename :code:`LazyConfigurationMeta` to :code:`LazyConstantsMeta`.
- :code:`LazyConfigurationMeta` default method is :code:`get()`.
- :code:`ServiceProvider` renamed to :code:`FactoryProvider` and reworked
  :code:`ServiceProvider.register()` with is split into :code:`register_factory()`,
  :code:`register_class`, :code:`register_providable_factory`.


Changes
-------

- Moved :code:`is_compiled` to :code:`antidote.utils`.
- Add better type hints.



0.5.1 (2019-04-27)
==================


Features
--------

- Add :code:`is_compiled()` to check whether the current version is compiled or pure
  python.



0.5.0 (2019-04-27)
==================


Breaking changes
----------------

- :code:`@resource` has been removed an replaced by :code:`LazyConfigurationMeta` to handle
  configuration. 


Features
--------

- Add :code:`LazyMethodCall` and :code:`LazyCall` to support output of functions as dependencies.


Changes
-------

- Add better type hints for helper decorators.



0.4.0 (2019-02-03)
==================


A lot of internals have changed, but it can roughly be resumed as the following:


Breaking changes
----------------

- The :code:`DependencyManager` does not exist anymore and has been replaced by
  multiple helpers which accepts a :code:`container` argument. By default the global
  container of Antidote is used. Thus one can easily replace 
  :code:`from antidote import antidote` to :code:`import antidote` to adapt existing code.
- The global container of Antidote, previously named :code:`container`, has been
  renamed :code:`world`.
- :code:`Dependency` does not take additional arguments anymore, for custom
  dependencies :code:`Build`, :code:`Tagged` must be used instead.
- Custom providers must inherit :code:`Provider`.
- :code:`register_parameters()` has been replaced by a more general function,
  :code:`resource()`. See the documentation to imitate its functionality.
- :code:`factory()` is more strict. Subclasses are not handled anymore, one should
  use :code:`register()` with its :code:`factory` argument instead.


Features
--------

- Dependencies can be tagged at registration. Those can then be retrieved as
  a dependency. This allows one to extend an app by registering a service in
  special way just by adding a tag.
- Type hints usage can now be finely controlled or disabled with :code:`use_type_hints`.
- Add :code:`resource()` to support custom resources, such as configuration.
- Dependency providers are more strict for more maintainable code.
- Use of Cython for better injection performance.



0.3.0 (2018-04-29)
==================


Initial release
