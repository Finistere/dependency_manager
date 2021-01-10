"""
Utilities used by world, mostly for syntactic sugar.
"""
from typing import Any, Callable, cast, Hashable, Type, TypeVar, TYPE_CHECKING

from .meta import FinalMeta
from ..._compatibility.typing import final
from ..._internal import API
from ...core.container import RawContainer
from ...core.utils import Dependency

T = TypeVar('T')

if TYPE_CHECKING:
    from mypy_extensions import DefaultArg


@API.private
@final
class WorldGet(metaclass=FinalMeta):
    def __call__(self, dependency: Hashable) -> Any:
        from ..state import current_container
        return current_container().get(dependency)

    def __getitem__(self,
                    tpe: Type[T]
                    ) -> 'Callable[[DefaultArg(object)], T]':
        def f(dependency: Hashable = None) -> T:
            from ..state import current_container
            if dependency is None:
                dependency = tpe  # type: ignore
            return cast(T, current_container().get(dependency))

        return f


@API.private
@final
class WorldLazy(metaclass=FinalMeta):
    def __call__(self, dependency: Hashable) -> Dependency[Any]:
        return Dependency(dependency)

    def __getitem__(self,
                    tpe: Type[T]
                    ) -> 'Callable[[DefaultArg(object)], Dependency[T]]':
        def f(dependency: Hashable = None) -> Dependency[T]:
            if dependency is None:
                dependency = tpe  # type: ignore
            return Dependency(dependency)

        return f


@API.private
def new_container() -> RawContainer:
    """ default new container in Antidote """

    from ..._providers import (LazyProvider, ServiceProvider, TagProvider,
                               IndirectProvider, FactoryProvider)

    container = RawContainer()
    container.add_provider(FactoryProvider)
    container.add_provider(LazyProvider)
    container.add_provider(IndirectProvider)
    container.add_provider(TagProvider)
    container.add_provider(ServiceProvider)

    return container
