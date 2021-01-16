from typing import Callable

import pytest

from antidote import world, Get, From, FromArgName
from antidote._compatibility.typing import Annotated
from antidote._providers import ServiceProvider
from antidote.core import (Dependency)
from antidote.core.exceptions import DuplicateDependencyError
from antidote.exceptions import DependencyNotFoundError, FrozenWorldError
from .utils import DummyIntProvider


@pytest.fixture(autouse=True)
def empty_world():
    with world.test.empty():
        yield


class A:
    pass


def test_singletons():
    world.singletons.add("singleton", 12342)
    assert world.get("singleton") == 12342

    world.singletons.add({
        "singleton2": 89,
        "singleton3": 123
    })
    assert world.get("singleton2") == 89
    assert world.get("singleton3") == 123


def test_invalid_singletons():
    with pytest.raises(TypeError):
        world.singletons.add(1)

    with pytest.raises(TypeError):
        world.singletons.add(dict(), 1)


def test_duplicate_singletons():
    world.singletons.add("singleton", 12342)

    with pytest.raises(DuplicateDependencyError, match=".*singleton.*12342.*"):
        world.singletons.add("singleton", 1)

    with pytest.raises(DuplicateDependencyError, match=".*singleton.*12342.*"):
        world.singletons.add({"singleton": 1})


def test_get():
    world.singletons.add("x", 1)
    assert 1 == world.get("x")

    with pytest.raises(DependencyNotFoundError):
        world.get("nothing")

    world.singletons.add(A, A())
    assert world.get[int]("x") == 1
    assert world.get[A]() is world.get(A)


@pytest.mark.parametrize('getter', [
    pytest.param(world.get, id='get'),
    pytest.param(world.get[A], id='get[A]'),
    pytest.param(lambda x: world.lazy(x).get(), id='lazy'),
    pytest.param(lambda x: world.lazy[A](x).get(), id='lazy[A]')
])
def test_annotation_support(getter: Callable[[object], object]):
    class Maker:
        def __rmatmul__(self, other):
            return 'maker'

    world.singletons.add({
        A: A(),
        'a': A(),
        'maker': A()
    })
    assert getter(Annotated[A, object()]) is world.get(A)
    assert getter(Annotated[A, Get('a')]) is world.get('a')  # noqa: F821
    assert getter(Annotated[A, From(Maker())]) is world.get('maker')

    with pytest.raises(TypeError):
        getter(Annotated[A, Get('a'), Get('a')])  # noqa: F821

    with pytest.raises(TypeError):
        getter(Annotated[A, FromArgName('{arg_name}')])  # noqa: F821


@pytest.mark.parametrize('getter', [
    pytest.param(lambda x, d: world.get(x, default=d), id='get'),
    pytest.param(lambda x, d: world.get[A](x, default=d), id='get[A]')
])
def test_default(getter: Callable[[object, object], object]):
    world.singletons.add(A, A())
    assert getter(A, 'default') is world.get(A)
    assert getter('a', 'default') == 'default'


def test_lazy():
    world.singletons.add({
        'x': object(),
        A: A()
    })

    lazy = world.lazy('x')
    assert isinstance(lazy, Dependency)
    assert lazy.unwrapped == 'x'
    assert lazy.get() == world.get('x')

    lazy = world.lazy[int]('x')
    assert isinstance(lazy, Dependency)
    assert lazy.unwrapped == 'x'
    assert lazy.get() == world.get('x')
    assert world.lazy[A]().get() is world.get(A)


def test_freeze():
    world.provider(ServiceProvider)
    factory = world.get(ServiceProvider)

    class Service:
        pass

    world.freeze()
    with pytest.raises(FrozenWorldError):
        world.singletons.add("test", "x")

    with pytest.raises(FrozenWorldError):
        factory.register(Service, scope=None)


def test_add_provider():
    world.provider(DummyIntProvider)
    assert world.get(10) == 20


def test_no_duplicate_provider():
    world.provider(DummyIntProvider)
    assert world.get(10) == 20

    with pytest.raises(ValueError, match=".*already exists.*"):
        world.provider(DummyIntProvider)


@pytest.mark.parametrize('p, expectation', [
    (object(), pytest.raises(TypeError, match=".*RawProvider.*")),
    (A, pytest.raises(TypeError, match=".*RawProvider.*"))
])
def test_invalid_add_provider(p, expectation):
    with expectation:
        world.provider(p)
