"""
Utilities to overrides dependencies in Antidote. Those can only be used in a test world
created by :py:func:`.world.test.clone` with :code:`overridable=True`. Dependencies
can be overridden multiple times, it won't raise any error. Overridden dependencies also
won't be taken into account when Antidote checks for duplicates. Hence you may do the
following:

.. doctest:: world_override

    >>> from antidote import world
    >>> with world.test.clone():
    ...     world.test.override.singleton('test', 1)
    ...     # Override a second time a singleton
    ...     world.test.override.singleton('test', 1)
    ...     world.get[int]("test")
    1

.. note::

    Overrides works as a layer on top of the usual dependencies. So they can interfer
    with each other.

    .. doctest:: world_override

        >>> from antidote import world
        >>> with world.test.clone():
        ...     world.test.override.singleton('test', 1)
        ...     # 'test' is already a singleton in the override layer, so the factory
        ...     # won't be taken into account.
        ...     @world.test.override.factory('test')
        ...     def test():
        ...         return 2
        ...     world.get[int]("test")
        1

    The priority of the overrides is the following:

    1. singletons
    2. providers
    3. factories

"""
from ._override import factory, provider, singleton

__all__ = ['singleton', 'factory', 'provider']
