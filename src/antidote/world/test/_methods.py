from contextlib import contextmanager
from typing import (Hashable, Iterator, Optional)

from ..._internal import API, state
from ...core.container import (DependencyValue, RawContainer, RawProvider)


@API.public
@contextmanager
def clone(*,
          keep_singletons: bool = False,
          keep_scopes: bool = False
          ) -> Iterator[None]:
    """
    Clone the current container, namely scopes and providers. Existing singletons and
    scopes depdency values can also be propagated. Its primary use is to test existing
    dependencies. Hence the world will already be frozen but overridding dependencies
    will be possible.

    .. doctest:: world_test_clone

        >>> from antidote import world, Service
        >>> from antidote.exceptions import DependencyNotFoundError
        >>> world.singletons.add("test", 1)
        >>> class MyService(Service):
        ...     pass
        >>> with world.test.clone():
        ...     # By default singletons are not propagated
        ...     world.get[int]("test")
        Traceback (most recent call last):
        ...
        DependencyNotFoundError: 'test'
        >>> with world.test.clone():
        ...     # But anything else will be accessible
        ...     world.get[MyService]()
        <MyService object ...>
        >>> # You can have the singletons if wish though:
        ... with world.test.clone(keep_singletons=True):
        ...     assert world.get[int]("test") == 1
        ...     # A clone is always frozen, its purpose is to test existing dependencies.
        ...     world.singletons.add("test", 10)
        Traceback (most recent call last):
        ...
        FrozenWorldError
        >>> with world.test.clone(keep_singletons=True):
        ...     # dependencies can also be overridden as many times as necessary
        ...     world.test.override.singleton("test", 9)
        ...     world.test.override.singleton("test", 10)
        ...     world.get[int]("test")
        10
        >>> # The original singleton is preserved
        ... world.get[int]("test")
        1

    Args:
        keep_singletons: Whether current singletons should be kept in the new world.
            Beware that the same objects will be propagated. Defaults to :py:obj:`False`.
        keep_scopes: Whether current dependency values within the existing scopes should
            be kept in the new world. Like :code:`keep_singletons`, the same objects will
            be propagated. Defaults to :py:obj:`False`.

    Returns:
        context manager within you can make your tests.

    """

    def build(c: RawContainer) -> RawContainer:
        return c.clone(keep_singletons=keep_singletons,
                       keep_scopes=keep_scopes)

    with state.override(build):
        yield


@API.public
@contextmanager
def new() -> Iterator[None]:
    """
    Creates a new container with the same kind of providers and scopes. So it doesn't
    have any dependencies defined, but any scope or provider added will be present.

    .. doctest:: world_test_new

        >>> from antidote import world
        >>> world.singletons.add("test", 1)
        >>> with world.test.new():
        ...     # Current world is empty
        ...     world.get[int]("test")
        Traceback (most recent call last):
        ...
        DependencyNotFoundError: 'test'
        >>> with world.test.new():
        ...     world.singletons.add("new", 2)
        >>> # Anything done within the context manager stays there.
        ... world.get[int]("new")
        Traceback (most recent call last):
        ...
        DependencyNotFoundError: 'test'

    """
    with state.override(lambda c: RawContainer.with_same_providers_and_scopes(c)):
        yield


###############################
# Utilities to test providers #
###############################

@API.public
@contextmanager
def empty() -> Iterator[None]:
    """
    Only used to test providers.

    Creates an empty container. No initial providers are set up. This is useful to test
    one or several providers in isolation. If you're not testing provider, consider use
    :py:func:`.new` instead.
    """
    with state.override(lambda _: RawContainer()):
        yield


@API.public
def maybe_provide_from(provider: RawProvider,
                       dependency: Hashable) -> Optional[DependencyValue]:
    """
    Only used to test providers.

    Utility function to test _providers that have not been registered in :py:mod:`.world`.
    The current :py:class:~.core.container.DependencyContainer` will be given as if it
    were registered. This allows to test exactly what has been returned by the provider.

    Args:
        provider: provider from which the dependency should be retrieved.
        dependency: dependency to retrieve.

    Returns:
        dependency instance as returned by the provider.
    """
    if provider.is_registered:
        raise RuntimeError("Method only intended to test provider that have not "
                           "been registered in world.")
    return provider.maybe_provide(dependency, state.current_container())
