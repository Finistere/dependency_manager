import inspect
from typing import Dict, Hashable, Optional, cast

from .._internal import API
from .._internal.utils import FinalImmutable, debug_repr
from ..core import Container, DependencyDebug, DependencyValue, Provider, Scope


@API.private
class Build(FinalImmutable):
    __slots__ = ('dependency', 'kwargs', '_hash')
    dependency: Hashable
    kwargs: Dict[str, object]
    _hash: int

    def __init__(self, dependency: Hashable, kwargs: Dict[str, object]) -> None:
        assert isinstance(kwargs, dict) and kwargs

        try:
            # Try most precise hash first
            _hash = hash((dependency, tuple(kwargs.items())))
        except TypeError:
            # If type error, return the best error-free hash possible
            _hash = hash((dependency, tuple(kwargs.keys())))

        super().__init__(dependency, kwargs, _hash)

    def __hash__(self) -> int:
        return self._hash

    def __repr__(self) -> str:
        return f"Build(dependency={self.dependency}, kwargs={self.kwargs})"

    def __antidote_debug_repr__(self) -> str:
        return f"{debug_repr(self.dependency)} with kwargs={self.kwargs}"

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, Build)
                and self._hash == other._hash
                and (self.dependency is other.dependency
                     or self.dependency == other.dependency)
                and self.kwargs == other.kwargs)  # noqa


@API.private
class ServiceProvider(Provider[Hashable]):
    def __init__(self) -> None:
        super().__init__()
        self.__services: Dict[Hashable, Optional[Scope]] = dict()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(services={list(self.__services.items())!r})"

    def exists(self, dependency: Hashable) -> bool:
        if isinstance(dependency, Build):
            return dependency.dependency in self.__services
        return dependency in self.__services

    def clone(self, keep_singletons_cache: bool) -> 'ServiceProvider':
        p = ServiceProvider()
        p.__services = self.__services.copy()
        return p

    def maybe_debug(self, build: Hashable) -> Optional[DependencyDebug]:
        klass = build.dependency if isinstance(build, Build) else build
        try:
            scope = self.__services[klass]
        except KeyError:
            return None
        return DependencyDebug(debug_repr(build),
                               scope=scope,
                               wired=[klass])

    def maybe_provide(self, build: Hashable, container: Container
                      ) -> Optional[DependencyValue]:
        dependency = build.dependency if isinstance(build, Build) else build
        try:
            scope = self.__services[dependency]
        except KeyError:
            return None

        klass = cast(type, dependency)
        if isinstance(build, Build) and build.kwargs:
            instance = klass(**build.kwargs)
        else:
            instance = klass()

        return DependencyValue(instance, scope=scope)

    def register(self,
                 klass: type,
                 *,
                 scope: Optional[Scope]
                 ) -> None:
        assert inspect.isclass(klass) \
               and (isinstance(scope, Scope) or scope is None)
        self._assert_not_duplicate(klass)
        self.__services[klass] = scope
