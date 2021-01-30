from contextlib import contextmanager
from typing import Callable, Generic, Hashable, Iterator, Optional, TypeVar, cast

from ._provider import ProviderMeta, _FREEZE_ATTR_NAME
from .container import Container, DependencyValue, RawProvider
from .exceptions import DebugNotAvailableError
from .utils import DependencyDebug
from .._compatibility.typing import final
from .._internal import API
from .._internal.utils import debug_repr

T = TypeVar('T', bound=Hashable)
M = TypeVar('M', bound=Callable[..., object])


@API.public
def does_not_freeze(method: M) -> M:
    """
    Decorated method won't freeze when :py:func:`~antidote.world.freeze` is called. All
    others will, with the exceptions of base methods defined in :py:class`.Provider`.

    Beware that is must be the last decorator if you use multiple ones.
    """
    setattr(method, _FREEZE_ATTR_NAME, False)
    return method


@API.public
class Provider(RawProvider, Generic[T],
               metaclass=ProviderMeta,
               # reserved
               abstract=True):
    """
    Abstract Base class for a provider.

    Consider using :py:class:`~.StatelessProvider` if you do not have any state
    to keep.

    .. doctest:: core_Provider

        >>> from typing import Hashable, Optional
        >>> from antidote import world, Scope
        >>> from antidote.core import Provider, Container, \\
        ...     DependencyValue, does_not_freeze
        >>> @world.provider
        ... class SquareProvider(Provider[int]):
        ...     def __init__(self, registered: set = None):
        ...         super().__init__()
        ...         self._registered = registered or set()
        ...
        ...     def register_numbers(self, number: int):
        ...         self._assert_not_duplicate(number)
        ...         self._registered |= {number}
        ...
        ...     def exists(self, dependency: Hashable):
        ...         return isinstance(dependency, int) and dependency in self._registered
        ...
        ...     def provide(self, dependency: int, container: Container
        ...                 ) -> DependencyValue:
        ...         return DependencyValue(self._square(dependency),
        ...                                   scope=Scope.singleton())
        ...
        ...     # we don't want this method to fail when world freezes
        ...     # and it does not modify any state, so we're safe !
        ...     @does_not_freeze
        ...     def _square(self, n: int) -> int:
        ...         return n ** 2
        ...
        ...     def clone(self, keep_singletons_cache: bool) -> 'SquareProvider':
        ...         return SquareProvider(self._registered.copy())
        ...
        >>> # To modify your provider, retrieve it from world
        ... world.get[SquareProvider]().register_numbers(9)
        >>> world.get[SquareProvider]().register_numbers(7)
        >>> world.get[int](9)
        81
        >>> # If you freeze world, you cannot register any dependencies
        ... world.freeze()
        >>> from antidote.exceptions import FrozenWorldError
        >>> try:
        ...     world.get[SquareProvider]().register_numbers(10)
        ... except FrozenWorldError:
        ...     print("Frozen world !")
        Frozen world !
        >>> # But you can still retrieve previously defined ones
        ... world.get[int](9)
        81
        >>> # even if never called before
        ... world.get[int](7)
        49


    .. warning::
        This is most advanced feature of Antidote and allows you to extend Antidote's
        behavior. So be careful with it, it will impact the whole library. There are
        several rules to respect:

        1. Different providers MUST provide strictly different dependencies.
        2. You MUST NOT use :py:mod:`~antidote.world`. If you need a dependency, rely on
           the provided :py:class:`~.core.container.Container`.
        3. Methods will automatically freeze except those marked with the decorator
           :py:func:`~.does_not_freeze`. Methods changing dependency *definitions* MUST
           freeze, others SHOULD NOT.
        4. You may cache singletons by yourself, but you need to clean your cache when
           :py:meth:`~.clone` is called with :code:`keep_singletons_cache=False`.
    """
    __antidote__ = None  # reserved

    def clone(self, keep_singletons_cache: bool) -> 'Provider[T]':
        """
        If you have no internal state, consider implementing
        :py:class:`~.StatelessProvider` instead.

        Used by the different test utilities.

        Args:
            keep_singletons_cache: Whether cached singletons, if any, should be kept or
                discarded.

        Returns:
            A deep copy of the current provider. It should always be a new instance.
        """
        raise NotImplementedError()

    def exists(self, dependency: Hashable) -> bool:
        """
        Check whether dependency exists in the current provider. It is recommended to be
        relatively fast as this function will often be called for all _providers. Among
        others it is used to check for duplicates and ensure that it is providable.

        Args:
            dependency: Dependency to check.

        Returns:
            bool: Whether dependency has been registered in this provider or not.
        """
        raise NotImplementedError()

    def provide(self, dependency: T, container: Container) -> DependencyValue:
        """
        Method called by the :py:class:`~.core.container.Container` when
        searching for a dependency. Be sure that the dependency space of your
        _providers don't intersect ! This function will only be called if
        :py:meth:`.exists` succeeded on the :code:`dependency`.

        If you need to access other dependencies, you MUST use the provided
        :code:`container` argument and NEVER :py:mod:`~antidote.world`.

        It is always called within a thread-safe (locked) environment, so you
        don't need to worry about it. You also don't need to worry about
        handling singletons, the :py:class:`~.core.container.Container` will
        handle it for you.

        Be careful to be consistent with :py:meth:`.exists`.

        Args:
            dependency: The dependency to be provided by the provider. It will have passed
                :py:meth:`.exists`.
            container: current container which may use to retrieve other dependencies.

        Returns:
            The requested instance wrapped in a
            :py:class:`~.core.container.DependencyValue`. If the dependency is a
            singleton, you MUST specify it with :code:`singleton=True`.
        """
        raise NotImplementedError("Either implement provide()"
                                  "or override maybe_provide()")

    def debug(self, dependency: T) -> DependencyDebug:
        """
        Optional support for :py:mod:`.world.debug`. If not implemented, debug information
        will not be provided for dependencies.

        Args:
            dependency: The dependency for which debug information should be provided. It
                will have passed :py:meth:`.exists`.

        Returns:
            A short information text on the dependency, whether it's a singleton and
            everything that has been wired for the dependency and its respective
            dependencies if any.

        """
        raise DebugNotAvailableError("Either implement debug() or override maybe_debug()")

    def maybe_provide(self,
                      dependency: Hashable,
                      container: Container
                      ) -> Optional[DependencyValue]:
        """
        **Expert feature**

        :py:meth:`.maybe_provide` MUST be consistent with :py:meth:`.exists`. It should
        return

        Args:
            dependency: The dependency to be provided by the provider.
            container: current container which may use to retrieve other dependencies.

        Returns:
            The requested instance wrapped in a
            :py:class:`~.core.container.DependencyValue` if available or
            :py:obj:`None`. If the dependency is a singleton, you MUST specify it
            with :code:`singleton=True`.

        """
        if self.exists(dependency):
            return self.provide(cast(T, dependency), container)
        return None

    def maybe_debug(self, dependency: Hashable) -> Optional[DependencyDebug]:
        """
        **Expert feature**

        :py:meth:`.maybe_debug` MUST be consistent with :py:meth:`.exists`.

        Args:
            dependency: The dependency for which debug information should be provided. It
                will have passed :py:meth:`.exists`.

        Returns:
            A short information text on the dependency, whether it's a singleton and
            everything that has been wired for the dependency and its respective
            dependencies if any.

        """
        if self.exists(dependency):
            try:
                return self.debug(cast(T, dependency))
            except DebugNotAvailableError:
                import warnings
                warnings.warn(f"Debug information for {debug_repr(dependency)} "
                              f"not available in {type(self)}")
        return None

    @does_not_freeze
    @final
    def _assert_not_duplicate(self, dependency: Hashable) -> None:
        """
        To be used whenever registering new dependencies to check that a dependency has
        not been declared before.

        Args:
            dependency: Dependency to check

        Raises:
            DuplicateDependencyError
        """
        self._bound_container_raise_if_exists(dependency)

    @does_not_freeze
    @final
    @contextmanager
    def _container_lock(self) -> Iterator[None]:
        """
        Context manager ensuring thread-safety regarding dependency instantiation and
        declaration over all providers. Typically useful if you want to change some
        mutable state in your provider.

        """
        with self._bound_container_locked():
            yield


@API.public
class StatelessProvider(Provider[T], abstract=True):
    """
    Abstract stateless :py:class:`~.Provider` which
    implements :py:meth:`~.clone`.

    .. doctest:: core_StatelessProvider

        >>> from typing import Hashable, Optional
        >>> from antidote import world, Scope
        >>> from antidote.core import StatelessProvider, Container, DependencyValue
        >>> @world.provider
        ... class SquareProvider(StatelessProvider[int]):
        ...     def exists(self, dependency: Hashable) -> bool:
        ...         return isinstance(dependency, int)
        ...
        ...     def provide(self, dependency: int, container: Container
        ...                 ) -> Optional[DependencyValue]:
        ...         return DependencyValue(dependency ** 2, scope=Scope.singleton())
        >>> world.get(9)
        81
    """

    @final
    def clone(self, keep_singletons_cache: bool) -> 'StatelessProvider[T]':
        return type(self)()
