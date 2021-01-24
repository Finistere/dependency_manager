*************
API Reference
*************



World Utilities
===============


world
-----

.. automodule:: antidote.world
    :members:

    .. autodata:: get

    .. autodata:: lazy

.. automodule:: antidote.utils
    :members: is_compiled


world.scopes
------------

.. automodule:: antidote.world.scopes
    :members:


world.singletons
----------------

.. automodule:: antidote.world.singletons
    :members:


world.test
----------

.. automodule:: antidote.world.test
    :members:


world.test.override
-------------------

.. automodule:: antidote.world.test.override
    :members:


Dependencies
============


Service
-------

.. automodule:: antidote.service
    :members: service

.. autoclass:: antidote.service.Service
    :members: __antidote__
    :inherited-members:

    .. automethod:: _with_kwargs


Factory
-------

.. automodule:: antidote.factory
    :members: factory

.. autoclass:: antidote.factory.Factory
    :members:
    :inherited-members:

    .. automethod:: _with_kwargs


Constants
---------

.. autoclass:: antidote.constants.Constants
    :members:


Lazy
----

.. automodule:: antidote.lazy
    :members:


Implementation
--------------

.. automodule:: antidote.implementation
    :members:


Tags
----

.. automodule:: antidote.tag
    :members: Tag, Tagged



Core
====


Injection
---------

Inject
^^^^^^
.. automodule:: antidote.core.injection
    :members: inject, Arg

Auto_provide
^^^^^^^^^^^^
.. automodule:: antidote.core.auto_provide
    :members:

Annotations
^^^^^^^^^^^
.. automodule:: antidote.core.annotations
    :members:

Wiring
^^^^^^
.. automodule:: antidote.core.wiring
    :members: Wiring, wire, WithWiringMixin

Utility
^^^^^^^
.. autoclass:: antidote.core.utils.Dependency
    :members:


Provider
--------

.. automodule:: antidote.core.provider
    :members:

.. automodule:: antidote.core.container
    :members:

.. autoclass::antidote.core.utils.DependencyDebug
    :members:



Exceptions
==========

.. automodule:: antidote.exceptions
    :members:
