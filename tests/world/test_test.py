from typing import Callable, Hashable, Optional

import pytest

from antidote import world
from antidote._providers import ServiceProvider
from antidote.core import (Container, DependencyValue, StatelessProvider)
from antidote.core.exceptions import FrozenWorldError
from antidote.exceptions import DependencyNotFoundError
from .utils import DummyIntProvider


@pytest.fixture(autouse=True)
def empty_world():
    with world.test.empty():
        yield


@pytest.mark.parametrize('context,keeps_singletons,strategy', [
    pytest.param(lambda: world.test.empty(),
                 False,
                 'empty',
                 id='empty'),
    pytest.param(lambda: world.test.new(),
                 False,
                 'new',
                 id='new'),
    pytest.param(lambda: world.test.clone(),
                 False,
                 'clone',
                 id='clone'),
    pytest.param(lambda: world.test.clone(keep_singletons=True),
                 True,
                 'clone',
                 id='clone-with-singletons')
])
def test_world(context: Callable, keeps_singletons: bool, strategy: str):
    class DummyFloatProvider(StatelessProvider[float]):
        def exists(self, dependency: Hashable) -> bool:
            return isinstance(dependency, float)

        def provide(self, dependency: float, container: Container
                    ) -> Optional[DependencyValue]:
            return DependencyValue(dependency ** 2)

    x = object()
    y = object()
    world.singletons.add("x", x)
    world.provider(DummyIntProvider)
    provider = world.get(DummyIntProvider)

    with context():
        if keeps_singletons:
            assert world.get('x') == x
        else:
            with pytest.raises(DependencyNotFoundError):
                world.get('x')

        if strategy == 'new':
            assert isinstance(world.get[DummyIntProvider](), DummyIntProvider)
            assert world.get(DummyIntProvider).original is None
        elif strategy == 'clone':
            assert isinstance(world.get(DummyIntProvider), DummyIntProvider)
            assert world.get(DummyIntProvider) is not provider
            assert world.get(DummyIntProvider).original is provider
        elif strategy == 'empty':
            with pytest.raises(DependencyNotFoundError):
                world.get(DummyIntProvider)
            with pytest.raises(DependencyNotFoundError):
                world.get(ServiceProvider)

        if strategy != 'clone':
            world.singletons.add("y", y)
            assert world.get('y') is y

            world.provider(DummyFloatProvider)
            assert world.get(1.2) == 1.2 ** 2

            s = world.scopes.new('dummy')
            world.scopes.reset(s)

    with pytest.raises(DependencyNotFoundError):
        world.get('y')

    with pytest.raises(DependencyNotFoundError):
        world.get(1.2)

    with pytest.raises(DependencyNotFoundError):
        world.get(DummyFloatProvider)


def test_clone_keep_singletons():
    world.singletons.add("singleton", 2)
    world.provider(DummyIntProvider)

    with world.test.clone(keep_singletons=True):
        assert world.get("singleton") == 2
        assert world.get(10) == 20

    with world.test.clone(keep_singletons=False):
        with pytest.raises(DependencyNotFoundError):
            world.get("singleton")
        assert world.get(10) == 20


@pytest.mark.parametrize('keep_singletons', [True, False])
@pytest.mark.parametrize('keep_scopes', [True, False])
def test_clone_restrictions(keep_singletons, keep_scopes):
    with world.test.clone(keep_singletons=keep_singletons,
                          keep_scopes=keep_scopes):
        with pytest.raises(FrozenWorldError):
            world.scopes.new("new scope")

        with pytest.raises(FrozenWorldError):
            world.provider(DummyIntProvider)

        with pytest.raises(FrozenWorldError):
            world.singletons.add('test', 1)


def test_deep_clone():
    world.singletons.add("test", 1)

    with world.test.clone(keep_singletons=True):
        with world.test.clone(keep_singletons=False):
            with pytest.raises(DependencyNotFoundError):
                world.get("test")


def test_empty():
    world.singletons.add("singleton", 2)

    with world.test.empty():
        world.singletons.add("a", 3)
        assert world.get("a") == 3
        with pytest.raises(DependencyNotFoundError):
            world.get("singleton")
        world.provider(DummyIntProvider)
        assert world.get(10) == 20
        with pytest.raises(DependencyNotFoundError):
            world.get(ServiceProvider)

    with pytest.raises(DependencyNotFoundError):
        world.get("a")

    with pytest.raises(DependencyNotFoundError):
        assert world.get(10)


def test_new():
    world.singletons.add("singleton", 2)
    world.provider(DummyIntProvider)
    assert world.get(10) == 20

    with world.test.new():
        world.singletons.add("a", 3)
        assert world.get("a") == 3
        with pytest.raises(DependencyNotFoundError):
            world.get("singleton")
        assert world.get(10) == 20

    with pytest.raises(DependencyNotFoundError):
        world.get("a")


def test_provide_from():
    provider = DummyIntProvider()
    assert world.test.maybe_provide_from(provider, 10) == DependencyValue(20)
    assert world.test.maybe_provide_from(provider, "1") is None

    world.provider(DummyIntProvider)
    with pytest.raises(RuntimeError):
        world.test.maybe_provide_from(world.get(DummyIntProvider), 10)
