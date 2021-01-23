from contextlib import contextmanager

import pytest

from antidote import service, Service, Tag, Wiring, world
from antidote._providers import ServiceProvider
from antidote.exceptions import DuplicateDependencyError


@contextmanager
def does_not_raise():
    yield


@pytest.fixture(autouse=True)
def test_world():
    with world.test.empty():
        world.provider(ServiceProvider)
        yield


def test_register_simple():
    @service
    class A:
        pass

    assert isinstance(world.get(A), A)
    # singleton by default
    assert world.get(A) is world.get(A)


def test_simple():
    class A(Service):
        pass

    assert isinstance(world.get(A), A)
    # singleton by default
    assert world.get(A) is world.get(A)


def test_register_singleton():
    @service(singleton=True)
    class Singleton:
        pass

    assert world.get(Singleton) is world.get(Singleton)

    @service(singleton=False)
    class NoScope:
        pass

    assert world.get(NoScope) != world.get(NoScope)


def test_singleton():
    class Singleton(Service):
        __antidote__ = Service.Conf(singleton=True)

    assert world.get(Singleton) is world.get(Singleton)

    class NoScope(Service):
        __antidote__ = Service.Conf(singleton=False)

    assert world.get(NoScope) != world.get(NoScope)


def test_custom_scope():
    dummy_scope = world.scopes.new('dummy')

    class Scoped(Service):
        __antidote__ = Service.Conf(scope=dummy_scope)

    my_service = world.get(Scoped)
    assert world.get(Scoped) is my_service
    world.scopes.reset(dummy_scope)
    assert world.get(Scoped) is not my_service

    @service(scope=dummy_scope)
    class Scoped:
        pass

    my_service = world.get(Scoped)
    assert world.get(Scoped) is my_service
    world.scopes.reset(dummy_scope)
    assert world.get(Scoped) is not my_service


def test_duplicate_registration():
    with pytest.raises(DuplicateDependencyError):
        @service
        class Dummy(Service):
            pass


@pytest.mark.parametrize('cls', ['test', object(), lambda: None])
def test_invalid_class(cls):
    with pytest.raises(TypeError):
        service(cls)


@pytest.mark.parametrize(
    'kwargs,expectation',
    [
        (dict(tags=object()), pytest.raises(TypeError, match=".*tags.*")),
        (dict(tags=['test']), pytest.raises(TypeError, match=".*tags.*")),
        (dict(singleton=object()), pytest.raises(TypeError, match=".*singleton.*")),
        (dict(scope=object()), pytest.raises(TypeError, match=".*scope.*")),
    ]
)
def test_invalid_service_args(kwargs, expectation):
    with expectation:
        @service(**kwargs)
        class Dummy:
            method = None


def test_not_tags():
    with world.test.empty():
        world.provider(ServiceProvider)

        @service
        class A:
            pass

        assert isinstance(world.get(A), A)
        assert world.get(A) is world.get(A)

        class B(Service):
            pass

        assert isinstance(world.get(B), B)
        assert world.get(B) is world.get(B)

    with world.test.empty():
        world.provider(ServiceProvider)
        tag = Tag()
        with pytest.raises(RuntimeError):
            @service(tags=[tag])
            class A:
                pass

        with pytest.raises(RuntimeError):
            class B(Service):
                __antidote__ = Service.Conf(tags=[tag])


def test_no_subclass_of_service():
    class A(Service):
        pass

    with pytest.raises(TypeError, match=".*abstract.*"):
        class B(A):
            pass


def test_invalid_conf():
    with pytest.raises(TypeError, match=".*__antidote__.*"):
        class Dummy(Service):
            __antidote__ = object()


@pytest.mark.parametrize('expectation, kwargs', [
    pytest.param(pytest.raises(TypeError, match=f'.*{arg}.*'),
                 {arg: object()},
                 id=arg)
    for arg in ['wiring',
                'singleton',
                'scope',
                'tags']
])
def test_invalid_conf_args(kwargs, expectation):
    with expectation:
        Service.Conf(**kwargs)


@pytest.mark.parametrize('kwargs', [
    dict(singleton=False),
    dict(tags=(Tag(),)),
    dict(wiring=Wiring(methods=['method'])),
])
def test_conf_copy(kwargs):
    conf = Service.Conf(singleton=True, tags=[]).copy(**kwargs)
    for k, v in kwargs.items():
        assert getattr(conf, k) == v


def test_invalid_copy():
    conf = Service.Conf()
    with pytest.raises(TypeError, match=".*both.*"):
        conf.copy(singleton=False, scope=None)


def test_conf_repr():
    conf = Service.Conf()
    assert "scope" in repr(conf)
