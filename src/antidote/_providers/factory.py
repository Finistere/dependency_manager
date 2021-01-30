import inspect
from typing import Callable, Dict, Hashable, Optional, Union

from .service import Build
from .._internal import API
from .._internal.utils import FinalImmutable, SlotRecord, debug_repr
from ..core import (Container, Dependency, DependencyDebug, DependencyValue, Provider,
                    Scope)


@API.private
class FactoryProvider(Provider[Hashable]):
    def __init__(self) -> None:
        super().__init__()
        self.__factories: Dict[FactoryDependency, Factory] = dict()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(factories={list(self.__factories.keys())})"

    def clone(self, keep_singletons_cache: bool) -> 'FactoryProvider':
        p = FactoryProvider()
        if keep_singletons_cache:
            factories = {
                k: (f.copy() if f.dependency is not None else f)
                for k, f in self.__factories.items()
            }
        else:
            factories = {
                k: (f.copy(keep_function=False) if f.dependency is not None else f)
                for k, f in self.__factories.items()
            }
        p.__factories = factories
        return p

    def exists(self, dependency: Hashable) -> bool:
        # For now we don't support multiple factories for a single dependency. Neither
        # is sharing the dependency with another provider. Simply because I don't see a
        # use case where it would make sense.
        # Open for discussions though, create an issue if you a use case.
        if isinstance(dependency, Build):
            dependency = dependency.dependency
        return (isinstance(dependency, FactoryDependency)
                and dependency in self.__factories)

    def maybe_debug(self, build: Hashable) -> Optional[DependencyDebug]:
        dependency_factory = build.dependency if isinstance(build, Build) else build
        if not isinstance(dependency_factory, FactoryDependency):
            return None

        try:
            factory = self.__factories[dependency_factory]
        except KeyError:
            return None

        dependencies = []
        wired = []
        if factory.dependency is not None:
            dependencies.append(factory.dependency)
            if isinstance(factory.dependency, type) \
                    and inspect.isclass(factory.dependency):
                wired.append(factory.dependency.__call__)
        else:
            wired.append(factory.function)

        return DependencyDebug(debug_repr(build),
                               scope=factory.scope,
                               wired=wired,
                               dependencies=dependencies)

    def maybe_provide(self, build: Hashable, container: Container
                      ) -> Optional[DependencyValue]:
        dependency_factory = build.dependency if isinstance(build, Build) else build
        if not isinstance(dependency_factory, FactoryDependency):
            return None

        try:
            factory = self.__factories[dependency_factory]
        except KeyError:
            return None

        if factory.function is None:
            f = container.provide(factory.dependency)
            assert f.is_singleton(), "factory dependency is expected to be a singleton"
            factory.function = f.unwrapped

        instance = (factory.function(**build.kwargs)
                    if isinstance(build, Build) and build.kwargs
                    else factory.function())

        return DependencyValue(instance, scope=factory.scope)

    def register(self,
                 output: type,
                 *,
                 factory: Union[Callable[..., object], Dependency[Hashable]],
                 scope: Optional[Scope]
                 ) -> 'FactoryDependency':
        assert inspect.isclass(output) \
               and (callable(factory) or isinstance(factory, Dependency)) \
               and (isinstance(scope, Scope) or scope is None)
        factory_dependency = FactoryDependency(output, factory)
        self._assert_not_duplicate(factory_dependency)

        if isinstance(factory, Dependency):
            self.__factories[factory_dependency] = Factory(scope,
                                                           dependency=factory.unwrapped)
        else:
            self.__factories[factory_dependency] = Factory(scope,
                                                           function=factory)

        return factory_dependency


@API.private
class FactoryDependency(FinalImmutable):
    __slots__ = ('output', 'factory', '__hash')
    output: Hashable
    factory: object
    __hash: int

    def __init__(self, output: Hashable, factory: object):
        if isinstance(factory, Dependency):
            factory = factory.unwrapped
        super().__init__(output, factory, hash((output, factory)))

    def __repr__(self) -> str:
        return f"FactoryDependency({self})"

    def __antidote_debug_repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"{debug_repr(self.output)} @ {debug_repr(self.factory)}"

    # Custom hash & eq necessary to find duplicates
    def __hash__(self) -> int:
        return self.__hash

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, FactoryDependency)
                and self.__hash == other.__hash
                and (self.output is other.output
                     or self.output == other.output)
                and (self.factory is other.factory
                     or self.factory == other.factory))  # noqa


@API.private
class Factory(SlotRecord):
    __slots__ = ('scope', 'function', 'dependency')
    scope: Optional[Scope]
    function: Callable[..., object]
    dependency: Hashable

    def __init__(self,
                 scope: Optional[Scope],
                 function: Callable[..., object] = None,
                 dependency: Hashable = None):
        assert function is not None or dependency is not None
        super().__init__(scope, function, dependency)

    def copy(self, keep_function: bool = True) -> 'Factory':
        return Factory(self.scope,
                       self.function if keep_function else None,
                       self.dependency)
