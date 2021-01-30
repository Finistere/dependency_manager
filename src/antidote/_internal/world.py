"""
Utilities used by world, mostly for syntactic sugar.
"""
from typing import Any, Callable, Hashable, TYPE_CHECKING, Type, TypeVar, Union, cast

from . import API
from .utils import Default
from .utils.meta import FinalMeta
from .._compatibility.typing import final
from ..core._annotations import extract_annotated_dependency
from ..core.container import RawContainer
from ..core.exceptions import DependencyNotFoundError
from ..core.utils import Dependency

T = TypeVar('T')

if TYPE_CHECKING:
    from mypy_extensions import DefaultArg, DefaultNamedArg


@API.private
@final
class WorldGet(metaclass=FinalMeta):
    def __call__(self, __dependency: Hashable, *, default: Any = Default.sentinel) -> Any:
        from .state import current_container
        dependency = extract_annotated_dependency(__dependency)
        try:
            return current_container().get(dependency)
        except DependencyNotFoundError:
            if default is not Default.sentinel:
                return default
            raise

    def __getitem__(self,
                    tpe: Type[T]
                    ) -> 'Callable[[DefaultArg(object), DefaultNamedArg(T, name="default")], T]':  # noqa F821,E501
        def f(__dependency: Hashable = None,
              *,
              default: Union[T, Default] = Default.sentinel) -> T:
            if __dependency is None:
                __dependency = tpe  # type: ignore
            return cast(T, self(__dependency, default=default))

        return f


@API.private
@final
class WorldLazy(metaclass=FinalMeta):
    def __call__(self, __dependency: Hashable) -> Dependency[Any]:
        return Dependency(__dependency)

    def __getitem__(self,
                    tpe: Type[T]
                    ) -> 'Callable[[DefaultArg(object)], Dependency[T]]':
        def f(__dependency: Hashable = None) -> Dependency[T]:
            if __dependency is None:
                __dependency = tpe  # type: ignore
            return Dependency(__dependency)

        return f


@API.private
def new_container() -> RawContainer:
    """ default new container in Antidote """

    from .._providers import (LazyProvider, ServiceProvider, TagProvider,
                              IndirectProvider, FactoryProvider)

    container = RawContainer()
    container.add_provider(FactoryProvider)
    container.add_provider(LazyProvider)
    container.add_provider(IndirectProvider)
    container.add_provider(TagProvider)
    container.add_provider(ServiceProvider)

    return container
