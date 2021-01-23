import pytest

from antidote import const, Constants, Wiring, world
from antidote._providers import LazyProvider, ServiceProvider
from antidote.core.exceptions import DependencyInstantiationError
from antidote.exceptions import DependencyNotFoundError


class A:
    pass


@pytest.fixture(autouse=True)
def test_world():
    with world.test.empty():
        world.provider(LazyProvider)
        world.provider(ServiceProvider)
        yield


def test_simple():
    class Config(Constants):
        A = const('a')
        B = const('b')

        def get(self, key):
            return key * 2

    assert world.get(Config.A) == 'aa'
    assert world.get(Config.B) == 'bb'

    conf = Config()
    assert conf.A == 'aa'
    assert conf.B == 'bb'


def test_default():
    a = object()
    b = object()

    class Config(Constants):
        # exists
        A = const('a')
        # default
        B = const('b', default=b)
        # nothing
        C = const('c')
        # different error
        D = const('d', default='x')

        def get(self, key):
            if key == 'd':
                raise Exception()
            return dict(a=a)[key]

    assert world.get(Config.A) is a
    assert world.get(Config.B) is b
    with pytest.raises(DependencyInstantiationError):
        world.get(Config.C)
    with pytest.raises(DependencyInstantiationError):
        world.get(Config.D)


@pytest.mark.parametrize('auto_cast, a, b, c', [
    pytest.param(True, 109, 3.14, '199', id='True'),
    pytest.param(False, '109', '3.14', 199, id='False'),
    pytest.param([str, int], 109, '3.14', '199', id='(str, int)'),
    pytest.param([float], '109', 3.14, 199, id='(float,)'),
])
def test_auto_cast(auto_cast, a, b, c):
    D = object()

    class Config(Constants):
        __antidote__ = Constants.Conf(auto_cast=auto_cast)

        A = const[int]('a')
        B = const[float]('b')
        C = const[str]('c')
        D = const[dict]('d')

        def get(self, key):
            if key == 'a':
                return '109'
            if key == 'b':
                return '3.14'
            if key == 'c':
                return 199
            if key == 'd':
                return D

    assert world.get(Config.A) == a
    assert world.get(Config.B) == b
    assert world.get(Config.C) == c
    assert world.get(Config.D) is D

    assert Config().A == a
    assert Config().B == b
    assert Config().C == c
    assert Config().D is D


def test_no_const():
    class Config(Constants):
        __antidote__ = Constants.Conf()
        A = 'a'

        def get(self, key):
            return key * 2

    with pytest.raises(DependencyNotFoundError):
        world.get(Config.A)

    conf = Config()
    assert conf.A == 'a'


def test_no_get_method():
    class Config(Constants):
        A = const('a')

    with pytest.raises(DependencyInstantiationError):
        world.get(Config.A)


def test_invalid_conf():
    with pytest.raises(TypeError, match=".*__antidote__.*"):
        class Config(Constants):
            __antidote__ = object()

            def get(self, key):
                pass


def test_no_subclass_of_constants():
    class Dummy(Constants):
        def get(self, key):
            pass

    with pytest.raises(TypeError, match=".*abstract.*"):
        class SubDummy(Dummy):
            def get(self, key):
                pass


@pytest.mark.parametrize('kwargs, expectation', [
    (dict(wiring=object()), pytest.raises(TypeError, match=".*wiring.*")),
    (dict(auto_cast=object()), pytest.raises(TypeError, match=".*auto_cast.*")),
    (dict(auto_cast=['1']), pytest.raises(TypeError, match=".*auto_cast.*")),
])
def test_conf_error(kwargs, expectation):
    with expectation:
        Constants.Conf(**kwargs)


@pytest.mark.parametrize('kwargs', [
    dict(wiring=Wiring(methods=['method'])),
    dict(auto_cast=frozenset((str,))),
])
def test_conf_copy(kwargs):
    conf = Constants.Conf().copy(**kwargs)
    for k, v in kwargs.items():
        assert getattr(conf, k) == v


def test_conf_repr():
    conf = Constants.Conf()
    assert "auto_cast" in repr(conf)
