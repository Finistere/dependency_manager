import pytest

from antidote import Scope, world
from antidote._providers.lazy import Lazy, LazyProvider
from antidote.core import Container, DependencyValue


@pytest.fixture()
def lazy_provider():
    with world.test.empty():
        world.provider(LazyProvider)
        yield world.get(LazyProvider)


class Dummy(Lazy):
    def __init__(self, value, singleton=False):
        self.value = value
        self.scope = Scope.singleton() if singleton else None

    def lazy_get(self, container: Container) -> DependencyValue:
        return DependencyValue(container.get(self.value), scope=self.scope)


def test_lazy():
    with world.test.empty():
        x = object()
        world.singletons.add(x, object())
        lazy_provider = LazyProvider()

        assert world.test.maybe_provide_from(lazy_provider,
                                             Dummy(x)).unwrapped is world.get(x)
        for s in [True, False]:
            assert world.test.maybe_provide_from(
                lazy_provider,
                Dummy(x, singleton=s)).is_singleton() is s


def test_exists():
    lazy = LazyProvider()
    assert not lazy.exists(object())
    assert lazy.exists(Dummy('x'))


def test_copy(lazy_provider: LazyProvider):
    assert isinstance(lazy_provider.clone(True), LazyProvider)
    assert isinstance(lazy_provider.clone(False), LazyProvider)


def test_debug():
    with pytest.warns(UserWarning, match="(?i).*debug.*"):
        world.debug(Dummy(1))
