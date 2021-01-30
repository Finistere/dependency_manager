import pytest

from antidote import Get, auto_provide, world
from antidote._compatibility.typing import Annotated


def test_invalid_obj():
    with pytest.raises(TypeError):
        auto_provide(object())


class Service:
    pass


@pytest.fixture(autouse=True)
def current_world():
    with world.test.empty():
        world.singletons.add({Service: Service(), 'y': object()})
        yield


def test_function():
    @auto_provide
    def f(x: Service):
        return x

    @auto_provide()
    def f2(x: Service):
        return x

    @auto_provide
    def g(z: Annotated[object, Get(Service)]):
        return z

    @auto_provide
    def h(y):
        return y

    assert f() is world.get(Service)
    assert f2() is world.get(Service)
    assert g() is world.get(Service)

    with pytest.raises(TypeError):
        h()


def test_use_names():
    @auto_provide(use_names=True)
    def f(y):
        return y

    assert f() is world.get('y')

    @auto_provide(use_names=['y'])
    def g(y):
        return y

    assert g() is world.get('y')

    @auto_provide(use_names=False)
    def h(y):
        return y

    with pytest.raises(TypeError):
        h()


def test_dependencies():
    @auto_provide(dependencies=dict(y=Service))
    def f(y):
        return y

    assert f() is world.get(Service)

    @auto_provide(dependencies="{arg_name}")
    def g(y):
        return y

    assert g() is world.get('y')

    @auto_provide(dependencies=None)
    def h(y):
        return y

    with pytest.raises(TypeError):
        h()
