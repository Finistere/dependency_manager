from typing import cast, Callable, Sequence

import pytest

from antidote import (Factory, factory, Service, Tag, Tagged,
                      world, service)
from antidote._providers import FactoryProvider, ServiceProvider


@pytest.fixture(autouse=True)
def new_world():
    with world.test.new():
        yield


class A:
    pass


class B:
    pass


class C:
    pass


Builder = Callable[[Sequence[Tag]], type]


@pytest.fixture(params=['factory', 'Factory', 'service', 'Service'])
def builder(request):
    tpe = request.param
    if tpe == 'factory':
        def f(tags):
            @factory(tags=tags)
            def build_a() -> A:
                return A()

            return A @ build_a
    elif tpe == 'Factory':
        def f(tags):
            class BFactory(Factory):
                __antidote__ = Factory.Conf(tags=tags)

                def __call__(self) -> B:
                    return B()

            return B @ BFactory
    elif tpe == 'service':
        def f(tags):
            service(C, tags=tags)
            return C
    elif tpe == 'Service':
        def f(tags):
            class X(Service):
                __antidote__ = Service.Conf(tags=tags)

            return X
    else:
        raise ValueError(tpe)
    return f


def test_tags(builder: Builder):
    tag = Tag()
    dep = builder([tag])

    tagged = cast(Tagged, world.get(Tagged.with_(tag)))

    assert len(tagged) == 1
    assert tagged.tag is tag
    assert set(tagged.values()) == {world.get(dep)}


def test_missing_tag_provider(builder: Builder):
    tag = Tag()

    with world.test.empty():
        world.provider(FactoryProvider)
        world.provider(ServiceProvider)

        with pytest.raises(RuntimeError, match=".*TagProvider.*"):
            builder([tag])


def test_multiple_tags(builder: Builder):
    tag = Tag()
    tag2 = Tag()
    tags = [tag, tag2]
    dep = builder(tags)

    for t in tags:
        tagged = cast(Tagged, world.get(Tagged.with_(t)))
        assert len(tagged) == 1
        assert tagged.tag is t
        assert set(tagged.values()) == {world.get(dep)}


@pytest.mark.parametrize('expectation, tags', [
    pytest.param(pytest.raises(TypeError, match=".*tags.*"), object(), id='object'),
    pytest.param(pytest.raises(TypeError, match=".*tags.*"), Tag(), id='single tag'),
    pytest.param(pytest.raises(TypeError, match=".*tags.*"), [1], id='list of int'),
    pytest.param(pytest.raises(TypeError, match=".*tags.*"), [Tag(), ''], id='mixed list')
])
def test_invalid_tags(expectation, tags, builder: Builder):
    with expectation:
        builder(tags)
