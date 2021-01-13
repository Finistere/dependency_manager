from typing import Any, Callable, Type

import pytest

from antidote import Factory, factory, Tag, Wiring, world
from antidote._providers import (FactoryProvider, LazyProvider, ServiceProvider,
                                 TagProvider)


@pytest.fixture(autouse=True)
def test_world():
    with world.test.empty():
        world.provider(ServiceProvider)
        world.provider(FactoryProvider)
        world.provider(LazyProvider)
        world.provider(TagProvider)
        yield


class A:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class B:
    pass


class C:
    pass


def dummy() -> A:
    pass


@pytest.fixture(params=['function', 'class'])
def build(test_world, request):
    if request.param == 'function':
        @factory
        def build(**kwargs) -> A:
            return A(**kwargs)

        return build
    else:
        class ServiceFactory(Factory):
            def __call__(self, **kwargs) -> A:
                return A(**kwargs)

        return ServiceFactory


def test_simple(build: Type[Factory]):
    # working dependency
    assert isinstance(world.get(A @ build), A)
    assert world.get(A @ build) is world.get(A @ build)


def test_pass_through(build):
    if isinstance(build, type) and issubclass(build, Factory):
        build = build()

    assert isinstance(build(), A)

    x = object()
    a = build(x=x)
    assert a.kwargs == dict(x=x)


def test_custom_scope():
    dummy_scope = world.scopes.new('dummy')

    class Scoped:
        pass

    class ScopedF(Factory):
        __antidote__ = Factory.Conf(scope=dummy_scope)

        def __call__(self) -> Scoped:
            return Scoped()

    x = world.get(Scoped @ ScopedF)
    assert world.get(Scoped @ ScopedF) is x
    world.scopes.reset(dummy_scope)
    assert world.get(Scoped @ ScopedF) is not x

    @factory(scope=dummy_scope)
    def scoped_factory() -> Scoped:
        return Scoped()

    x = world.get(Scoped @ scoped_factory)
    assert world.get(Scoped @ scoped_factory) is x
    world.scopes.reset(dummy_scope)
    assert world.get(Scoped @ scoped_factory) is not x


def test_with_kwargs(build: Type[Factory]):
    x = object()
    a = world.get(A @ build.with_kwargs(x=x))
    assert a.kwargs == dict(x=x)

    with pytest.raises(ValueError, match=".*with_kwargs.*"):
        A @ build.with_kwargs()


def test_getattr():
    def build() -> A:
        return A()

    build.hello = 'world'

    build = factory(build)
    assert build.hello == 'world'

    build.new_hello = 'new_world'
    assert build.new_hello == 'new_world'


def test_invalid_dependency(build: Type[Factory]):
    with pytest.raises(ValueError, match="Unsupported output.*"):
        B @ build

    with pytest.raises(ValueError, match="Unsupported output.*"):
        B @ build.with_kwargs(x=1)


def test_missing_call():
    with pytest.raises(TypeError, match="__call__"):
        class ServiceFactory(Factory):
            pass


def test_missing_return_type_hint():
    with pytest.raises(ValueError, match=".*return type hint.*"):
        @factory
        def faulty_service_provider():
            return A()

    with pytest.raises(TypeError, match=".*return type hint.*"):
        @factory
        def faulty_service_provider2() -> Any:
            return A()

    with pytest.raises(ValueError, match=".*return type hint.*"):
        class FaultyServiceFactory(Factory):
            def __call__(self):
                return A()

    with pytest.raises(TypeError, match=".*return type hint.*"):
        class FaultyServiceFactory2(Factory):
            def __call__(self) -> Any:
                return A()


@pytest.mark.parametrize('expectation,kwargs,func',
                         [
                             pytest.param(pytest.raises(TypeError, match='.*function.*'),
                                          dict(),
                                          object(),
                                          id='function')
                         ] + [
                             pytest.param(pytest.raises(TypeError, match=f'.*{arg}.*'),
                                          {arg: object()},
                                          lambda: None,
                                          id=arg)
                             for arg in ['auto_wire',
                                         'singleton',
                                         'scope',
                                         'dependencies',
                                         'use_names',
                                         'use_type_hints',
                                         'tags']
                         ])
def test_invalid_factory_args(expectation, kwargs: dict, func: Callable[..., object]):
    with expectation:
        factory(**kwargs)(func)

    with expectation:
        factory(func, **kwargs)


def test_no_subclass_of_service():
    class Dummy(Factory):
        def __call__(self, *args, **kwargs) -> A:
            pass

    with pytest.raises(TypeError, match=".*abstract.*"):
        class SubDummy(Dummy):
            def __call__(self, *args, **kwargs) -> B:
                pass


def test_invalid_conf():
    with pytest.raises(TypeError, match=".*__antidote__.*"):
        class Dummy(Factory):
            __antidote__ = object()

            def __call__(self) -> A:
                pass


@pytest.mark.parametrize('expectation, kwargs', [
    pytest.param(pytest.raises(TypeError, match=f'.*{arg}.*'),
                 {arg: object()},
                 id=arg)
    for arg in ['wiring',
                'singleton',
                'scope',
                'tags',
                'public']
])
def test_invalid_conf_args(kwargs, expectation):
    with expectation:
        Factory.Conf(**kwargs)


@pytest.mark.parametrize('kwargs', [
    dict(singleton=False),
    dict(scope=None),
    dict(tags=(Tag(),)),
    dict(wiring=Wiring(methods=['method'])),
])
def test_conf_copy(kwargs):
    conf = Factory.Conf(singleton=True, tags=[]).copy(**kwargs)
    for k, v in kwargs.items():
        assert getattr(conf, k) == v


def test_invalid_copy():
    conf = Factory.Conf()
    with pytest.raises(TypeError, match=".*both.*"):
        conf.copy(singleton=False, scope=None)


def test_conf_repr():
    conf = Factory.Conf()
    assert "__init__" in repr(conf)
