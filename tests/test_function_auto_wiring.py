import itertools
from typing import Callable

import pytest

from antidote import factory, implementation, world
from antidote._compatibility.typing import Protocol


class FactoryOutput:
    def __init__(self, a, b):
        self.a = a
        self.b = b


class A:
    pass


class B:
    pass


class FuncProtocol(Protocol):
    def __call__(self, a: A = None, b: B = None) -> FactoryOutput:
        pass


@pytest.fixture(autouse=True)
def new_world():
    with world.test.new():
        world.singletons.add({A: A(),
                              B: B(),
                              'a': object(),
                              'b': object(),
                              'x': object()})
        yield


class WiringTestCase:
    def __init__(self, func: FuncProtocol, has_type_hints: bool):
        self.func = func
        self.has_type_hints = has_type_hints
        self.expected_with_type_hints = None


def impl_interface(**kwargs):
    # Obviously Interface won't be implemented by anything, but
    # we're only checking the wiring.
    class Interface:
        pass

    return implementation(Interface, **kwargs)


@pytest.fixture(params=[
    pytest.param((f, tp), id=f"{f.__name__} - {tp}")
    for (f, tp) in itertools.product([factory, impl_interface],
                                     ['type_hints', None])
])
def builder(request):
    (wrapper, has_type_hints) = request.param

    def build(**kwargs):
        cls = type('FactoryOutputX', (FactoryOutput,), {})

        if has_type_hints:
            def func(a: A, b: B = None) -> cls:
                return cls(a, b)
        else:
            def func(a, b=None) -> cls:
                return cls(a, b)

        return WiringTestCase(wrapper(**kwargs)(func),
                              has_type_hints=has_type_hints is not None)

    return build


Builder = Callable[..., WiringTestCase]


def test_auto_wiring(builder: Builder):
    test_case = builder()
    if test_case.has_type_hints:
        out = test_case.func()
        assert out.a is world.get(A)
        assert out.b is world.get(B)
    else:
        with pytest.raises(TypeError):
            test_case.func()


def test_no_auto_wiring(builder: Builder):
    test_case = builder(auto_wire=False)

    with pytest.raises(TypeError):
        test_case.func()

    a = object()
    out = test_case.func(a)
    assert out.a is a
    assert out.b is None


def test_use_names(builder: Builder):
    # default
    test_case = builder()
    if test_case.has_type_hints:
        out = test_case.func()
        assert out.a is world.get(A)
        assert out.b is world.get(B)
    else:
        with pytest.raises(TypeError):
            test_case.func()

    # False
    test_case = builder(use_names=False)
    if test_case.has_type_hints:
        out = test_case.func()
        assert out.a is world.get(A)
        assert out.b is world.get(B)
    else:
        with pytest.raises(TypeError):
            test_case.func()

    # True
    test_case = builder(use_names=True)
    out = test_case.func()
    if test_case.has_type_hints:
        assert out.a is world.get(A)
        assert out.b is world.get(B)
    else:
        assert out.a is world.get('a')
        assert out.b is world.get('b')

    # ['a']
    test_case = builder(use_names=['a'])
    out = test_case.func()
    if test_case.has_type_hints:
        assert out.a is world.get(A)
        assert out.b is world.get(B)
    else:
        assert out.a is world.get('a')
        assert out.b is None


def test_use_type_hints(builder: Builder):
    # Default
    test_case = builder()
    if test_case.has_type_hints:
        out = test_case.func()
        assert out.a is world.get(A)
        assert out.b is world.get(B)
    else:
        with pytest.raises(TypeError):
            test_case.func()

    # True
    test_case = builder(use_type_hints=True)
    if test_case.has_type_hints:
        out = test_case.func()
        assert out.a is world.get(A)
        assert out.b is world.get(B)
    else:
        with pytest.raises(TypeError):
            test_case.func()

    # False
    test_case = builder(use_type_hints=False)
    with pytest.raises(TypeError):
        test_case.func()

    # ['a']
    test_case = builder(use_type_hints=['a'])
    if test_case.has_type_hints:
        out = test_case.func()
        assert out.a is world.get(A)
        assert out.b is None
    else:
        with pytest.raises(TypeError):
            test_case.func()

    # False with use_names
    test_case = builder(use_type_hints=False, use_names=True)
    out = test_case.func()
    assert out.a is world.get('a')
    assert out.b is world.get('b')

    # ['a'] with use_names
    test_case = builder(use_type_hints=['a'], use_names=True)
    out = test_case.func()
    if test_case.has_type_hints:
        assert out.a is world.get(A)
        assert out.b is world.get('b')
    else:
        assert out.a is world.get('a')
        assert out.b is world.get('b')


def test_dependencies_dict(builder: Builder):
    test_case = builder(dependencies=dict(), use_names=True)
    out = test_case.func()
    if test_case.has_type_hints:
        assert out.a is world.get(A)
        assert out.b is world.get(B)
    else:
        assert out.a is world.get('a')
        assert out.b is world.get('b')

    test_case = builder(dependencies=dict(a='x'), use_names=True)
    out = test_case.func()
    if test_case.has_type_hints:
        assert out.a is world.get('x')
        assert out.b is world.get(B)
    else:
        assert out.a is world.get('x')
        assert out.b is world.get('b')


def test_dependencies_seq(builder: Builder):
    test_case = builder(dependencies=[], use_names=True)
    out = test_case.func()
    if test_case.has_type_hints:
        assert out.a is world.get(A)
        assert out.b is world.get(B)
    else:
        assert out.a is world.get('a')
        assert out.b is world.get('b')

    test_case = builder(dependencies=['x'], use_names=True)
    out = test_case.func()
    if test_case.has_type_hints:
        assert out.a is world.get('x')
        assert out.b is world.get(B)
    else:
        assert out.a is world.get('x')
        assert out.b is world.get('b')

    # Skip last argument
    test_case = builder(dependencies=['x', None], use_names=True)
    out = test_case.func()
    if test_case.has_type_hints:
        assert out.a is world.get('x')
        assert out.b is world.get(B)
    else:
        assert out.a is world.get('x')
        assert out.b is world.get('b')

    # skip first argument
    test_case = builder(dependencies=[None, 'x'], use_names=True)
    out = test_case.func()
    if test_case.has_type_hints:
        assert out.a is world.get(A)
        assert out.b is world.get('x')
    else:
        assert out.a is world.get('a')
        assert out.b is world.get('x')


def test_dependencies_callable(builder: Builder):
    test_case = builder(dependencies=lambda arg: None, use_names=True)
    out = test_case.func()
    if test_case.has_type_hints:
        assert out.a is world.get(A)
        assert out.b is world.get(B)
    else:
        assert out.a is world.get('a')
        assert out.b is world.get('b')

    test_case = builder(dependencies=lambda arg: 'x' if arg.name == 'b' else None,
                        use_names=True)
    out = test_case.func()
    if test_case.has_type_hints:
        assert out.a is world.get(A)
        assert out.b is world.get('x')
    else:
        assert out.a is world.get('a')
        assert out.b is world.get('x')


def test_dependencies_str(builder: Builder):
    world.singletons.add({
        'conf:a': object(),
        'conf:b': object()
    })
    out = builder(dependencies='conf:{arg_name}').func()
    assert out.a is world.get('conf:a')
    assert out.b is world.get('conf:b')


@pytest.mark.parametrize('func', [factory, impl_interface])
@pytest.mark.parametrize('expectation,kwargs', [
    pytest.param(pytest.raises(TypeError, match=f".*{arg}.*"),
                 {arg: object()},
                 id=arg)
    for arg in ['auto_wire', 'dependencies', 'use_names', 'use_type_hints']
])
def test_invalid(func, expectation, kwargs):
    def f() -> FactoryOutput:
        pass

    with expectation:
        func(**kwargs)(f)
