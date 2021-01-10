from contextlib import contextmanager
from typing import Hashable, Optional

import pytest

from antidote import world
from antidote.core import (Container, DependencyValue, does_not_freeze, Provider,
                           StatelessProvider)
from antidote.exceptions import FrozenWorldError


@contextmanager
def does_not_raise():
    yield


def test_freeze_world():
    class DummyProvider(Provider):
        def provide(self, dependency: Hashable, container: Container
                    ) -> Optional[DependencyValue]:
            return None

        def clone(self, keep_singletons_cache: bool) -> 'DummyProvider':
            return self

        def register(self):
            return "register"

        @does_not_freeze
        def method(self):
            return "method"

        @staticmethod
        def static():
            return "static"

        @classmethod
        def klass(cls):
            return "klass"

    provider = DummyProvider()
    assert provider.register() == "register"
    assert provider.method() == "method"
    assert provider.static() == "static"
    assert provider.klass() == "klass"

    with world.test.empty():
        world.provider(DummyProvider)
        provider = world.get[DummyProvider]()
        assert provider.register() == "register"
        assert provider.method() == "method"
        assert provider.static() == "static"
        assert provider.klass() == "klass"

        world.freeze()
        assert provider.method() == "method"
        assert provider.static() == "static"
        assert provider.klass() == "klass"
        provider.clone(False)
        provider.provide(None, None)
        with pytest.raises(FrozenWorldError):
            provider.register()


def test_stateless():
    class DummyProvider(StatelessProvider):
        def provide(self, dependency: Hashable, container: Container
                    ) -> Optional[DependencyValue]:
            return None

    p = DummyProvider()
    assert p.clone(True) is not p
    assert isinstance(p.clone(False), DummyProvider)


def test_no_default_implementation():
    class Dummy(Provider):
        pass

    with pytest.raises(NotImplementedError):
        Dummy().maybe_provide(object(), object())

    with pytest.raises(NotImplementedError):
        Dummy().exists(object())

    with pytest.raises(NotImplementedError):
        Dummy().clone(False)

    with pytest.raises(RuntimeError):
        Dummy().provide(object(), object())

    with pytest.raises(NotImplementedError):
        Dummy().exists(False)


def test_debug():
    x = object()

    class Dummy(Provider):
        def exists(self, dependency: Hashable) -> bool:
            return dependency is x

    Dummy().maybe_debug(object())  # should no fail
    with pytest.warns(UserWarning, match="(?i).*debug.*"):
        Dummy().maybe_debug(x)


def test_provide():
    x = object()

    class Dummy(Provider):
        def exists(self, dependency: Hashable) -> bool:
            return dependency is x

        def provide(self, dependency: Hashable,
                    container: Container) -> DependencyValue:
            assert dependency is x
            return DependencyValue(None)

    dummy = Dummy()
    assert world.test.maybe_provide_from(dummy, 1) is None
    assert world.test.maybe_provide_from(dummy, x) is not None


def test_container_lock():
    from ..test_thread_safety import ThreadSafetyTest

    with world.test.empty():
        failures = []

        @world.provider
        class A(Provider):
            def exists(self, dependency: Hashable) -> bool:
                return dependency == 'a'

            def provide(self, dependency: Hashable,
                        container: Container) -> DependencyValue:
                ThreadSafetyTest.check_locked(failures)
                return DependencyValue('a')

            def change_state(self):
                with self._container_lock():
                    ThreadSafetyTest.check_locked(failures)

        @world.provider
        class B(Provider):
            def exists(self, dependency: Hashable) -> bool:
                return dependency == 'b'

            def provide(self, dependency: Hashable,
                        container: Container) -> DependencyValue:
                ThreadSafetyTest.check_locked(failures)
                return DependencyValue('b')

            def change_state(self):
                with self._container_lock():
                    ThreadSafetyTest.check_locked(failures)

        a = world.get[A]()
        b = world.get[B]()
        actions = [
            lambda: a.change_state(),
            lambda: world.get('a'),
            lambda: b.change_state(),
            lambda: world.get('b')
        ]

        def worker():
            import random
            for f in random.choices(actions, k=20):
                f()

        ThreadSafetyTest.run(worker, n_threads=5)
        assert not failures

    with world.test.empty():
        class C(Provider):
            def change_state(self):
                with self._container_lock():
                    pass

        # Should not raise any error if not bound to any container yet
        C().change_state()
