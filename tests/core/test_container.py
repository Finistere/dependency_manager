from typing import Dict, Hashable, Optional

import pytest

from antidote.core.container import (Container, DependencyValue, RawContainer,
                                     RawProvider, Scope)
from antidote.core.exceptions import DuplicateDependencyError
from antidote.core.utils import DependencyDebug
from antidote.exceptions import (DependencyCycleError, DependencyInstantiationError,
                                 DependencyNotFoundError, FrozenWorldError)
from .utils import DummyFactoryProvider, DummyProvider


class A:
    def __init__(self, *args):
        pass


class B:
    def __init__(self, *args):
        pass


class C:
    def __init__(self, *args):
        pass


class ServiceWithNonMetDependency:
    def __init__(self, dependency):
        pass


@pytest.fixture()
def container():
    return RawContainer()


def test_dependency_repr():
    o = object()
    d = DependencyValue(o, scope=Scope.singleton())

    assert 'singleton' in repr(d)
    assert repr(o) in repr(d)


def test_scope_repr():
    s = Scope("test")
    assert "test" in repr(s)
    assert "test" in str(s)


def test_add_singletons(container: RawContainer):
    x = object()
    y = object()
    container.add_singletons({'x': x, 'y': y})

    assert container.provide('x').unwrapped is x
    assert container.provide('x').scope is Scope.singleton()
    assert container.get('y') is y


def test_duplicate_singletons(container: RawContainer):
    x = object()
    container.add_singletons(dict(x=x))

    with pytest.raises(DuplicateDependencyError):
        container.add_singletons(dict(x=object()))

    # did not change singleton
    assert container.get('x') is x


def test_get(container: RawContainer):
    container.add_provider(DummyFactoryProvider)
    container.get(DummyFactoryProvider).data = {
        A: lambda _: A(),
        ServiceWithNonMetDependency: lambda _: ServiceWithNonMetDependency(),
    }
    container.add_provider(DummyProvider)
    container.get(DummyProvider).data = {'name': 'Antidote'}

    assert isinstance(container.get(A), A)
    assert isinstance(container.provide(A), DependencyValue)
    assert 'Antidote' == container.get('name')
    assert 'Antidote' == container.provide('name').unwrapped

    with pytest.raises(DependencyNotFoundError):
        container.get(object)

    with pytest.raises(DependencyInstantiationError):
        container.get(ServiceWithNonMetDependency)


def test_singleton(container: RawContainer):
    container.add_provider(DummyFactoryProvider)
    container.get(DummyFactoryProvider).data = {
        A: lambda _: A(),
        B: lambda _: B(),
    }

    service = container.get(A)
    assert container.get(A) is service
    assert container.provide(A).unwrapped is service
    assert container.provide(A).scope is Scope.singleton()

    container.get(DummyFactoryProvider).singleton = False
    another_service = container.get(B)
    assert container.get(B) is not another_service
    assert container.provide(B).unwrapped is not another_service
    assert container.provide(B).scope is None

    assert container.get(A) == service


def test_dependency_cycle_error(container: RawContainer):
    container.add_provider(DummyFactoryProvider)
    container.get(DummyFactoryProvider).data = {
        A: lambda _: container.get(B),
        B: lambda _: container.get(C),
        C: lambda _: container.get(A),
    }

    with pytest.raises(DependencyCycleError):
        container.get(A)

    with pytest.raises(DependencyCycleError):
        container.get(B)

    with pytest.raises(DependencyCycleError):
        container.get(C)


def test_dependency_instantiation_error(container: RawContainer):
    container.add_provider(DummyFactoryProvider)

    def raise_error():
        raise RuntimeError()

    container.get(DummyFactoryProvider).data = {
        A: lambda _: container.get(B),
        B: lambda _: container.get(C),
        C: lambda _: raise_error(),
    }

    with pytest.raises(DependencyInstantiationError, match=".*C.*"):
        container.get(C)

    with pytest.raises(DependencyInstantiationError, match=".*A.*"):
        container.get(A)


def test_providers_property(container: RawContainer):
    x = object()
    container.add_provider(DummyProvider)
    container.get(DummyProvider).data = dict(x=x)
    container.add_provider(DummyFactoryProvider)
    container.get(DummyFactoryProvider).data = dict(y=lambda c: c.get('y'))

    assert len(container.providers) == 2
    for provider in container.providers:
        if isinstance(provider, DummyProvider):
            assert provider.data == dict(x=x)
        else:
            assert 'y' in provider.data


def test_scope_property(container: RawContainer):
    assert container.scopes == []

    s1 = container.create_scope('1')
    assert container.scopes == [s1]

    s2 = container.create_scope('2')
    assert container.scopes == [s1, s2]


def test_repr_str(container: RawContainer):
    container.add_provider(DummyProvider)
    container.get(DummyProvider).data = {'name': 'Antidote'}
    container.add_singletons({'test': 1})

    assert 'test' in repr(container)
    assert repr(container.get(DummyProvider)) in repr(container)
    assert str(container.get(DummyProvider)) in str(container)


def test_freeze(container: RawContainer):
    container.add_provider(DummyProvider)
    container.get(DummyProvider).data = {'name': 'Antidote'}
    container.freeze()

    with pytest.raises(FrozenWorldError):
        container.add_provider(DummyFactoryProvider)

    with pytest.raises(FrozenWorldError):
        container.add_singletons({'test': object()})


def test_freezing_locked(container: RawContainer):
    with container.locked(freezing=True):
        pass

    container.freeze()

    with pytest.raises(FrozenWorldError):
        with container.locked(freezing=True):
            pass


def test_provider_property(container: RawContainer):
    container.add_provider(DummyProvider)
    assert container.providers == [container.get(DummyProvider)]


def test_clone_keep_singletons(container: RawContainer):
    container.add_provider(DummyProvider)
    container.get(DummyProvider).data = {'name': 'Antidote'}
    container.add_singletons({'test': object()})

    cloned = container.clone(keep_singletons=True)
    assert cloned.get('test') is container.get('test')
    assert cloned.get(DummyProvider) is not container.get(DummyProvider)

    cloned = container.clone(keep_singletons=False)
    with pytest.raises(DependencyNotFoundError):
        cloned.get("test")
    assert cloned.get(DummyProvider) is not container.get(DummyProvider)


def test_providers_must_properly_clone(container: RawContainer):
    class DummySelf(RawProvider):
        def clone(self, keep_singletons_cache: bool) -> 'RawProvider':
            return self

    container.add_provider(DummySelf)

    with pytest.raises(RuntimeError, match="(?i).*provider.*instance.*"):
        container.clone(keep_singletons=False,
                        keep_scopes=False)


def test_providers_must_properly_clone2(container: RawContainer):
    container.add_provider(DummyProvider)
    p = container.get(DummyProvider)

    class DummyRegistered(RawProvider):
        def clone(self, keep_singletons_cache: bool) -> 'RawProvider':
            return p

    container.add_provider(DummyRegistered)
    with pytest.raises(RuntimeError, match="(?i).*provider.*fresh instance.*"):
        container.clone(keep_singletons=False,
                        keep_scopes=False)


@pytest.mark.filterwarnings("ignore:Debug information")
def test_raise_if_exists(container: RawContainer):
    container.raise_if_exists(1)  # Nothing should happen

    container.add_singletons({1: 10})
    with pytest.raises(DuplicateDependencyError, match=".*singleton.*10.*"):
        container.raise_if_exists(1)

    container.add_provider(DummyProvider)
    container.get(DummyProvider).data = {'name': 'Antidote'}
    with pytest.raises(DuplicateDependencyError, match=".*DummyProvider.*"):
        container.raise_if_exists('name')

    class DummyProviderWithDebug(DummyProvider):
        def debug(self, dependency) -> DependencyDebug:
            return DependencyDebug("debug_info", scope=Scope.singleton())

    container.add_provider(DummyProviderWithDebug)
    container.get(DummyProviderWithDebug).data = {'hello': 'world'}
    with pytest.raises(DuplicateDependencyError,
                       match=".*DummyProviderWithDebug.*\\ndebug_info"):
        container.raise_if_exists('hello')


def test_scope(container: RawContainer):
    class ScopeProvider(RawProvider):
        dependencies: Dict[object, DependencyValue] = {}

        def exists(self, dependency):
            return dependency in self.dependencies

        def maybe_provide(self, dependency: Hashable, container: Container
                          ) -> Optional[DependencyValue]:
            try:
                return self.dependencies[dependency]
            except KeyError:
                return None

    container.add_provider(ScopeProvider)

    scope = container.create_scope('dummy')
    x = object()
    y = object()
    ScopeProvider.dependencies[1] = DependencyValue(x, scope=scope)
    assert container.get(1) is x

    ScopeProvider.dependencies[1] = DependencyValue(y, scope=scope)
    # Using cache
    assert container.get(1) is x
    assert container.provide(1) == DependencyValue(x, scope=scope)

    container.reset_scope(scope)
    assert container.get(1) is y
    assert container.provide(1) == DependencyValue(y, scope=scope)


def test_sanity_checks(container: RawContainer):
    # Cannot register twice the same kind of provider
    container.add_provider(DummyProvider)
    with pytest.raises(AssertionError):
        container.add_provider(DummyProvider)

    container.create_scope('test')
    with pytest.raises(AssertionError):
        container.create_scope('test')


def test_already_frozen(container: RawContainer):
    container.freeze()

    with pytest.raises(FrozenWorldError):
        container.freeze()
