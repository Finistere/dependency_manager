import itertools
from typing import Any, Callable, Optional, Tuple, Type

import pytest

from antidote import Constants, Factory, Implementation, Service, world
from antidote._compatibility.typing import Protocol
from antidote.core import Wiring


class Interface:
    pass


class FactoryOutput:
    pass


class FactoryOutput2:
    pass


class A:
    pass


class B:
    pass


@pytest.fixture(autouse=True)
def new_world():
    with world.test.new():
        world.singletons.add({A: A(),
                              B: B(),
                              'a': object(),
                              'b': object(),
                              'x': object(),
                              'y': object(),
                              'z': object()})
        yield


class DummyProtocol(Protocol):
    a: A
    b: B

    def __init__(self, a: A = None, b: B = None):
        pass

    def method(self, a: A = None, b: B = None) -> Tuple[A, B]:
        pass

    def method2(self, a=None, b=None) -> Tuple[Any, Any]:
        pass

    def method3(self, x=None, y=None, z=None) -> Tuple[Any, Any, Any]:
        pass


default_wiring = object()


def builder(cls: type, wiring_kind: str, subclass: bool = False):
    meta_kwargs = dict(abstract=True) if subclass else dict()
    if cls is Implementation:
        bases = (Interface, Implementation)
    else:
        bases = (cls,)

    def build(wiring: Wiring = None):
        class Dummy(*bases, **meta_kwargs):
            if wiring is not default_wiring:
                if wiring is not None:
                    if wiring_kind == 'Wiring':
                        __antidote__ = cls.Conf(wiring=wiring)
                    else:
                        __antidote__ = cls.Conf().with_wiring(**{
                            attr: getattr(wiring, attr)
                            for attr in Wiring.__slots__
                        })
                else:
                    __antidote__ = cls.Conf(wiring=None)

            def __init__(self, a: A = None, b: B = None):
                super().__init__()
                self.a = a
                self.b = b

            def method(self, a: A = None, b: B = None) -> Tuple[A, B]:
                return a, b

            def method2(self, a=None, b=None) -> Tuple[Any, Any]:
                return a, b

            def method3(self, x=None, y=None, z=None) -> Tuple[Any, Any, Any]:
                return x, y, z

            def __call__(self) -> FactoryOutput:  # for Factory
                pass

            def get(self):  # for Constants
                pass

        if subclass:
            class SubDummy(Dummy):
                def __call__(self) -> FactoryOutput2:  # for Factory
                    pass

            return SubDummy
        else:
            return Dummy

    return build


@pytest.fixture(params=[
    pytest.param((c, w), id=f"{c.__name__} - w")
    for (c, w) in itertools.product([Factory,
                                     Service,
                                     Constants,
                                     Implementation],
                                    ['with_wiring', 'Wiring'])
])
def class_builder(request):
    (cls, wiring_kind) = request.param
    return builder(cls, wiring_kind)


@pytest.fixture(params=[
    pytest.param((c, w), id=f"{c.__name__} - w")
    for (c, w) in itertools.product([Factory,
                                     Service,
                                     Constants],
                                    ['with_wiring', 'Wiring'])
])
def subclass_builder(request):
    (cls, wiring_kind) = request.param
    return builder(cls, wiring_kind, subclass=True)


F = Callable[[Optional[Wiring]], Type[DummyProtocol]]


def test_auto_wiring(class_builder: F):
    """__init__ should be injected by default."""
    dummy = class_builder(default_wiring)()
    assert dummy.a is world.get(A)
    assert dummy.b is world.get(B)


def test_no_wiring(class_builder: F):
    """__init__ should be injected by default."""
    dummy = class_builder(None)()
    assert dummy.a is None
    assert dummy.b is None


def test_method_wiring(class_builder: F):
    dummy = class_builder(Wiring(methods=('method',)))()
    assert dummy.a is None
    assert dummy.b is None

    (a, b) = dummy.method()
    assert a is world.get(A)
    assert b is world.get(B)


def test_attempt_methods(class_builder: F):
    with pytest.raises(AttributeError, match=".*unknown.*"):
        class_builder(Wiring(methods=('unknown',)))()

    with pytest.raises(AttributeError, match=".*unknown.*"):
        class_builder(Wiring(methods=['unknown'],
                             attempt_methods=['method']))()

    with world.test.clone(keep_singletons=True):
        class_builder(Wiring(attempt_methods=['unknown']))()

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(attempt_methods=('unknown',)))()
        assert dummy.a is None
        assert dummy.b is None

        (a, b) = dummy.method()
        assert a is None
        assert b is None

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(attempt_methods=('method',)))()
        assert dummy.a is None
        assert dummy.b is None

        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is world.get(B)


def test_super_wiring(subclass_builder: F):
    with pytest.raises(AttributeError, match=".*method.*"):
        # method() is not implemented by the subclass.
        subclass_builder(Wiring(methods=('method',)))()

    with world.test.clone(keep_singletons=True):
        sub_dummy = subclass_builder(Wiring(attempt_methods=('method',)))()
        assert sub_dummy.a is None
        assert sub_dummy.b is None

        (a, b) = sub_dummy.method()
        assert a is None
        assert b is None

    with world.test.clone(keep_singletons=True):
        sub_dummy = subclass_builder(Wiring(attempt_methods=('method',),
                                            wire_super=False))()
        assert sub_dummy.a is None
        assert sub_dummy.b is None

        (a, b) = sub_dummy.method()
        assert a is None
        assert b is None

    with world.test.clone(keep_singletons=True):
        sub_dummy = subclass_builder(Wiring(methods=('method', '__init__'),
                                            wire_super=True))()
        assert sub_dummy.a is world.get(A)
        assert sub_dummy.b is world.get(B)

        (a, b) = sub_dummy.method()
        assert a is world.get(A)
        assert b is world.get(B)

    with world.test.clone(keep_singletons=True):
        sub_dummy = subclass_builder(Wiring(methods=('method', '__init__'),
                                            wire_super=('method', '__init__')))()
        assert sub_dummy.a is world.get(A)
        assert sub_dummy.b is world.get(B)

        (a, b) = sub_dummy.method()
        assert a is world.get(A)
        assert b is world.get(B)

    with world.test.clone(keep_singletons=True):
        sub_dummy = subclass_builder(Wiring(attempt_methods=('method', '__init__'),
                                            wire_super=('__init__',)))()
        assert sub_dummy.a is world.get(A)
        assert sub_dummy.b is world.get(B)

        (a, b) = sub_dummy.method()
        assert a is None
        assert b is None

    with world.test.clone(keep_singletons=True):
        sub_dummy = subclass_builder(Wiring(attempt_methods=('method', '__init__'),
                                            wire_super=('method',)))()
        assert sub_dummy.a is None
        assert sub_dummy.b is None

        (a, b) = sub_dummy.method()
        assert a is world.get(A)
        assert b is world.get(B)

    with pytest.raises(ValueError, match=".*methods.*"):
        subclass_builder(Wiring(methods=('method', '__init__'),
                                wire_super=('__init__', 'unknown')))()


def test_use_names(class_builder: F):
    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method2',)))()
        (a, b) = dummy.method2()
        assert a is None
        assert b is None

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method2',), use_names=False))()
        (a, b) = dummy.method2()
        assert a is None
        assert b is None

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method2',), use_names=True))()
        (a, b) = dummy.method2()
        assert a is world.get('a')
        assert b is world.get('b')

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method2',), use_names=('a',)))()
        (a, b) = dummy.method2()
        assert a is world.get('a')
        assert b is None

    # Does not override type_hints
    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method',), use_names=True))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is world.get(B)


def test_use_type_hints(class_builder: F):
    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method',)))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is world.get(B)

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method',), use_type_hints=True))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is world.get(B)

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method',), use_type_hints=False))()
        (a, b) = dummy.method()
        assert a is None
        assert b is None

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method',), use_type_hints=('a',)))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is None

    # with use_names
    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method',),
                                     use_type_hints=False,
                                     use_names=True))()
        (a, b) = dummy.method()
        assert a is world.get('a')
        assert b is world.get('b')

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method',),
                                     use_type_hints=('a',),
                                     use_names=True))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is world.get('b')


def test_dependencies_dict(class_builder: F):
    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method', 'method2'),
                                     dependencies=dict()))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is world.get(B)

        (a, b) = dummy.method2()
        assert a is None
        assert b is None

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method', 'method2'),
                                     use_names=True,
                                     dependencies=dict(a='x', b='y')))()
        (a, b) = dummy.method()
        assert a is world.get('x')
        assert b is world.get('y')

        (a, b) = dummy.method2()
        assert a is world.get('x')
        assert b is world.get('y')

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method', 'method2'),
                                     use_names=True,
                                     dependencies=dict(b='y')))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is world.get('y')

        (a, b) = dummy.method2()
        assert a is world.get('a')
        assert b is world.get('y')


def test_dependencies_seq(class_builder: F):
    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method', 'method2'),
                                     dependencies=tuple()))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is world.get(B)

        (a, b) = dummy.method2()
        assert a is None
        assert b is None

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method', 'method2'),
                                     dependencies=[None, None]))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is world.get(B)

        (a, b) = dummy.method2()
        assert a is None
        assert b is None

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method', 'method2'),
                                     use_names=True,
                                     dependencies=['x', 'y']))()
        (a, b) = dummy.method()
        assert a is world.get('x')
        assert b is world.get('y')

        (a, b) = dummy.method2()
        assert a is world.get('x')
        assert b is world.get('y')

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method', 'method2'),
                                     use_names=True,
                                     dependencies=[None, 'y']))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is world.get('y')

        (a, b) = dummy.method2()
        assert a is world.get('a')
        assert b is world.get('y')

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method', 'method2'),
                                     use_names=True,
                                     dependencies=['x', None]))()
        (a, b) = dummy.method()
        assert a is world.get('x')
        assert b is world.get(B)

        (a, b) = dummy.method2()
        assert a is world.get('x')
        assert b is world.get('b')


def test_dependencies_callable(class_builder: F):
    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(
            methods=('method', 'method2'),
            dependencies=lambda arg: 'x' if arg.name == 'a' else 'y'))()
        (a, b) = dummy.method()
        assert a is world.get('x')
        assert b is world.get('y')

        (a, b) = dummy.method2()
        assert a is world.get('x')
        assert b is world.get('y')

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(
            methods=('method', 'method2'),
            use_names=True,
            dependencies=lambda arg: 'x' if arg.name == 'a' else None))()
        (a, b) = dummy.method()
        assert a is world.get('x')
        assert b is world.get(B)

        (a, b) = dummy.method2()
        assert a is world.get('x')
        assert b is world.get('b')

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method', 'method2'),
                                     use_names=True,
                                     dependencies=lambda arg: None))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is world.get(B)

        (a, b) = dummy.method2()
        assert a is world.get('a')
        assert b is world.get('b')


def test_dependencies_str(class_builder: F):
    with world.test.clone(keep_singletons=True):
        world.singletons.add({
            'conf:a': object(),
            'conf:b': object()
        })
        dummy = class_builder(Wiring(methods=('method', 'method2'),
                                     dependencies='conf:{arg_name}'))()
        (a, b) = dummy.method()
        assert a is world.get('conf:a')
        assert b is world.get('conf:b')

        (a, b) = dummy.method2()
        assert a is world.get('conf:a')
        assert b is world.get('conf:b')


def test_distinct_arguments(class_builder: F):
    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method', 'method3'),
                                     dependencies=['x', None, 'z']))()
        (a, b) = dummy.method()
        assert a is world.get('x')
        assert b is world.get(B)

        (x, y, z) = dummy.method3()
        assert x is world.get('x')
        assert y is None
        assert z is world.get('z')

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method', 'method3'),
                                     dependencies=dict(b='b', y='y')))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is world.get('b')

        (x, y, z) = dummy.method3()
        assert x is None
        assert y is world.get('y')
        assert z is None

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method', 'method3'),
                                     use_type_hints=['a']))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is None

        (x, y, z) = dummy.method3()
        assert x is None
        assert y is None
        assert z is None

    with world.test.clone(keep_singletons=True):
        dummy = class_builder(Wiring(methods=('method', 'method3'),
                                     use_names=['x']))()
        (a, b) = dummy.method()
        assert a is world.get(A)
        assert b is world.get(B)

        (x, y, z) = dummy.method3()
        assert x is world.get('x')
        assert y is None
        assert z is None
