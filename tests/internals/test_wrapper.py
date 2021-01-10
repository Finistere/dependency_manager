"""
Test only that the wrapper behaves nicely in all cases.
Injection itself is tested through inject.
"""
import inspect
from typing import Any, List, Tuple

import pytest

from antidote import world
from antidote._internal.wrapper import build_wrapper, Injection, InjectionBlueprint
from antidote.exceptions import DependencyNotFoundError

A = object()
B = object()
C = object()


@pytest.fixture(autouse=True, scope='module')
def empty_world():
    with world.test.empty():
        world.singletons.add('x', A)
        yield


def easy_wrap(func=None,
              arg_dependency: List[Tuple[str, bool, Any]] = tuple()):
    def wrapper(func):
        return build_wrapper(
            blueprint=InjectionBlueprint(tuple([
                Injection(arg_name, required, dependency)
                for arg_name, required, dependency in arg_dependency
            ])),
            wrapped=func
        )

    return func and wrapper(func) or wrapper


arg_self_x = [('self', True, None), ('x', True, 'x')]
arg_cls_x = [('cls', True, None), ('x', True, 'x')]
arg_x = [('x', True, 'x')]


class Dummy:
    @easy_wrap(arg_dependency=arg_self_x)
    def method(self, x):
        return self, x

    @easy_wrap(arg_dependency=arg_cls_x)
    @classmethod
    def class_before(cls, x):
        return cls, x

    @classmethod
    @easy_wrap(arg_dependency=arg_cls_x)
    def class_after(cls, x):
        return cls, x

    @easy_wrap(arg_dependency=arg_x)
    @staticmethod
    def static_before(x):
        return x

    @staticmethod
    @easy_wrap(arg_dependency=arg_x)
    def static_after(x):
        return x


class Dummy2:
    def method(self, x):
        return self, x

    @classmethod
    def class_method(cls, x):
        return cls, x

    @staticmethod
    def static(x):
        return x


Dummy2.method = easy_wrap(Dummy2.__dict__['method'], arg_self_x)
Dummy2.class_method = easy_wrap(Dummy2.__dict__['class_method'], arg_cls_x)
Dummy2.static = easy_wrap(Dummy2.__dict__['static'], arg_x)


@easy_wrap(arg_dependency=arg_x)
def f(x):
    return x


d = Dummy()
d2 = Dummy2()


@pytest.mark.parametrize(
    'expected, func',
    [
        pytest.param(A, f,
                     id='func'),

        pytest.param((B, A), Dummy.method,
                     id='method'),
        pytest.param((Dummy, A), Dummy.class_before,
                     id='classmethod before'),
        pytest.param((Dummy, A), Dummy.class_after,
                     id='classmethod after'),
        pytest.param(A, Dummy.static_before,
                     id='staticmethod before'),
        pytest.param(A, Dummy.static_after,
                     id='staticmethod after'),

        pytest.param((d, A), d.method,
                     id='instance method'),
        pytest.param((Dummy, A), d.class_before,
                     id='instance classmethod before'),
        pytest.param((Dummy, A), d.class_after,
                     id='instance classmethod after'),
        pytest.param(A, d.static_before,
                     id='instance staticmethod before'),
        pytest.param(A, d.static_after,
                     id='instance staticmethod after'),

        pytest.param((d2, A), d2.method,
                     id='post:instance method'),
        pytest.param((Dummy2, A), d2.class_method,
                     id='post:instance classmethod'),
        pytest.param(A, d2.static,
                     id='post:instance staticmethod'),

        pytest.param((B, A), Dummy2.method,
                     id='post:method'),
        pytest.param((Dummy2, A), Dummy2.class_method,
                     id='post:classmethod'),
        pytest.param(A, Dummy2.static,
                     id='post:staticmethod'),
    ]
)
def test_wrapper(expected, func):
    if expected == (B, A):
        assert expected == func(B, A)
        assert expected == func(B)
        assert (B, C) == func(B, C)
        assert (B, C) == func(B, x=C)
    else:
        assert expected == func(A)
        assert expected == func()

        if isinstance(expected, tuple):
            new_expected = (expected[0], C)
        else:
            new_expected = C

        assert new_expected == func(C)
        assert new_expected == func(x=C)


def test_classmethod_wrapping():
    def class_method(cls):
        pass

    class A:
        method = easy_wrap(classmethod(class_method))

    assert class_method == A.__dict__['method'].__func__
    assert A == A.method.__self__


def test_required_dependency_not_found():
    @easy_wrap(arg_dependency=[('x', True, 'unknown')])
    def f(x):
        return x

    with pytest.raises(DependencyNotFoundError):
        f()


def test_dependency_not_found():
    @easy_wrap(arg_dependency=[('x', False, 'unknown')])
    def f(x):
        return x

    with pytest.raises(TypeError):
        f()


def test_multiple_injections():
    xx = object()
    yy = object()
    zz = object()

    @easy_wrap(arg_dependency=[('x', True, 'xx'),
                               ('y', True, 'yy'),
                               ('z', False, 'zz')])
    def f(x, y, z=zz):
        return x, y, z

    world.singletons.add(dict(xx=xx, yy=yy))
    assert (xx, yy, zz) == f()
    assert (xx, A, zz) == f(y=A)
    assert (xx, yy, A) == f(z=A)
    assert (A, yy, zz) == f(x=A)
    assert (A, yy, B) == f(A, z=B)

    with pytest.raises(TypeError):
        f(A, x=A)


def g():
    pass


def g_with_annotations(x: int):
    pass


def g_with_defaults(x, y=3):
    pass


def g_with_kw_only(x, *, y):
    pass


class G:
    def method(self):
        pass

    def method_with_annotations(self, x: int):
        pass

    def method_with_defaults(self, x, y=3):
        pass

    def method_with_kw_only(self, x, *, y):
        pass

    @staticmethod
    def cls():
        pass

    @staticmethod
    def cls_with_annotations(cls, x: int):
        pass

    @staticmethod
    def cls_with_defaults(cls, x, y=3):
        pass

    @staticmethod
    def cls_with_kw_only(cls, x, *, y):
        pass

    @staticmethod
    def static():
        pass

    @staticmethod
    def static_with_annotations(x: int):
        pass

    @staticmethod
    def static_with_defaults(x, y=3):
        pass

    @staticmethod
    def static_with_kw_only(x, *, y):
        pass


@pytest.mark.parametrize(
    'original,wrapped',
    [
        pytest.param(g,
                     easy_wrap(g),
                     id='function'),
        pytest.param(g_with_annotations,
                     easy_wrap(g_with_annotations,
                               arg_dependency=[('x', True, None)]),
                     id='function:__annotations__'),
        pytest.param(g_with_defaults,
                     easy_wrap(g_with_defaults,
                               arg_dependency=[('x', True, None), ('y', False, None)]),
                     id='function:__defaults__'),
        pytest.param(g_with_kw_only,
                     easy_wrap(g_with_kw_only,
                               arg_dependency=[('x', True, None), ('y', True, None)]),
                     id='function:__kwdefaults__'),
        pytest.param(G.method,
                     easy_wrap(G.method),
                     id='method'),
        pytest.param(G.method_with_annotations,
                     easy_wrap(G.method_with_annotations,
                               arg_dependency=[('self', True, None),
                                               ('x', True, None)]),
                     id='method:__annotations__'),
        pytest.param(G.method_with_defaults,
                     easy_wrap(G.method_with_defaults,
                               arg_dependency=[('self', True, None),
                                               ('x', True, None),
                                               ('y', False, None)]),
                     id='method:__defaults__'),
        pytest.param(G.method_with_kw_only,
                     easy_wrap(G.method_with_kw_only,
                               arg_dependency=[('self', True, None),
                                               ('x', True, None),
                                               ('y', True, None)]),
                     id='method:__kwdefaults__'),
        pytest.param(G.cls,
                     easy_wrap(G.cls),
                     id='classmethod'),
        pytest.param(G.cls_with_annotations,
                     easy_wrap(G.cls_with_annotations,
                               arg_dependency=[('cls', True, None),
                                               ('x', True, None)]),
                     id='classmethod:__annotations__'),
        pytest.param(G.cls_with_defaults,
                     easy_wrap(G.cls_with_defaults,
                               arg_dependency=[('cls', True, None),
                                               ('x', True, None),
                                               ('y', False, None)]),
                     id='classmethod:__defaults__'),
        pytest.param(G.cls_with_kw_only,
                     easy_wrap(G.cls_with_kw_only,
                               arg_dependency=[('cls', True, None),
                                               ('x', True, None),
                                               ('y', True, None)]),
                     id='classmethod:__kwdefaults__'),
        pytest.param(G.static,
                     easy_wrap(G.static),
                     id='static'),
        pytest.param(G.static_with_annotations,
                     easy_wrap(G.static_with_annotations,
                               arg_dependency=[('x', True, None)]),
                     id='static:__annotations__'),
        pytest.param(G.static_with_defaults,
                     easy_wrap(G.static_with_defaults,
                               arg_dependency=[('x', True, None), ('y', False, None)]),
                     id='static:__defaults__'),
        pytest.param(G.static_with_kw_only,
                     easy_wrap(G.static_with_kw_only,
                               arg_dependency=[('x', True, None), ('y', True, None)]),
                     id='static:__kwdefaults__')
    ]
)
def test_wrapped_attributes(original, wrapped):
    assert original is wrapped.__wrapped__
    assert original.__module__ == wrapped.__module__
    assert original.__name__ == wrapped.__name__
    assert original.__qualname__ == wrapped.__qualname__
    assert original.__doc__ == wrapped.__doc__
    assert original.__annotations__ == wrapped.__annotations__
    assert original.__defaults__ == wrapped.__defaults__
    assert original.__kwdefaults__ == wrapped.__kwdefaults__

    try:
        func = original.__func__
    except AttributeError:
        with pytest.raises(AttributeError):
            wrapped.__func__
    else:
        assert func is wrapped.__func__

    try:
        func = original.__self__
    except AttributeError:
        with pytest.raises(AttributeError):
            wrapped.__self__
    else:
        assert func is wrapped.__self__

    assert inspect.signature(original) == inspect.signature(wrapped)


def test_custom_attributes():
    def f():
        pass

    f.attr = "test"
    f.another_attr = "another_attr"
    wrapped = easy_wrap(f)
    assert "test" == wrapped.attr

    wrapped.attr2 = "test2"
    assert "test2" == wrapped.attr2
    # After setting a new attribute, original ones should still be accessible.
    assert "test" == wrapped.attr

    wrapped.attr = "overridden test"
    assert "overridden test" == wrapped.attr

    # You should be able to remove new attributes
    del wrapped.attr2

    with pytest.raises(AttributeError):
        wrapped.attr2

    # but not existing ones
    with pytest.raises(AttributeError):
        del wrapped.another_attr
