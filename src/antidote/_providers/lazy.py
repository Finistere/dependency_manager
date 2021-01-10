from typing import Hashable

from .._compatibility.typing import final
from .._internal import API
from ..core import Container, DependencyDebug, DependencyValue, StatelessProvider
from ..core.exceptions import DebugNotAvailableError


@API.private
class Lazy:
    def debug_info(self) -> DependencyDebug:
        raise DebugNotAvailableError()

    def lazy_get(self, container: Container) -> DependencyValue:
        raise NotImplementedError()  # pragma: no cover


@API.private
@final
class LazyProvider(StatelessProvider[Lazy]):
    def exists(self, dependency: Hashable) -> bool:
        return isinstance(dependency, Lazy)

    def debug(self, dependency: Lazy) -> DependencyDebug:
        return dependency.debug_info()

    def provide(self, dependency: Lazy, container: Container
                ) -> DependencyValue:
        return dependency.lazy_get(container)
