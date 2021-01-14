import typing
from contextlib import contextmanager

import pytest

from antidote import world
from antidote._internal.argspec import Arguments
from antidote.core._injection import raw_inject
from antidote.core.injection import inject, validate_injection
from antidote.exceptions import DependencyNotFoundError, DoubleInjectionError


@contextmanager
def does_not_raise():
    yield


class Service:
    pass


class AnotherService:
    pass


@pytest.mark.parametrize('kwargs, expectation', [
    (dict(), does_not_raise()),
    (dict(dependencies="{arg_name}"), does_not_raise()),
    (dict(dependencies=lambda arg: arg.name), does_not_raise()),
    (dict(dependencies=dict(x='x')), does_not_raise()),
    (dict(dependencies=['x']), does_not_raise()),
    (dict(use_names=True), does_not_raise()),
    (dict(use_names=['x']), does_not_raise()),
    (dict(use_type_hints=True), does_not_raise()),
    (dict(use_type_hints=['x']), does_not_raise()),
    (dict(dependencies=1), pytest.raises(TypeError, match=".*dependencies.*int.*")),
    (dict(use_names=1), pytest.raises(TypeError, match=".*use_names.*int.*")),
    (dict(use_type_hints=1), pytest.raises(TypeError, match=".*use_type_hints.*int.*")),
])
def test_validate_injection(kwargs, expectation):
    print(expectation)
    with expectation:
        validate_injection(**kwargs)


@pytest.fixture(params=[raw_inject, inject])
def injector(request):
    return request.param


def test_simple(injector):
    @injector
    def f(x: Service):
        return x

    with world.test.empty():
        s = Service()
        world.singletons.add(Service, s)
        assert s == f()


@pytest.mark.parametrize(
    'expected,kwargs',
    [
        pytest.param((None, None),
                     dict(),
                     id='nothing'),
        pytest.param((Service, None),
                     dict(dependencies=dict(first=Service)),
                     id='dependencies:dict-first'),
        pytest.param((Service, None),
                     dict(dependencies=(Service,)),
                     id='dependencies:tuple-first'),
        pytest.param((None, Service),
                     dict(dependencies=dict(second=Service)),
                     id='dependencies:dict-second'),
        pytest.param((None, Service),
                     dict(dependencies=(None, Service)),
                     id='dependencies:tuple-second'),
        pytest.param(('first', 'second'),
                     dict(dependencies=lambda arg: arg.name),
                     id='dependencies:callable'),
        pytest.param((Service, Service),
                     dict(dependencies=lambda arg: Service),
                     id='dependencies:callable2'),
        pytest.param((None, None),
                     dict(dependencies=lambda s: None),
                     id='dependencies:callable3'),
        pytest.param(('first', 'second'),
                     dict(dependencies="{arg_name}"),
                     id='dependencies:str'),
        pytest.param(('prefix:first', 'prefix:second'),
                     dict(dependencies="prefix:{arg_name}"),
                     id='dependencies:str2'),
        pytest.param(('first', 'second'),
                     dict(use_names=True),
                     id='use_names:True'),
        pytest.param((None, None),
                     dict(use_names=False),
                     id='use_names:False'),
        pytest.param((None, 'second'),
                     dict(use_names=['second']),
                     id='use_names:list')
    ]
)
def test_without_type_hints(injector, expected, kwargs):
    default = object()

    @injector(**kwargs)
    def f(first=default, second=default):
        return first, second

    class A:
        @injector(**kwargs)
        def method(self, first=default, second=default):
            return first, second

        @injector(**kwargs)
        @classmethod
        def class_method(cls, first=default, second=default):
            return first, second

        @injector(**kwargs)
        @staticmethod
        def static_method(first=default, second=default):
            return first, second

        @classmethod
        @injector(**kwargs)
        def klass(cls, first=default, second=default):
            return first, second

    with world.test.empty():
        world.singletons.add({
            Service: Service(),
            AnotherService: AnotherService(),
            'first': object(),
            'second': object(),
            'prefix:first': object(),
            'prefix:second': object()
        })

        expected = tuple((
            world.get(d) if d is not None else default
            for d in expected
        ))
        assert expected == f()
        assert expected == A().method()
        assert expected == A.class_method()
        assert expected == A.static_method()
        assert expected == A.klass()

        a, b = object(), object()
        assert (a, b) == f(a, b)
        assert (a, b) == A().method(a, b)
        assert (a, b) == A.class_method(a, b)
        assert (a, b) == A.static_method(a, b)
        assert (a, b) == A.klass(a, b)


@pytest.mark.parametrize(
    'expected, kwargs',
    [
        pytest.param((Service, None),
                     dict(),
                     id='nothing'),
        pytest.param((Service, None),
                     dict(dependencies=dict(first=Service)),
                     id='dependencies:dict-first'),
        pytest.param((Service, None),
                     dict(dependencies=(Service,)),
                     id='dependencies:tuple-first'),
        pytest.param((Service, Service),
                     dict(dependencies=dict(second=Service)),
                     id='dependencies:dict-second'),
        pytest.param((Service, Service),
                     dict(dependencies=(None, Service)),
                     id='dependencies:tuple-second'),
        pytest.param(('first', 'second'),
                     dict(dependencies=lambda arg: arg.name),
                     id='dependencies:callable'),
        pytest.param((Service, Service),
                     dict(dependencies=lambda arg: Service),
                     id='dependencies:callable2'),
        pytest.param((Service, None),
                     dict(dependencies=lambda arg: None),
                     id='dependencies:callable3'),
        pytest.param(('first', 'second'),
                     dict(dependencies="{arg_name}"),
                     id='dependencies:str'),
        pytest.param(('prefix:first', 'prefix:second'),
                     dict(dependencies="prefix:{arg_name}"),
                     id='dependencies:str2'),
        pytest.param((Service, 'second'),
                     dict(use_names=True),
                     id='use_names:True'),
        pytest.param((Service, None),
                     dict(use_names=False),
                     id='use_names:False'),
        pytest.param((Service, None),
                     dict(use_names=['first']),
                     id='use_names:list-first'),
        pytest.param((Service, 'second'),
                     dict(use_names=['second']),
                     id='use_names:list-second'),
        pytest.param((Service, None),
                     dict(use_type_hints=True),
                     id='use_type_hints:True'),
        pytest.param((Service, None),
                     dict(use_type_hints=['first']),
                     id='use_type_hints:list-first'),
        pytest.param((Service, 'second'),
                     dict(use_type_hints=['first'], use_names=True),
                     id='use_type_hints:list-first+use_names=True'),
        pytest.param((None, None),
                     dict(use_type_hints=['second']),
                     id='use_type_hints:list-second'),
        pytest.param(('first', 'second'),
                     dict(use_type_hints=['second'], use_names=True),
                     id='use_type_hints:list-second+use_names=True'),
        pytest.param((None, None),
                     dict(use_type_hints=False),
                     id='use_type_hints:False'),
        pytest.param(('first', 'second'),
                     dict(use_type_hints=False, use_names=True),
                     id='use_type_hints:False+use_names=True'),
    ]
)
def test_with_type_hints(injector, expected, kwargs):
    default = object()

    @injector(**kwargs)
    def f(first: Service = default, second: str = default):
        return first, second

    class A:
        @injector(**kwargs)
        def method(self, first: Service = default, second: str = default):
            return first, second

        @injector(**kwargs)
        @classmethod
        def class_method(cls, first: Service = default, second: str = default):
            return first, second

        @injector(**kwargs)
        @staticmethod
        def static_method(first: Service = default, second: str = default):
            return first, second

        @classmethod
        @injector(**kwargs)
        def klass(cls, first: Service = default, second: str = default):
            return first, second

    with world.test.empty():
        world.singletons.add({Service: Service(),
                              AnotherService: AnotherService(),
                              'first': object(),
                              'second': object(),
                              'prefix:first': object(),
                              'prefix:second': object()})

        expected = tuple((
            world.get(d) if d is not None else default
            for d in expected
        ))
        assert expected == f()
        assert expected == A().method()
        assert expected == A.class_method()
        assert expected == A.static_method()
        assert expected == A.klass()

        a, b = object(), object()
        assert (a, b) == f(a, b)
        assert (a, b) == A().method(a, b)
        assert (a, b) == A.class_method(a, b)
        assert (a, b) == A.static_method(a, b)
        assert (a, b) == A.klass(a, b)


@pytest.mark.parametrize('type_hint',
                         # builtins
                         [str, int, float, set, list, dict, complex, type, tuple, bytes,
                          bytearray]
                         # typing
                         + [typing.Optional, typing.Sequence]
                         # not a class / weird stuff
                         + [1, lambda x: x, object()])
def test_ignored_type_hints(injector, type_hint):
    @injector
    def f(x: type_hint):
        pass

    with world.test.empty():
        world.singletons.add(type_hint, object())
        with pytest.raises(TypeError):
            f()


def test_arguments():
    def f(a, b):
        pass

    arguments = Arguments.from_callable(f)

    @raw_inject(arguments=arguments, use_names=True)
    def g(**kwargs):
        return kwargs

    with world.test.empty():
        world.singletons.add(dict(a=12, b=24))
        assert dict(a=12, b=24) == g()


def test_none_optional_support(injector):
    class Dummy:
        pass

    @injector
    def f(x: Service = None):
        return x

    @injector
    def g(x: typing.Optional[Service] = None):
        return x

    @injector
    def h(x: Dummy, y: typing.Optional[Service] = None):
        return y

    @injector
    def f2(x: typing.Union[Service, Dummy]):
        pass

    with world.test.empty():
        s = Service()
        world.singletons.add(Dummy, Dummy())
        world.singletons.add(Service, s)
        assert s == f()
        assert s == g()
        assert s == h()
        with pytest.raises(TypeError):
            f2()

    with world.test.empty():
        world.singletons.add(Dummy, Dummy())
        assert f() is None
        assert g() is None
        assert h() is None


@pytest.mark.parametrize(
    'expectation,kwargs',
    [
        pytest.param(pytest.raises(TypeError, match=".*dependencies.*"),
                     dict(dependencies=object()),
                     id="dependencies:unsupported-type"),
        pytest.param(pytest.raises(ValueError, match=".*dependencies.*"),
                     dict(dependencies="dummy"),
                     id="dependencies:missing-string-arg_name"),
        pytest.param(pytest.raises(TypeError),
                     dict(dependencies={1: 'x'}),
                     id="dependencies:invalid-key-type"),
        pytest.param(pytest.raises(TypeError, match=".*use_names.*"),
                     dict(use_names=object()),
                     id="use_names:unsupported-type"),
        pytest.param(pytest.raises(TypeError),
                     dict(use_names=[1]),
                     id="use_names:invalid-name-type"),
        pytest.param(pytest.raises(TypeError, match=".*use_type_hints.*"),
                     dict(use_type_hints=object()),
                     id="use_type_hints:unsupported-type"),
        pytest.param(pytest.raises(TypeError),
                     dict(use_type_hints=[1]),
                     id="use_type_hints:invalid-name-type")
    ]
)
def test_invalid_args(injector, expectation, kwargs):
    with expectation:
        @injector(**kwargs)
        def f(x):
            return x

        f()

    with expectation:
        class A:
            @injector(**kwargs)
            def method(self, x):
                return x

        A().method()

    with expectation:
        class A:
            @injector(**kwargs)
            @classmethod
            def classmethod(cls, x):
                return x

        A.classmethod()

    with expectation:
        class A:
            @injector(**kwargs)
            @staticmethod
            def staticmethod(x):
                return x

        A.staticmethod()

    with expectation:
        class A:
            @classmethod
            @injector(**kwargs)
            def classmethod(cls, x):
                return x

        A.classmethod()

    with expectation:
        validate_injection(**kwargs)


@pytest.mark.parametrize(
    'expectation,kwargs',
    [
        pytest.param(pytest.raises(TypeError),
                     dict(),
                     id="unknown-dependency"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*Service.*"),
                     dict(dependencies=(Service,)),
                     id="dependencies:unknown-dependency-tuple"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*Service.*"),
                     dict(dependencies=dict(x=Service)),
                     id="dependencies:unknown-dependency-dict"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*Service.*"),
                     dict(dependencies=lambda arg: Service),
                     id="dependencies:unknown-dependency-callable"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*unknown.*"),
                     dict(dependencies="unknown:{arg_name}"),
                     id="dependencies:unknown-dependency-str"),
        pytest.param(pytest.raises((ValueError, TypeError)),
                     dict(dependencies=(None, None)),
                     id="dependencies:too-much-arguments"),
        pytest.param(pytest.raises(ValueError, match=".*unknown.*"),
                     dict(dependencies=dict(unknown=DependencyNotFoundError)),
                     id="dependencies:unknown-argument-dict"),
        pytest.param(pytest.raises(TypeError),
                     dict(use_names=False),
                     id="use_names:unknown-dependency-False"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*x.*"),
                     dict(use_names=True),
                     id="use_names:unknown-dependency-True"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*x.*"),
                     dict(use_names=['x']),
                     id="use_names:unknown-dependency-list"),
        pytest.param(pytest.raises(ValueError, match=".*y.*"),
                     dict(use_names=['y']),
                     id="use_names:unknown-argument-list"),
        pytest.param(pytest.raises(ValueError, match=".*y.*"),
                     dict(use_names=['x', 'y']),
                     id="use_names:unknown-argument-list2"),
        pytest.param(pytest.raises(TypeError),
                     dict(use_names=[]),
                     id="use_names:empty"),
        pytest.param(pytest.raises(ValueError, match=".*y.*"),
                     dict(use_type_hints=['y']),
                     id="use_type_hints:unknown-arg"),
    ]
)
def test_invalid_call(injector, expectation, kwargs):
    with expectation:
        @injector(**kwargs)
        def f(x):
            return x

        f()

    with expectation:
        class A:
            @injector(**kwargs)
            def method(self, x):
                return x

        A().method()

    with expectation:
        class A:
            @injector(**kwargs)
            @classmethod
            def classmethod(cls, x):
                return x

        A.classmethod()

    with expectation:
        class A:
            @injector(**kwargs)
            @staticmethod
            def staticmethod(x):
                return x

        A.staticmethod()

    with expectation:
        class A:
            @classmethod
            @injector(**kwargs)
            def classmethod(cls, x):
                return x

        A.classmethod()


@pytest.mark.parametrize(
    'expectation,kwargs',
    [
        pytest.param(pytest.raises(ValueError, match=".*self.*"),
                     dict(dependencies=dict(self='x')),
                     id="dependencies"),
        pytest.param(pytest.raises(ValueError, match=".*self.*"),
                     dict(use_names=('self',)),
                     id="use_names"),
        pytest.param(pytest.raises(ValueError, match=".*self.*"),
                     dict(use_type_hints=('self',)),
                     id="use_type_hints"),
    ]
)
def test_cannot_inject_self(injector, expectation, kwargs):
    with expectation:
        class A:
            @injector(**kwargs)
            def method(self, x=None):
                return x

        A()

    with expectation:
        class A:
            @injector(**kwargs)
            @classmethod
            def classmethod(self, x=None):
                return x

        A()

    with expectation:
        class A:
            @classmethod
            @injector(**kwargs)
            def classmethod(self, x=None):
                return x

        A()


def test_invalid_type_hint(injector):
    @injector
    def f(x: Service):
        return x

    with pytest.raises(DependencyNotFoundError):
        f()


def test_no_injections():
    def f(x):
        return x

    # When nothing can be injected, the same function should be returned
    assert raw_inject(f) is f


def test_double_injection(injector):
    # When the function has already its arguments injected, the same function should
    # be returned
    with pytest.raises(DoubleInjectionError,
                       match=".*<locals>.f.*"):
        @injector
        @injector(use_names=True)
        def f(x):
            return x

    with pytest.raises(DoubleInjectionError,
                       match=".*StaticmethodA.*"):
        class StaticmethodA:
            @injector
            @staticmethod
            @injector(use_names=True)
            def f(x, y):
                pass

    with pytest.raises(DoubleInjectionError,
                       match=".*StaticmethodB.*"):
        class StaticmethodB:
            @injector
            @injector(use_names=True)
            @staticmethod
            def f(x, y):
                pass

    with pytest.raises(DoubleInjectionError,
                       match=".*ClassmethodA.*"):
        class ClassmethodA:
            @injector
            @classmethod
            @injector(use_names=True)
            def f(cls, x):
                pass

    with pytest.raises(DoubleInjectionError,
                       match=".*ClassmethodB.*"):
        class ClassmethodB:
            @injector
            @injector(use_names=True)
            @classmethod
            def f(cls, x):
                pass

    with pytest.raises(DoubleInjectionError,
                       match=".*Method.*"):
        class Method:
            @injector
            @injector(use_names=True)
            def f(self, x):
                pass


def test_invalid_inject(injector):
    with pytest.raises(TypeError):
        @injector
        class Dummy:
            pass

    with pytest.raises(TypeError):
        injector(1)


def test_static_class_method(injector):
    class Dummy:
        @injector(use_names=True)
        @staticmethod
        def static(x):
            pass

        @injector(use_names=True)
        @classmethod
        def klass(cls, x):
            pass

    assert isinstance(Dummy.__dict__['static'], staticmethod)
    assert isinstance(Dummy.__dict__['klass'], classmethod)
