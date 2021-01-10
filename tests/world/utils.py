from typing import Hashable, Optional

from antidote.core import (Container, DependencyValue, Provider)


class DummyIntProvider(Provider[int]):
    def __init__(self):
        super().__init__()
        self.original = None

    def exists(self, dependency: Hashable) -> bool:
        return isinstance(dependency, int)

    def provide(self, dependency: int, container: Container
                ) -> Optional[DependencyValue]:
        return DependencyValue(dependency * 2)

    def clone(self, keep_singletons_cache: bool):
        p = DummyIntProvider()
        p.original = self
        return p
