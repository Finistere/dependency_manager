import pytest

from antidote import inject, world
from antidote.core.exceptions import DoubleInjectionError
from antidote.core.wiring import Wiring, WithWiringMixin


class Dummy:
    pass


@pytest.fixture(autouse=True)
def new_world():
    with world.test.empty():
        world.singletons.add({'x': object(),
                              'xx': object(),
                              'y': object(),
                              'z': object(),
                              Dummy: Dummy()})
        yield


@pytest.mark.parametrize('kwargs, expectation', [
    (dict(), pytest.raises(TypeError)),
    (dict(methods=[]), pytest.raises(ValueError, match=".*method.*")),
    (dict(attempt_methods=[]),
     pytest.raises(ValueError, match=".*attempt_methods.*")),
    (dict(methods=[], attempt_methods=[]),
     pytest.raises(ValueError, match=".*methods.*attempt_methods.*")),

    (dict(methods=1), pytest.raises(TypeError, match=".*method.*")),
    (dict(attempt_methods=1),
     pytest.raises(TypeError, match=".*attempt_methods.*")),
    (dict(methods=[1]), pytest.raises(ValueError, match="(?i).*method.*")),
    (dict(attempt_methods=[1]),
     pytest.raises(ValueError, match=".*attempt_methods.*")),

    (dict(methods=['f'], dependencies=1),
     pytest.raises(TypeError, match=".*dependencies.*")),
    (dict(methods=['f'], use_names=1), pytest.raises(TypeError, match=".*use_names.*")),
    (dict(methods=['f'], use_type_hints=1),
     pytest.raises(TypeError, match=".*use_type_hints.*")),
    (dict(methods=['f'], wire_super=1), pytest.raises(TypeError, match=".*wire_super.*")),
    (dict(methods=['f'], wire_super=['x']),
     pytest.raises(ValueError, match=".*wire_super.*")),
    (dict(attempt_methods=['f'], wire_super=['x']),
     pytest.raises(ValueError, match=".*wire_super.*"))
])
def test_validation(kwargs, expectation):
    with expectation:
        Wiring(**kwargs)


def test_init():
    w = Wiring(methods=iter(['method']), attempt_methods=iter(['attempt']),
               wire_super=iter(['method']), use_names=iter(['method']),
               use_type_hints=iter(['method']))

    assert isinstance(w.methods, frozenset)
    assert w.methods == {'method'}
    assert isinstance(w.attempt_methods, frozenset)
    assert w.attempt_methods == {'attempt'}
    assert isinstance(w.wire_super, frozenset)
    assert w.wire_super == {'method'}
    assert isinstance(w.use_names, frozenset)
    assert w.use_names == {'method'}
    assert isinstance(w.use_type_hints, frozenset)
    assert w.use_type_hints == {'method'}


def test_wiring_methods():
    wiring = Wiring(methods=['f'])

    @wiring.wire
    class A:
        def f(self, x: Dummy):
            return x

        def g(self, x: Dummy):
            return x

    assert A().f() is world.get(Dummy)
    with pytest.raises(TypeError):
        A().g()

    with pytest.raises(AttributeError):
        wiring = Wiring(methods=['f'])

        @wiring.wire
        class A:
            pass

    with pytest.raises(DoubleInjectionError):
        wiring = Wiring(methods=['f'])

        @wiring.wire
        class A:
            @inject
            def f(self, x: Dummy):
                return x


def test_wiring_super_methods():
    class A:
        def f(self, x: Dummy):
            return x

    with pytest.raises(AttributeError, match=".*'f'.*"):
        wiring = Wiring(methods=['f'])

        @wiring.wire
        class X(A):
            pass

    with pytest.raises(AttributeError, match=".*'f'.*"):
        wiring = Wiring(methods=['f'], wire_super=False)

        @wiring.wire
        class Y(A):
            pass

    b_wiring = Wiring(methods=['f'], wire_super=True)

    @b_wiring.wire
    class B(A):
        pass

    assert B().f() is world.get(Dummy)

    c_wiring = Wiring(methods=['f'], wire_super=['f'])

    @c_wiring.wire
    class C(A):
        pass

    assert C().f() is world.get(Dummy)

    d_wiring = Wiring(attempt_methods=['f'], wire_super=['f'])

    @d_wiring.wire
    class D(A):
        pass

    assert D().f() is world.get(Dummy)


def test_wiring_dependencies():
    a_wiring = Wiring(methods=['f'], dependencies=('y',))

    @a_wiring.wire
    class A:
        def f(self, x: Dummy):
            return x

    assert A().f() is world.get('y')

    b_wiring = Wiring(methods=['f'], dependencies=dict(x='z'))

    @b_wiring.wire
    class B:
        def f(self, x: Dummy):
            return x

    assert B().f() is world.get('z')

    c_wiring = Wiring(methods=['f'], dependencies="{arg_name}")

    @c_wiring.wire
    class C:
        def f(self, x: Dummy):
            return x

    assert C().f() is world.get('x')

    d_wiring = Wiring(methods=['f'], dependencies=lambda arg: arg.name * 2)

    @d_wiring.wire
    class D:
        def f(self, x: Dummy):
            return x

    assert D().f() is world.get('xx')


def test_wiring_use_names():
    a_wiring = Wiring(methods=['f'])

    @a_wiring.wire
    class A:
        def f(self, y):
            return y

    with pytest.raises(TypeError):
        A().f()

    b_wiring = Wiring(methods=['f'], use_names=False)

    @b_wiring.wire
    class B:
        def f(self, y):
            return y

    with pytest.raises(TypeError):
        B().f()

    c_wiring = Wiring(methods=['f'], use_names=True)

    @c_wiring.wire
    class C:
        def f(self, y):
            return y

    assert C().f() is world.get('y')

    d_wiring = Wiring(methods=['f'], use_names=['y'])

    @d_wiring.wire
    class D:
        def f(self, y):
            return y

    assert D().f() is world.get('y')


def test_wiring_use_type_hints():
    a_wiring = Wiring(methods=['f'])

    @a_wiring.wire
    class A:
        def f(self, y: Dummy):
            return y

    assert A().f() is world.get(Dummy)

    b_wiring = Wiring(methods=['f'], use_type_hints=False)

    @b_wiring.wire
    class B:
        def f(self, y: Dummy):
            return y

    with pytest.raises(TypeError):
        B().f()

    c_wiring = Wiring(methods=['f'], use_type_hints=True)

    @c_wiring.wire
    class C:
        def f(self, y: Dummy):
            return y

    assert C().f() is world.get(Dummy)

    d_wiring = Wiring(methods=['f'], use_type_hints=['y'])

    @d_wiring.wire
    class D:
        def f(self, y: Dummy):
            return y

    assert D().f() is world.get(Dummy)


def test_complex_wiring():
    wiring = Wiring(methods=['f', 'g'],
                    use_names=['x'],
                    wire_super=True)

    class A:
        def g(self, x, y=None):
            return x, y

    @wiring.wire
    class B(A):
        def f(self, x: Dummy):
            return x

    assert B().f() is world.get(Dummy)
    assert B().g() == (world.get('x'), None)


def test_wiring_static_class_method():
    a_wiring = Wiring(methods=['static', 'klass'])

    @a_wiring.wire
    class A:
        @staticmethod
        def static(x: Dummy):
            return x

        @classmethod
        def klass(cls, x: Dummy):
            return cls, x

    assert A.static() is world.get(Dummy)
    assert A.klass() == (A, world.get(Dummy))
    assert A().static() is world.get(Dummy)
    assert A().klass() == (A, world.get(Dummy))

    class B:
        @staticmethod
        def static(x: Dummy):
            return x

        @classmethod
        def klass(cls, x: Dummy):
            return cls, x

    c_wiring = Wiring(methods=['static', 'klass'], wire_super=True)

    @c_wiring.wire
    class C(B):
        pass

    assert C.static() is world.get(Dummy)
    assert C.klass() == (C, world.get(Dummy))
    assert C().static() is world.get(Dummy)
    assert C().klass() == (C, world.get(Dummy))


def test_attempt_methods():
    with pytest.raises(AttributeError, match=".*unknown_method.*"):
        wiring = Wiring(methods=['unknown_method'])

        @wiring.wire
        class X:
            pass

    a_wiring = Wiring(attempt_methods=['unknown_method'])

    @a_wiring.wire
    class A:
        pass

    b_wiring = Wiring(methods=['method'], attempt_methods=['maybe_method'])

    @b_wiring.wire
    class B:
        def method(self):
            pass

    with pytest.raises(AttributeError, match=".*method.*"):
        @b_wiring.wire
        class B2:
            def maybe_method(self):
                pass

    c_wiring = Wiring(attempt_methods=['method'])

    @c_wiring.wire
    class C:
        def method(self, d: Dummy):
            return d

    assert C().method() is world.get[Dummy]()

    @c_wiring.wire
    class C2:
        @inject  # shouldn't fail
        def method(self, d: Dummy):
            return d

    assert C().method() is world.get[Dummy]()


def test_unwrap_class_static_methods():
    wiring = Wiring(methods=['static', 'klass'],
                    use_names=True)  # use_names to force injection

    @wiring.wire
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
    dict(attempt_methods={'attempt_method', 'test'}),
    dict(dependencies="{arg_name}"),
    dict(use_names=True),
    dict(use_type_hints=True),
    dict(wire_super={'method'})
])
def test_copy(kwargs):
    wiring = Wiring(methods=['method'],
                    attempt_methods=['attempt_method'],
                    dependencies=dict(),
                    use_names=False,
                    use_type_hints=False,
                    wire_super=False)
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
    dict(attempt_methods={'attempt_method', 'test'}),
    dict(dependencies="{arg_name}"),
    dict(use_names=True),
    dict(use_type_hints=True),
    dict(wire_super={'method'})
])
def test_with_wiring(kwargs):
    conf = DummyConf(Wiring(methods=['method'],
                            attempt_methods=['attempt_method'],
                            dependencies=dict(),
                            use_names=False,
                            use_type_hints=False,
                            wire_super=False))
    copy = conf.with_wiring(**kwargs)
    for key, value in kwargs.items():
        assert getattr(copy.wiring, key) == value

    kwargs.setdefault('methods', {'method'})
    copy = DummyConf().with_wiring(**kwargs)
    for key, value in kwargs.items():
        assert getattr(copy.wiring, key) == value


def test_invalid_with_wiring():
    with pytest.raises(TypeError):
        DummyConf().with_wiring()


def test_invalid_methods():
    wiring = Wiring(methods=['not_a_method'],
                    use_names=True)  # use_names to force injection

    with pytest.raises(TypeError, match='.*not_a_method.*'):
        @wiring.wire
        class Dummy:
            not_a_method = 1
