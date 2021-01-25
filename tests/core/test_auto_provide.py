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

    @auto_provide
    def g(z: Annotated[object, Get(Service)]):
        return z

    @auto_provide
    def h(y):
        return y

    assert f() is world.get(Service)
    assert g() is world.get(Service)

    with pytest.raises(TypeError):
        h()
