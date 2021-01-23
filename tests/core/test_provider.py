from contextlib import contextmanager
from typing import Hashable, Optional

import pytest

from antidote import world
from antidote.core import (Container, DependencyValue, Provider, StatelessProvider,
                           does_not_freeze)
from antidote.core.exceptions import DuplicateDependencyError
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

    with pytest.raises(NotImplementedError):
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


def test_assert_not_duplicate():
    x = object()

    class A(Provider[Hashable]):
        def __init__(self):
            super().__init__()
            self.registered = dict()

        def exists(self, dependency: Hashable) -> bool:
            return dependency in self.registered

        def provide(self,
                    dependency: Hashable,
                    container: Container) -> DependencyValue:
            return DependencyValue(self.registered[dependency])

        def add(self, dependency: Hashable, value: object):
            self._assert_not_duplicate(dependency)
            self.registered[dependency] = value

    with world.test.empty():
        a = A()
        a.add(x, 1)

        with pytest.raises(DuplicateDependencyError):
            a.add(x, 1)

    with world.test.empty():
        world.provider(A)

        @world.provider
        class B(Provider[Hashable]):
            def __init__(self):
                super().__init__()
                self.registered = dict()

            def exists(self, dependency: Hashable) -> bool:
                return dependency in self.registered

            def provide(self,
                        dependency: Hashable,
                        container: Container) -> DependencyValue:
                return DependencyValue(self.registered[dependency])

            def add(self, dependency: Hashable, value: object):
                self._assert_not_duplicate(dependency)
                self.registered[dependency] = value

        world.get[A]().add(x, 1)

        with pytest.raises(DuplicateDependencyError):
            world.get[B]().add(x, 1)
