import inspect
from typing import Callable, Dict, Hashable, Optional, Set, cast

from .._internal import API
from .._internal.utils import debug_repr, FinalImmutable
from ..core import Container, DependencyDebug, DependencyValue, Provider, Scope


@API.private
class IndirectProvider(Provider[Hashable]):
    def __init__(self) -> None:
        super().__init__()
        self.__implementations: Set[ImplementationDependency] = set()
        self.__implicits_registered: bool = False
        self.__indirect: Dict[Hashable, Hashable] = dict()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(implementations={self.__implementations}, " \
               f"indirect={self.__indirect}, implicits={self.__implicits_registered})"

    def clone(self, keep_singletons_cache: bool) -> 'IndirectProvider':
        p = IndirectProvider()
        p.__implicits_registered = self.__implicits_registered
        p.__implementations = self.__implementations.copy()
        p.__indirect = self.__indirect.copy()
        return p

    def exists(self, dependency: Hashable) -> bool:
        return dependency in self.__indirect or dependency in self.__implementations

    def maybe_debug(self, dependency: Hashable) -> Optional[DependencyDebug]:
        if dependency in self.__implementations:
            impl = cast(ImplementationDependency, dependency)
            if dependency in self.__indirect:
                target = self.__indirect[dependency]
            else:
                target = impl.implementation()  # type: ignore

            return DependencyDebug(debug_repr(dependency),
                                   scope=Scope.singleton() if impl.permanent else None,
                                   wired=[impl.implementation],  # type: ignore
                                   dependencies=[target])

        try:
            target = self.__indirect[dependency]
        except KeyError:
            pass
        else:
            repr_d = debug_repr(dependency)
            return DependencyDebug(f"Implicit: {repr_d} -> {debug_repr(target)}",
                                   scope=Scope.singleton(),
                                   dependencies=[target])
        return None

    def maybe_provide(self, dependency: Hashable, container: Container
                      ) -> Optional[DependencyValue]:
        try:
            target = self.__indirect[dependency]
        except KeyError:
            pass
        else:
            return container.provide(target)

        if dependency in self.__implementations:
            impl = cast(ImplementationDependency, dependency)
            # Mypy treats linker as a method
            target = impl.implementation()  # type: ignore
            if impl.permanent:
                self.__indirect[dependency] = target
            value = container.provide(target)
            return DependencyValue(
                value.unwrapped,
                scope=value.scope if impl.permanent else None
            )

        return None

    def register_implicits(self, dependency_to_target: Dict[Hashable, Hashable]) -> None:
        assert isinstance(dependency_to_target, dict)
        if self.__implicits_registered:
            raise RuntimeError("Implicits have already been defined once.")
        for dependency in dependency_to_target.keys():
            self._assert_not_duplicate(dependency)
        self.__implicits_registered = True
        self.__indirect.update(dependency_to_target)

    def register_implementation(self,
                                interface: type,
                                implementation: Callable[[], Hashable],
                                *,
                                permanent: bool
                                ) -> 'ImplementationDependency':
        assert callable(implementation) \
               and inspect.isclass(interface) \
               and isinstance(permanent, bool)
        impl = ImplementationDependency(interface, implementation, permanent)
        self._assert_not_duplicate(impl)
        self.__implementations.add(impl)
        return impl


@API.private
class ImplementationDependency(FinalImmutable):
    __slots__ = ('interface', 'implementation', 'permanent', '__hash')
    interface: type
    implementation: Callable[[], Hashable]
    permanent: bool
    __hash: int

    def __init__(self,
                 interface: Hashable,
                 implementation: Callable[[], Hashable],
                 permanent: bool):
        super().__init__(interface,
                         implementation,
                         permanent,
                         hash((interface, implementation)))

    def __repr__(self) -> str:
        return f"Implementation({self})"

    def __antidote_debug_repr__(self) -> str:
        if self.permanent:
            return f"Permanent implementation: {self}"
        else:
            return f"Implementation: {self}"

    def __str__(self) -> str:
        impl = self.implementation  # type: ignore
        return f"{debug_repr(self.interface)} @ {debug_repr(impl)}"

    # Custom hash & eq necessary to find duplicates
    def __hash__(self) -> int:
        return self.__hash

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, ImplementationDependency)
                and self.__hash == other.__hash
                and (self.interface is other.interface
                     or self.interface == other.interface)
                and (self.implementation is other.implementation  # type: ignore
                     or self.implementation == other.implementation)  # type: ignore
                )  # noqa
