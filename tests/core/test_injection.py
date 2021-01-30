import itertools
from typing import Optional, Sequence, Union

import pytest

from antidote import From, FromArg, FromArgName, Get, ProvideArgName, world
from antidote._compatibility.typing import Annotated
from antidote.core.annotations import Provide
from antidote.core.injection import inject, validate_injection
from antidote.exceptions import DependencyNotFoundError, DoubleInjectionError

SENTINEL = object()


class DoesNotRaise:
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class Service:
    pass


class AnotherService:
    pass


@pytest.mark.parametrize('kwargs, expectation', [
    pytest.param(kwargs, expectation, id=str(kwargs))
    for kwargs, expectation in [
        (dict(), DoesNotRaise()),
        (dict(dependencies="{arg_name}"), DoesNotRaise()),
        (dict(dependencies=lambda arg: arg.name), DoesNotRaise()),
        (dict(dependencies=dict(x='x')), DoesNotRaise()),
        (dict(dependencies=['x']), DoesNotRaise()),
        (dict(use_names=True), DoesNotRaise()),
        (dict(use_names=['x']), DoesNotRaise()),
        (dict(auto_provide=True), DoesNotRaise()),
        (dict(dependencies=1),
         pytest.raises(TypeError, match=".*dependencies.*int.*")),
        (dict(use_names=1),
         pytest.raises(TypeError, match=".*use_names.*int.*")),
        (dict(use_names=[1]),
         pytest.raises(TypeError, match=".*use_names.*")),
        (dict(auto_provide=1),
         pytest.raises(TypeError, match=".*auto_provide.*int.*")),
        (dict(auto_provide=['x']),
         pytest.raises(TypeError, match=".*auto_provide.*x.*")),
    ]
])
def test_validate_injection(kwargs, expectation):
    with expectation:
        @inject(**kwargs)
        def f(x: Service):
            pass

    with expectation:
        validate_injection(**kwargs)


@pytest.fixture(params=[inject])
def injector(request):
    return request.param


def test_simple(injector):
    @injector
    def f(x: Provide[Service]):
        return x

    with world.test.empty():
        s = Service()
        world.singletons.add(Service, s)
        assert s == f()


no_SENTINEL_injection = [
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


@pytest.mark.parametrize('expected,kwargs', no_SENTINEL_injection)
def test_without_type_hints(injector, expected, kwargs):
    @injector(**kwargs)
    def f(first=SENTINEL, second=SENTINEL):
        return first, second

    class A:
        @injector(**kwargs)
        def method(self, first=SENTINEL, second=SENTINEL):
            return first, second

        @injector(**kwargs)
        @classmethod
        def class_method(cls, first=SENTINEL, second=SENTINEL):
            return first, second

        @injector(**kwargs)
        @staticmethod
        def static_method(first=SENTINEL, second=SENTINEL):
            return first, second

        @classmethod
        @injector(**kwargs)
        def klass(cls, first=SENTINEL, second=SENTINEL):
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
            world.get(d) if d is not None else SENTINEL
            for d in expected
        ))
        (first, second) = expected
        a, b = object(), object()

        assert (a, second) == f(first=a)
        assert (a, second) == A().method(first=a)
        assert (a, second) == A.class_method(first=a)
        assert (a, second) == A.static_method(first=a)
        assert (a, second) == A.klass(first=a)

        assert (first, b) == f(second=b)
        assert (first, b) == A().method(second=b)
        assert (first, b) == A.class_method(second=b)
        assert (first, b) == A.static_method(second=b)
        assert (first, b) == A.klass(second=b)

        assert (a, second) == f(a)
        assert (a, second) == A().method(a)
        assert (a, second) == A.class_method(a)
        assert (a, second) == A.static_method(a)
        assert (a, second) == A.klass(a)

        assert (a, b) == f(a, b)
        assert (a, b) == A().method(a, b)
        assert (a, b) == A.class_method(a, b)
        assert (a, b) == A.static_method(a, b)
        assert (a, b) == A.klass(a, b)


@pytest.mark.parametrize('expected,kwargs', no_SENTINEL_injection + [
    pytest.param((Service, AnotherService),
                 dict(auto_provide=True),
                 id='auto_provide:True'),
    pytest.param((Service, None),
                 dict(auto_provide=[Service]),
                 id='auto_provide:list-first'),
    pytest.param((Service, 'second'),
                 dict(auto_provide=[Service], use_names=True),
                 id='auto_provide:list-first+use_names=True'),
    pytest.param((None, AnotherService),
                 dict(auto_provide=[AnotherService]),
                 id='auto_provide:list-second'),
    pytest.param(('first', AnotherService),
                 dict(auto_provide=[AnotherService], use_names=True),
                 id='auto_provide:list-second+use_names=True'),
    pytest.param((None, None),
                 dict(auto_provide=False),
                 id='auto_provide:False'),
    pytest.param(('first', 'second'),
                 dict(auto_provide=False, use_names=True),
                 id='auto_provide:False+use_names=True'),
])
def test_with_auto_provide(injector, expected, kwargs):
    @injector(**kwargs)
    def f(first: Service = SENTINEL, second: AnotherService = SENTINEL):
        return first, second

    class A:
        @injector(**kwargs)
        def method(self, first: Service = SENTINEL, second: AnotherService = SENTINEL):
            return first, second

        @injector(**kwargs)
        @classmethod
        def class_method(cls, first: Service = SENTINEL,
                         second: AnotherService = SENTINEL):
            return first, second

        @injector(**kwargs)
        @staticmethod
        def static_method(first: Service = SENTINEL, second: AnotherService = SENTINEL):
            return first, second

        @classmethod
        @injector(**kwargs)
        def klass(cls, first: Service = SENTINEL, second: AnotherService = SENTINEL):
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
            world.get(d) if d is not None else SENTINEL
            for d in expected
        ))
        (first, second) = expected
        a, b = object(), object()

        assert (a, second) == f(first=a)
        assert (a, second) == A().method(first=a)
        assert (a, second) == A.class_method(first=a)
        assert (a, second) == A.static_method(first=a)
        assert (a, second) == A.klass(first=a)

        assert (first, b) == f(second=b)
        assert (first, b) == A().method(second=b)
        assert (first, b) == A.class_method(second=b)
        assert (first, b) == A.static_method(second=b)
        assert (first, b) == A.klass(second=b)

        assert (a, second) == f(a)
        assert (a, second) == A().method(a)
        assert (a, second) == A.class_method(a)
        assert (a, second) == A.static_method(a)
        assert (a, second) == A.klass(a)

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
                     dict(dependencies=dict(first=AnotherService)),
                     id='dependencies:dict-first'),
        pytest.param((Service, None),
                     dict(dependencies=(AnotherService,)),
                     id='dependencies:tuple-first'),
        pytest.param((Service, Service),
                     dict(dependencies=dict(second=Service)),
                     id='dependencies:dict-second'),
        pytest.param((Service, Service),
                     dict(dependencies=(None, Service)),
                     id='dependencies:tuple-second'),
        pytest.param((Service, 'second'),
                     dict(dependencies=lambda arg: arg.name),
                     id='dependencies:callable'),
        pytest.param((Service, AnotherService),
                     dict(dependencies=lambda arg: AnotherService),
                     id='dependencies:callable2'),
        pytest.param((Service, None),
                     dict(dependencies=lambda arg: None),
                     id='dependencies:callable3'),
        pytest.param((Service, 'second'),
                     dict(dependencies="{arg_name}"),
                     id='dependencies:str'),
        pytest.param((Service, 'prefix:second'),
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
        pytest.param((Service, AnotherService),
                     dict(auto_provide=True),
                     id='auto_provide:True'),
        pytest.param((Service, None),
                     dict(auto_provide=[Service]),
                     id='auto_provide:list-first'),
        pytest.param((Service, 'second'),
                     dict(auto_provide=[Service], use_names=True),
                     id='auto_provide:list-first+use_names=True'),
        pytest.param((Service, AnotherService),
                     dict(auto_provide=[AnotherService]),
                     id='auto_provide:list-second'),
        pytest.param((Service, AnotherService),
                     dict(auto_provide=[AnotherService], use_names=True),
                     id='auto_provide:list-second+use_names=True'),
        pytest.param((Service, None),
                     dict(auto_provide=False),
                     id='auto_provide:False'),
        pytest.param((Service, 'second'),
                     dict(auto_provide=False, use_names=True),
                     id='auto_provide:False+use_names=True'),
    ]
)
def test_with_provide(injector, expected, kwargs):
    @injector(**kwargs)
    def f(first: Provide[Service] = SENTINEL, second: AnotherService = SENTINEL):
        return first, second

    class A:
        @injector(**kwargs)
        def method(self,
                   first: Provide[Service] = SENTINEL,
                   second: AnotherService = SENTINEL):
            return first, second

        @injector(**kwargs)
        @classmethod
        def class_method(cls,
                         first: Provide[Service] = SENTINEL,
                         second: AnotherService = SENTINEL):
            return first, second

        @injector(**kwargs)
        @staticmethod
        def static_method(first: Provide[Service] = SENTINEL,
                          second: AnotherService = SENTINEL):
            return first, second

        @classmethod
        @injector(**kwargs)
        def klass(cls,
                  first: Provide[Service] = SENTINEL,
                  second: AnotherService = SENTINEL):
            return first, second

    with world.test.empty():
        world.singletons.add({Service: Service(),
                              AnotherService: AnotherService(),
                              'first': object(),
                              'second': object(),
                              'prefix:first': object(),
                              'prefix:second': object()})

        expected = tuple((
            world.get(d) if d is not None else SENTINEL
            for d in expected
        ))
        (first, second) = expected
        a, b = object(), object()

        assert (a, second) == f(first=a)
        assert (a, second) == A().method(first=a)
        assert (a, second) == A.class_method(first=a)
        assert (a, second) == A.static_method(first=a)
        assert (a, second) == A.klass(first=a)

        assert (first, b) == f(second=b)
        assert (first, b) == A().method(second=b)
        assert (first, b) == A.class_method(second=b)
        assert (first, b) == A.static_method(second=b)
        assert (first, b) == A.klass(second=b)

        assert (a, second) == f(a)
        assert (a, second) == A().method(a)
        assert (a, second) == A.class_method(a)
        assert (a, second) == A.static_method(a)
        assert (a, second) == A.klass(a)

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
                         + [Optional, Sequence]
                         # not a class / weird stuff
                         + [1, lambda x: x, object()])
def test_ignored_type_hints(injector, type_hint):
    @injector(auto_provide=True)
    def f(x: type_hint):
        pass

    with world.test.empty():
        world.singletons.add(type_hint, object())
        with pytest.raises(TypeError):
            f()


def test_none_optional_support(injector):
    class Dummy:
        pass

    @injector
    def f(x: Provide[Service] = None):
        return x

    @injector
    def g(x: Optional[Provide[Service]] = None):
        return x

    with world.test.empty():
        s = Service()
        world.singletons.add(Dummy, Dummy())
        world.singletons.add(Service, s)
        assert f() is s
        assert g() is s

    with world.test.empty():
        world.singletons.add(Dummy, Dummy())
        assert f() is None
        assert g() is None


@pytest.mark.parametrize('auto_provide', [True, False])
def test_none_optional_support_auto_provide(injector, auto_provide):
    class Dummy:
        pass

    @injector(auto_provide=auto_provide)
    def f(x: Service = None):
        return x

    @injector(auto_provide=auto_provide)
    def g(x: Optional[Service] = None):
        return x

    @injector(auto_provide=auto_provide)
    def h(x: Union[Service, Dummy]):
        pass

    with world.test.empty():
        s = Service()
        world.singletons.add(Dummy, Dummy())
        world.singletons.add(Service, s)
        expected = s if auto_provide else None
        assert f() is expected
        assert g() is expected
        with pytest.raises(TypeError):
            h()

    with world.test.empty():
        world.singletons.add(Dummy, Dummy())
        assert f() is None
        assert g() is None


def test_annotations(injector):
    class Dummy:
        pass

    with world.test.empty():
        @injector
        def custom_annotated(x: Annotated[Dummy, object()]):
            return x

        world.singletons.add(Dummy, Dummy())
        with pytest.raises(TypeError):
            custom_annotated()

    with world.test.empty():
        @injector
        def optional_annotated(x: Annotated[Dummy, object()] = None):
            return x

        world.singletons.add(Dummy, Dummy())
        assert optional_annotated() is None

    with world.test.empty():
        @injector
        def get(x: Annotated[Dummy, Get('dummy')]):  # noqa: F821
            return x

        world.singletons.add('dummy', Dummy())
        assert get() is world.get('dummy')

    with world.test.empty():
        @injector
        def optional_get(
                x: Optional[Annotated[Dummy, Get('dummy')]] = None):  # noqa: F821, E501
            return x

        world.singletons.add('dummy', Dummy())
        assert optional_get() is world.get('dummy')

    with world.test.empty():
        @injector
        def from_arg(x: Annotated[Dummy, FromArg(lambda arg: arg.name)]):
            return x

        world.singletons.add('x', Dummy())
        assert from_arg() is world.get('x')

    with world.test.empty():
        @injector
        def use_arg_name(x: ProvideArgName[Dummy]):
            return x

        world.singletons.add('x', Dummy())
        assert use_arg_name() is world.get('x')

    with world.test.empty():
        @injector
        def from_arg_name(x: Annotated[Dummy, FromArgName('service:{arg_name}')]):  # noqa: F722, E501
            return x

        world.singletons.add('service:x', Dummy())
        assert from_arg_name() is world.get('service:x')

    with world.test.empty():
        class Maker:
            def __rmatmul__(self, other):
                return 'dummy'

        @injector
        def get(x: Annotated[Dummy, From(Maker())]):
            return x

        world.singletons.add('dummy', Dummy())
        assert get() is world.get('dummy')


def test_multiple_antidote_annotations(injector):
    class Dummy:
        pass

    class Maker:
        def __rmatmul__(self, other):
            return 'dummy'

    annotations = [
        Get('dummy'),
        From(Maker()),
        FromArg(lambda arg: arg.name),
        FromArgName('service:{arg_name}'),
    ]
    for (a, b) in itertools.combinations(annotations, 2):
        with pytest.raises(TypeError):
            @injector
            def custom_annotated(x: Annotated[Dummy, a, b]):
                return x


@pytest.fixture(params=['function',
                        'method',
                        'classmethod',
                        'classmethod-after',
                        'staticmethod'])
def injected_method_with(request, injector):
    kind = request.param

    def builder(**kwargs):
        if kind == 'function':
            @injector(**kwargs)
            def f(x: Service):
                return x

            return f
        else:
            class Dummy:
                @injector(**kwargs)
                def method(self, x: Service):
                    return x

                @classmethod
                @injector(**kwargs)
                def class_method(cls, x: Service):
                    return x

                @injector(**kwargs)
                @classmethod
                def class_method_after(cls, x: Service):
                    return x

                @injector(**kwargs)
                @staticmethod
                def static_method(x: Service):
                    return x

            if kind == 'method':
                return Dummy().method
            elif kind == 'classmethod':
                return Dummy.class_method
            elif kind == 'classmethod-after':
                return Dummy.class_method_after
            elif kind == 'staticmethod':
                return Dummy.static_method
            else:
                raise RuntimeError()

    return builder


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
        pytest.param(pytest.raises(TypeError, match=".*auto_provide.*"),
                     dict(auto_provide=object()),
                     id="auto_provide:unsupported-type"),
        pytest.param(pytest.raises(TypeError, match=".*strict_validation.*"),
                     dict(strict_validation=object()),
                     id="auto_provide:unsupported-type")
    ]
)
def test_invalid_args(injected_method_with, expectation, kwargs):
    with expectation:
        injected_method_with(**kwargs)()

    with expectation:
        validate_injection(**kwargs)


@pytest.mark.parametrize(
    'expectation,kwargs',
    [
        pytest.param(pytest.raises(TypeError),
                     dict(),
                     id="nothing"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*Service.*"),
                     dict(dependencies=(Service,)),
                     id="dependencies:tuple"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*Service.*"),
                     dict(dependencies=dict(x=Service)),
                     id="dependencies:dict"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*Service.*"),
                     dict(dependencies=lambda arg: Service),
                     id="dependencies:callable"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*x.*"),
                     dict(dependencies="{arg_name}"),
                     id="dependencies:str"),
        pytest.param(pytest.raises(TypeError),
                     dict(use_names=False),
                     id="use_names:False"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*x.*"),
                     dict(use_names=True),
                     id="use_names:True"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*x.*"),
                     dict(use_names=['x']),
                     id="use_names:list"),
        pytest.param(pytest.raises(TypeError),
                     dict(auto_provide=False),
                     id="auto_provide:False"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*Service.*"),
                     dict(auto_provide=True),
                     id="auto_provide:True"),
        pytest.param(pytest.raises(DependencyNotFoundError, match=".*Service.*"),
                     dict(auto_provide=[Service]),
                     id="auto_provide:list")
    ]
)
def test_unknown_dependency(injected_method_with, expectation, kwargs):
    with expectation:
        injected_method_with(**kwargs)()


def test_unknown_provide(injector):
    @injector
    def f(x: Provide[Service]):
        return x

    with pytest.raises(DependencyNotFoundError):
        f()


@pytest.mark.parametrize(
    'expectation,kwargs',
    [

        pytest.param(pytest.raises(ValueError, match=".*y.*"),
                     dict(use_names=['y']),
                     id="use_names"),
        pytest.param(pytest.raises(ValueError, match=".*y.*"),
                     dict(use_names=['x', 'y']),
                     id="use_names2"),
        pytest.param(pytest.raises(ValueError, match=".*y.*"),
                     dict(auto_provide=[AnotherService]),
                     id="auto_provide"),
        pytest.param(pytest.raises(ValueError, match=".*y.*"),
                     dict(auto_provide=[Service, AnotherService]),
                     id="auto_provide2"),
        pytest.param(pytest.raises(ValueError),
                     dict(dependencies=(None, None)),
                     id="dependencies:too-much-arguments"),
        pytest.param(pytest.raises(ValueError, match=".*unknown.*"),
                     dict(dependencies=dict(unknown=DependencyNotFoundError)),
                     id="dependencies:unknown-dict-key"),
    ]
)
@pytest.mark.parametrize('strict', [True, False])
def test_strict_validation(injected_method_with, injector, expectation, kwargs, strict):
    kwargs['strict_validation'] = strict
    if strict:
        with expectation:
            injected_method_with(**kwargs)
    else:
        injected_method_with(**kwargs)(object())


@pytest.mark.parametrize(
    'expectation,kwargs',
    [
        pytest.param(pytest.raises(ValueError, match=".*self.*"),
                     dict(dependencies=dict(self='x')),
                     id="dependencies"),
        pytest.param(pytest.raises(ValueError, match=".*self.*"),
                     dict(use_names=('self',)),
                     id="use_names")
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


def test_no_injections():
    def f(x):
        return x

    # When nothing can be injected, the same function should be returned
    assert inject(f) is f


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
