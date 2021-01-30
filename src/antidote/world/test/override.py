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
    ...     world.test.override.singleton('test', 2)
    ...     world.get[int]("test")
    2

"""
from ._override import factory, provider, singleton

__all__ = ['singleton', 'factory', 'provider']
