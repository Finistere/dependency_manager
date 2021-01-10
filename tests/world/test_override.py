from typing import Any, Callable, Hashable, Optional

import pytest

from antidote import Scope, world, Service
from antidote.core import DependencyValue
from antidote.core.exceptions import DuplicateDependencyError
from antidote.exceptions import DependencyNotFoundError
from ..core.utils import DummyProvider

sentinel = object()


@pytest.mark.parametrize('override', [
    pytest.param(lambda d, v: world.test.override.singleton(d, v), id='singleton'),
    pytest.param(lambda d, v: world.test.override.singleton({d: v}), id='singletons')
])
def test_singleton(override: Callable[[Any, Any], Any]):
    with world.test.empty():
        with world.test.clone():
            override('test', 'a')
            assert world.get("test") == 'a'

        world.singletons.add('test', sentinel)

        with world.test.clone(keep_singletons=True):
            assert world.get("test") is sentinel
            override('test', 'a')
            assert world.get("test") == 'a'

    with world.test.clone():
        override("test", 'a')
        assert world.get("test") == 'a'

        # double override works
        override("test", 'b')
        assert world.get("test") == 'b'


def test_factory():

    # overrides normal provider
    with world.test.empty():
        world.provider(DummyProvider)
        p = world.get[DummyProvider]()
        p.data = {'test': sentinel}
        assert world.get('test') is sentinel

        with world.test.clone():
            @world.test.override.factory('test')
            def f():
                return 'a'

            assert world.get('test') == 'a'

            @world.test.override.factory('test')
            def g():
                return 'b'

            assert world.get('test') == 'b'

    # overrides singletons
    with world.test.empty():
        world.singletons.add({'test': sentinel, 'test2': sentinel})
        assert world.get('test') is sentinel
        assert world.get('test2') is sentinel

        with world.test.clone(keep_singletons=True):
            @world.test.override.factory('test')
            def f1():
                return 'a'

            assert world.get('test') == 'a'
            assert world.get('test2') is sentinel

    # non singleton
    with world.test.clone():
        @world.test.override.factory('test')
        def f2():
            return object()

        assert world.get('test') is not world.get('test')

    # singleton
    with world.test.clone():
        @world.test.override.factory('test', singleton=True)
        def f3():
            return object()

        assert world.get('test') is world.get('test')


def test_factory_return_type():
    class X(Service):
        pass

    with world.test.clone():
        @world.test.override.factory()
        def build() -> X:
            return "hello X"

        assert world.get(X) == "hello X"

        with pytest.raises(ValueError, match=".*dependency.*return type hint.*"):
            @world.test.override.factory()
            def build2():
                return "hello X"


def test_provider():
    # overrides normal provider
    with world.test.empty():
        world.provider(DummyProvider)
        p = world.get[DummyProvider]()
        p.data = {'test': sentinel, 'test2': sentinel}
        assert world.get('test') is sentinel
        assert world.get('test2') is sentinel

        with world.test.clone():
            @world.test.override.provider()
            def f(dependency: Hashable) -> Optional[DependencyValue]:
                if dependency == 'test':
                    return DependencyValue('a')

            assert world.get('test') == 'a'
            assert world.get('test2') is sentinel

    # overrides singletons
    with world.test.empty():
        world.singletons.add({'test': sentinel, 'test2': sentinel})
        assert world.get('test') is sentinel
        assert world.get('test2') is sentinel

        with world.test.clone(keep_singletons=True):
            @world.test.override.provider()
            def f2(dependency: Hashable) -> Optional[DependencyValue]:
                if dependency == 'test':
                    return DependencyValue('a')

            assert world.get('test') == 'a'
            assert world.get('test2') is sentinel

    # non singleton dependency
    with world.test.clone():

        @world.test.override.provider()
        def f3(dependency: Hashable) -> Optional[DependencyValue]:
            if dependency == 'test':
                return DependencyValue(object())

        assert world.get('test') is not world.get('test')

    # singleton dependency
    with world.test.clone():

        @world.test.override.provider()
        def f4(dependency: Hashable) -> Optional[DependencyValue]:
            if dependency == 'test':
                return DependencyValue(object(), scope=Scope.singleton())

        assert world.get('test') is world.get('test')


def test_scope_support():
    dummy_scope = world.scopes.new("dummy")

    class X(Service):
        __antidote__ = Service.Conf(scope=dummy_scope)

    with world.test.clone():
        x = world.get(X)
        assert x is world.get(X)
        world.scopes.reset(dummy_scope)
        assert world.get(X) is not x

        @world.test.override.factory(1, scope=dummy_scope)
        def build():
            return object()

        x = world.get(1)
        assert x is world.get(1)
        world.scopes.reset(dummy_scope)
        assert world.get(1) is not x

        @world.test.override.provider()
        def provide(dependency):
            if dependency == 2:
                return DependencyValue(object(), scope=dummy_scope)

        x = world.get(2)
        assert x is world.get(2)
        world.scopes.reset(dummy_scope)
        assert world.get(2) is not x


def test_deep_clone():
    with world.test.empty():
        world.singletons.add("test", sentinel)

        with world.test.clone(keep_singletons=True):
            with world.test.clone(keep_singletons=True):
                assert world.get("test") is sentinel

            with world.test.clone(keep_singletons=False):
                with pytest.raises(DependencyNotFoundError):
                    world.get("test")

        with world.test.clone():
            world.test.override.singleton("test", 'a')
            with world.test.clone(keep_singletons=True):
                assert world.get("test") == 'a'

            with world.test.clone(keep_singletons=False):
                with pytest.raises(DependencyNotFoundError):
                    world.get("test")


def test_debug():
    with world.test.new():
        world.singletons.add("original", 2)

        with world.test.clone(keep_singletons=True):
            from antidote._internal import state

            world.test.override.singleton("s", 1)

            @world.test.override.factory('f')
            def f():
                return 2

            c = state.current_container()
            assert "Override" in c.debug("s").info
            assert "Singleton" in c.debug("s").info

            assert "Override" in c.debug("f").info
            assert "Factory" in c.debug("f").info

            assert "Singleton" in c.debug("original").info


def test_invalid():
    with world.test.clone():
        with pytest.raises(TypeError):
            world.test.override.singleton(1)

        with pytest.raises(TypeError):
            world.test.override.singleton(dict(), 1)

        with pytest.raises(TypeError):
            @world.test.override.factory('test', singleton=object())
            def f():
                pass

        with pytest.raises(TypeError):
            world.test.override.factory('test', singleton=True)(object())

        with pytest.raises(TypeError):
            world.test.override.provider()(object())
