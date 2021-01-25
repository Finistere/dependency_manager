import pytest

from antidote import Factory, Provide, Service, factory, implementation, inject, world
from antidote._implementation import validate_provided_class
from antidote._providers import (FactoryProvider, IndirectProvider,
                                 ServiceProvider)
from antidote.exceptions import DependencyInstantiationError


@pytest.fixture(autouse=True)
def test_world():
    with world.test.empty():
        world.provider(ServiceProvider)
        world.provider(FactoryProvider)
        world.provider(IndirectProvider)
        yield


class Interface:
    pass


def test_default_implementation():
    class A(Interface, Service):
        pass

    class B(Interface, Service):
        pass

    choice = 'a'

    @implementation(Interface)
    def choose():
        return dict(a=A, b=B)[choice]

    assert world.get(Interface @ choose) is world.get(A)
    choice = 'b'
    assert choose() is B
    assert world.get(Interface @ choose) is world.get(A)


@pytest.mark.parametrize('singleton,permanent',
                         [(True, True), (True, False), (False, True), (False, False)])
def test_implementation(singleton: bool, permanent: bool):
    choice = 'a'

    class A(Interface, Service):
        __antidote__ = Service.Conf(singleton=singleton)

    class B(Interface, Service):
        __antidote__ = Service.Conf(singleton=singleton)

    @implementation(Interface, permanent=permanent)
    def choose_service():
        return dict(a=A, b=B)[choice]

    dependency = Interface @ choose_service
    assert isinstance(world.get(dependency), A)
    assert (world.get(dependency) is world.get(A)) is singleton

    choice = 'b'
    assert choose_service() == B
    if permanent:
        assert isinstance(world.get(dependency), A)
        assert (world.get(dependency) is world.get(A)) is singleton
    else:
        assert isinstance(world.get(dependency), B)
        assert (world.get(dependency) is world.get(B)) is singleton


def test_implementation_with_service():
    x = object()

    class A(Interface, Service):
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    @implementation(Interface)
    def impl():
        return A._with_kwargs(test=x)

    a = world.get(Interface @ impl)
    assert isinstance(a, A)
    assert a.kwargs == dict(test=x)


def test_implementation_with_factory():
    x = object()

    class A(Interface):
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class BuildA(Factory):
        def __call__(self, **kwargs) -> A:
            return A(**kwargs)

    @implementation(Interface)
    def impl2():
        return A @ BuildA._with_kwargs(test=x)

    a = world.get(Interface @ impl2)
    assert isinstance(a, A)
    assert a.kwargs == dict(test=x)


def dummy_choose():
    class A(Interface):
        pass

    return A


@pytest.mark.parametrize('expectation,kwargs,func',
                         [
                             pytest.param(pytest.raises(TypeError, match='.*function.*'),
                                          dict(interface=Interface),
                                          object(),
                                          id='function'),
                             pytest.param(pytest.raises(TypeError, match='.*interface.*'),
                                          dict(interface=object()),
                                          dummy_choose,
                                          id='interface')
                         ] + [
                             pytest.param(pytest.raises(TypeError, match=f'.*{arg}.*'),
                                          {'interface': Interface, arg: object()},
                                          dummy_choose,
                                          id=arg)
                             for arg in ['permanent',
                                         'auto_provide',
                                         'dependencies',
                                         'use_names',
                                         'auto_provide']
                         ])
def test_invalid_implementation(expectation, kwargs: dict, func):
    with expectation:
        implementation(**kwargs)(func)


def test_invalid_implementation_return_type():
    class B:
        pass

    world.singletons.add(B, 1)

    with world.test.new():
        world.singletons.add(1, 1)

        @implementation(Interface)
        def choose():
            return 1

        world.get(1)
        with pytest.raises(DependencyInstantiationError):
            world.get(Interface @ choose)

    with world.test.new():
        world.singletons.add(B, 1)

        @implementation(Interface)
        def choose2():
            return B

        world.get(B)
        with pytest.raises(DependencyInstantiationError):
            world.get(Interface @ choose2)

    with world.test.new():
        class C(Service):
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        @implementation(Interface)
        def impl():
            return C._with_kwargs(test=1)

        world.get(C._with_kwargs(test=1))
        with pytest.raises(DependencyInstantiationError):
            world.get(Interface @ impl)

    with world.test.new():
        class D:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class BuildD(Factory):
            def __call__(self, **kwargs) -> D:
                return D(**kwargs)

        @implementation(Interface)
        def impl2():
            return D @ BuildD._with_kwargs(test=1)

        world.get(D @ BuildD._with_kwargs(test=1))
        with pytest.raises(DependencyInstantiationError):
            world.get(Interface @ impl2)


def test_invalid_implementation_dependency():
    class Interface:
        pass

    class A(Interface, Service):
        pass

    @implementation(Interface)
    def current_interface():
        return A

    with pytest.raises(ValueError, match=".*interface.*"):
        A @ current_interface


def test_getattr():
    class Interface:
        pass

    class A(Interface, Service):
        pass

    def current_interface():
        return A

    current_interface.hello = 'world'

    build = implementation(Interface)(current_interface)
    assert build.hello == 'world'

    build.new_hello = 'new_world'
    assert build.new_hello == 'new_world'


def test_validate_provided_class():
    class Interface:
        pass

    with pytest.raises(TypeError):
        validate_provided_class(object(), expected=Interface)

    class A(Interface, Service):
        pass

    class B(Service):
        pass

    validate_provided_class(A, expected=Interface)
    validate_provided_class(B, expected=B)
    with pytest.raises(TypeError):
        validate_provided_class(B, expected=Interface)

    validate_provided_class(A._with_kwargs(a=1), expected=Interface)
    validate_provided_class(B._with_kwargs(a=1), expected=B)
    with pytest.raises(TypeError):
        validate_provided_class(B._with_kwargs(a=1), expected=Interface)

    @implementation(Interface)
    def choose_a():
        return A

    @implementation(B)
    def choose_b():
        return B

    validate_provided_class(Interface @ choose_a, expected=Interface)
    validate_provided_class(B @ choose_b, expected=B)
    with pytest.raises(TypeError):
        validate_provided_class(B @ choose_b, expected=Interface)


def test_validate_provided_class_factory():
    class Interface:
        pass

    class A(Interface):
        pass

    class B:
        pass

    with world.test.new():
        @factory
        def build_a() -> A:
            return A()

        @factory
        def build_b() -> B:
            return B()

        validate_provided_class(A @ build_a, expected=Interface)
        validate_provided_class(B @ build_b, expected=B)
        with pytest.raises(TypeError):
            validate_provided_class(B @ build_b, expected=Interface)

    with world.test.new():
        class BuildA(Factory):
            def __call__(self, **kwargs) -> A:
                return A(**kwargs)

        class BuildB(Factory):
            def __call__(self, **kwargs) -> B:
                return B(**kwargs)

        validate_provided_class(A @ BuildA, expected=Interface)
        validate_provided_class(B @ BuildB, expected=B)
        with pytest.raises(TypeError):
            validate_provided_class(B @ BuildB, expected=Interface)

        validate_provided_class(A @ BuildA._with_kwargs(a=1), expected=Interface)
        validate_provided_class(B @ BuildB._with_kwargs(a=1), expected=B)
        with pytest.raises(TypeError):
            validate_provided_class(B @ BuildB._with_kwargs(a=1), expected=Interface)


def test_default_injection():
    class MyService(Service):
        pass

    class Interface:
        pass

    class A(Interface, Service):
        pass

    injected = None

    @implementation(Interface)
    def choose_a(s: Provide[MyService]):
        nonlocal injected
        injected = s
        return A

    assert world.get(Interface @ choose_a) is world.get(A)
    assert injected is world.get(MyService)


def test_double_injection():
    world.singletons.add('s', object())

    class Interface:
        pass

    class A(Interface, Service):
        pass

    injected = None

    @implementation(Interface)
    @inject(use_names=True)
    def choose_a(s):
        nonlocal injected
        injected = s
        return A

    assert world.get(Interface @ choose_a) is world.get(A)
    assert injected is world.get('s')
