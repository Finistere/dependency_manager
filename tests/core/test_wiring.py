from typing import TYPE_CHECKING

import pytest

from antidote import Provide, inject, world
from antidote.core.exceptions import DoubleInjectionError
from antidote.core.wiring import Wiring, WithWiringMixin

if TYPE_CHECKING:
    pass


class Dummy:
    pass


@pytest.fixture(params=['Wiring', 'wire'])
def wire(request):
    kind = request.param
    if kind == 'Wiring':
        def wire(**kwargs):
            return Wiring(**kwargs).wire

        return wire
    else:
        from antidote import wire
        return wire


@pytest.fixture(autouse=True)
def new_world():
    with world.test.empty():
        world.singletons.add({'x': object(),
                              'xx': object(),
                              'y': object(),
                              'z': object(),
                              Dummy: Dummy()})
        yield


class Service:
    pass


class AnotherService:
    pass


@pytest.mark.parametrize('kwargs', [
    dict(dependencies=('x', 'y')),
    dict(dependencies=dict(x='x', y='y')),
    dict(use_names=['x', 'y']),
])
def test_no_strict_validation(wire, kwargs):
    @wire(**kwargs)
    class A:
        def f(self, x):
            return x

        def g(self, x, y):
            return x, y

    a = A()
    assert a.f() == world.get("x")
    assert a.g() == (world.get("x"), world.get("y"))


def test_no_strict_validation_auto_provide(wire):
    world.singletons.add({Service: Service(), AnotherService: AnotherService()})

    @wire(auto_provide=[Service, AnotherService])
    class A:
        def f(self, x: Service):
            return x

        def g(self, x: Service, y: AnotherService):
            return x, y

    a = A()
    assert a.f() == world.get(Service)
    assert a.g() == (world.get(Service), world.get(AnotherService))


def test_subclass_classmethod(wire):
    @wire(use_names=True)
    class Dummy:
        @classmethod
        def cls_method(cls, x):
            return cls, x

    assert (Dummy, world.get('x')) == Dummy.cls_method()

    class SubDummy(Dummy):
        pass

    assert (SubDummy, world.get('x')) == SubDummy.cls_method()


@pytest.mark.parametrize('kwargs, expectation', [
    (dict(methods=object()), pytest.raises(TypeError, match=".*method.*")),
    (dict(methods=[object()]), pytest.raises(TypeError, match="(?i).*method.*")),
    (dict(dependencies=object()), pytest.raises(TypeError, match=".*dependencies.*")),
    (dict(use_names=object()), pytest.raises(TypeError, match=".*use_names.*")),
    (dict(use_names=[object()]), pytest.raises(TypeError, match=".*use_names.*")),
    (dict(auto_provide=object()), pytest.raises(TypeError, match=".*auto_provide.*")),
    (dict(raise_on_double_injection=object()),
     pytest.raises(TypeError, match=".*raise_on_double_injection.*")),
])
def test_validation(wire, kwargs, expectation):
    with expectation:
        wire(**kwargs)


def test_iterable():
    w = Wiring(methods=iter(['method']),
               use_names=iter(['method']),
               auto_provide=iter([Service]))

    assert isinstance(w.methods, frozenset)
    assert w.methods == {'method'}
    assert isinstance(w.auto_provide, frozenset)
    assert w.auto_provide == {Service}
    assert isinstance(w.use_names, frozenset)
    assert w.use_names == {'method'}


def test_default_all_methods(wire):
    @wire()
    class A:
        def __init__(self, x: Provide[Dummy]):
            self.x = x

        def __call__(self, x: Provide[Dummy]):
            return x

        def method(self, x: Provide[Dummy]):
            return x

        @classmethod
        def klass(cls, x: Provide[Dummy]):
            return x

        @staticmethod
        def static(x: Provide[Dummy]):
            return x

        def _method(self, x: Provide[Dummy]):
            return x

        @classmethod
        def _klass(cls, x: Provide[Dummy]):
            return x

        @staticmethod
        def _static(x: Provide[Dummy]):
            return x

        def __method(self, x: Provide[Dummy]):
            return x

        @classmethod
        def __klass(cls, x: Provide[Dummy]):
            return x

        @staticmethod
        def __static(x: Provide[Dummy]):
            return x

    a = A()
    dummy = world.get(Dummy)
    assert a.x is dummy
    assert a() is dummy
    assert a.method() is dummy
    assert a.klass() is dummy
    assert a.static() is dummy
    assert a._method() is dummy
    assert a._klass() is dummy
    assert a._static() is dummy
    assert a._A__method() is dummy
    assert a._A__klass() is dummy
    assert a._A__static() is dummy


def test_methods(wire):
    @wire(methods=['f'], dependencies={'x': Dummy})
    class A:
        def f(self, x):
            return x

        def g(self, x):
            return x

    assert A().f() is world.get(Dummy)
    with pytest.raises(TypeError):
        A().g()

    with pytest.raises(AttributeError):
        @wire(methods=['f'])
        class A:
            pass


def test_double_injection(wire):
    @wire(methods=['f'])
    class A:
        @inject(use_names=True)  # use_names to force injection
        def f(self, x):
            return x

    assert A().f() is world.get('x')

    with pytest.raises(DoubleInjectionError):
        @wire(methods=['f'], raise_on_double_injection=True)
        class B:
            @inject(use_names=True)  # use_names to force injection
            def f(self, x):
                return x

    @wire()
    class C:
        @inject(use_names=True)  # use_names to force injection
        def f(self, x):
            return x

    assert C().f() is world.get('x')

    with pytest.raises(DoubleInjectionError):
        @wire(raise_on_double_injection=True)
        class D:
            @inject(use_names=True)  # use_names to force injection
            def f(self, x):
                return x


def test_invalid_methods(wire):
    with pytest.raises(TypeError, match='.*not_a_method.*'):
        @wire(methods=['not_a_method'],
              use_names=True)  # use_names to force injection
        class Dummy:
            not_a_method = 1


@pytest.fixture(params=['method', 'classmethod', 'staticmethod'])
def wired_method_builder(request):
    kind = request.param

    def build(wire, *, annotation=object):
        if kind == 'method':
            @wire
            class A:
                def f(self, x: annotation):
                    return x
        elif kind == 'classmethod':
            @wire
            class A:
                @classmethod
                def f(cls, x: annotation):
                    return x
        else:
            @wire
            class A:
                @staticmethod
                def f(x: annotation):
                    return x
        return A().f

    return build


def test_use_inject_annotation(wire, wired_method_builder):
    f = wired_method_builder(wire())
    with pytest.raises(TypeError):
        f()

    f = wired_method_builder(wire(), annotation=Provide[Dummy])
    assert f() is world.get(Dummy)


def test_dependencies(wire, wired_method_builder):
    f = wired_method_builder(wire(methods=['f'], dependencies=('y',)))
    assert f() is world.get('y')

    f = wired_method_builder(wire(methods=['f'], dependencies=dict(x='z')))
    assert f() is world.get('z')

    f = wired_method_builder(wire(methods=['f'], dependencies=dict(y='z')))
    with pytest.raises(TypeError):
        f()

    f = wired_method_builder(wire(methods=['f'], dependencies="{arg_name}"))
    assert f() is world.get('x')

    f = wired_method_builder(wire(methods=['f'], dependencies=lambda arg: arg.name * 2))
    assert f() is world.get('xx')


def test_use_names(wire, wired_method_builder):
    f = wired_method_builder(wire(methods=['f']))
    with pytest.raises(TypeError):
        f()

    f = wired_method_builder(wire(methods=['f'], use_names=False))
    with pytest.raises(TypeError):
        f()

    f = wired_method_builder(wire(methods=['f'], use_names=True))
    assert f() is world.get('x')

    f = wired_method_builder(wire(methods=['f'], use_names=['x']))
    assert f() is world.get('x')

    f = wired_method_builder(wire(methods=['f'], use_names=['y']))
    with pytest.raises(TypeError):
        f()


@pytest.mark.parametrize('annotation', [object, Dummy])
def test_wiring_auto_provide(wire, wired_method_builder, annotation):
    f = wired_method_builder(wire(methods=['f']),
                             annotation=annotation)
    with pytest.raises(TypeError):
        f()

    f = wired_method_builder(wire(methods=['f'], auto_provide=False),
                             annotation=annotation)
    with pytest.raises(TypeError):
        f()

    f = wired_method_builder(wire(methods=['f'], auto_provide=True),
                             annotation=annotation)
    if annotation is Dummy:
        assert f() is world.get(Dummy)
    else:
        with pytest.raises(TypeError):
            f()

    f = wired_method_builder(wire(methods=['f'], auto_provide=[Dummy]),
                             annotation=annotation)
    if annotation is Dummy:
        assert f() is world.get(Dummy)
    else:
        with pytest.raises(TypeError):
            f()

    class Unknown:
        pass

    f = wired_method_builder(wire(methods=['f'], auto_provide=[Unknown]),
                             annotation=annotation)
    with pytest.raises(TypeError):
        f()


def test_complex_wiring(wire):
    @wire(auto_provide=True,
          methods=['g'],
          use_names=['y'])
    class A:
        def f(self, x: Dummy, y=None):
            return x, y

        def g(self, x: Dummy, y=None):
            return x, y

    with pytest.raises(TypeError):
        A().f()

    assert A().g() == (world.get(Dummy), world.get("y"))


def test_class_static_methods(wire):
    @wire(methods=['static', 'klass'],
          use_names=True)  # use_names to force injection
    class Dummy:
        @staticmethod
        def static(x):
            pass

        @classmethod
        def klass(cls, x):
            pass

    assert isinstance(Dummy.__dict__['static'], staticmethod)
    assert isinstance(Dummy.__dict__['klass'], classmethod)


@pytest.mark.parametrize('kwargs', [
    dict(methods={'method', 'test'}),
    dict(dependencies="{arg_name}"),
    dict(use_names=True),
    dict(auto_provide=True),
    dict(auto_provide=True)
])
def test_copy(kwargs):
    wiring = Wiring(methods=['method'],
                    dependencies=dict(),
                    use_names=False,
                    auto_provide=False)
    copy = wiring.copy(**kwargs)
    for key, value in kwargs.items():
        assert getattr(copy, key) == value


class DummyConf(WithWiringMixin):
    def __init__(self, wiring=None):
        self.wiring = wiring

    def copy(self, wiring):
        return DummyConf(wiring)


@pytest.mark.parametrize('kwargs', [
    dict(methods={'method', 'test'}),
    dict(dependencies="{arg_name}"),
    dict(use_names=True),
    dict(auto_provide=True),
])
def test_with_wiring(kwargs):
    conf = DummyConf(Wiring(methods=['method'],
                            dependencies=dict(),
                            use_names=False,
                            auto_provide=False))
    copy = conf.with_wiring(**kwargs)
    for key, value in kwargs.items():
        assert getattr(copy.wiring, key) == value

    kwargs.setdefault('methods', {'method'})
    copy = DummyConf().with_wiring(**kwargs)
    for key, value in kwargs.items():
        assert getattr(copy.wiring, key) == value


def test_with_wiring_auto_provide():
    conf = DummyConf(Wiring())
    assert conf.wiring.auto_provide is False

    conf2 = conf.auto_provide()
    assert conf2.wiring.auto_provide is True
