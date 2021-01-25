import pytest

from antidote.core.container import (DependencyValue, OverridableRawContainer,
                                     RawContainer, Scope)
from antidote.exceptions import (DependencyCycleError, DependencyInstantiationError,
                                 DependencyNotFoundError)
from .utils import DummyProvider


@pytest.fixture
def original_container():
    c = RawContainer()
    c.add_provider(DummyProvider)
    c.get(DummyProvider).data = {'name': 'Antidote'}
    c.add_singletons({'singleton': 'yes'})
    return c


@pytest.fixture
def container(original_container):
    return original_container.clone(keep_singletons=True,
                                    keep_scopes=False)


@pytest.mark.parametrize('keep_singletons', [True, False])
def test_build(original_container: RawContainer, keep_singletons: bool):
    container = original_container.clone(keep_singletons=keep_singletons,
                                         keep_scopes=False)
    assert container.get('name') == "Antidote"
    if keep_singletons:
        assert container.get('singleton') == 'yes'
    else:
        with pytest.raises(DependencyNotFoundError):
            container.get('singleton')


def test_override_singletons(container: OverridableRawContainer):
    assert container.get('name') == "Antidote"
    assert container.get('singleton') == 'yes'

    for dep in ['name', 'singleton']:
        container.override_singletons({dep: 'different'})
        assert container.get(dep) == 'different'
        container.override_singletons({dep: 'different-v2'})
        assert container.get(dep) == 'different-v2'
        assert container.provide(dep) == DependencyValue('different-v2',
                                                         scope=Scope.singleton())


def test_override_factory(container: OverridableRawContainer):
    assert container.get('name') == "Antidote"
    assert container.get('singleton') == 'yes'

    for dep in ['name', 'singleton']:
        container.override_factory(dep, factory=lambda: 'different', scope=None)
        assert container.get(dep) == 'different'
        container.override_factory(dep, factory=lambda: 'different-v2', scope=None)
        assert container.get(dep) == 'different-v2'
        assert container.provide(dep) == DependencyValue('different-v2',
                                                         scope=None)

        # overriding previous factory which had no scope
        container.override_factory(dep, factory=lambda: object(), scope=Scope.singleton())
        value = container.get(dep)
        assert not isinstance(value, str)
        assert container.get(dep) is value

        # override still works
        container.override_factory(dep, factory=lambda: object(), scope=Scope.singleton())
        assert container.get(dep) is not value

        container.override_singletons({dep: 'Hello'})
        assert container.get(dep) == 'Hello'


def test_override_provider(container: OverridableRawContainer):
    assert container.get('name') == "Antidote"
    assert container.get('singleton') == 'yes'

    for dep in ['name', 'singleton']:
        container.override_provider(
            lambda x: DependencyValue('different') if x == dep else None)
        assert container.get(dep) == 'different'
        container.override_provider(
            lambda x: DependencyValue('different-v2') if x == dep else None)
        assert container.get(dep) == 'different-v2'
        assert container.provide(dep) == DependencyValue('different-v2',
                                                         scope=None)

        with pytest.raises(DependencyNotFoundError):
            container.get('x')  # new provider does not bring any other value

        # overriding previous provider which had no scope
        container.override_provider(
            lambda x: DependencyValue(object(),
                                      scope=Scope.singleton()) if x == dep else None)
        value = container.get(dep)
        assert not isinstance(value, str)
        assert container.get(dep) is value

        container.override_provider(
            lambda x: DependencyValue(object(),
                                      scope=Scope.singleton()) if x == dep else None)
        # didn't change anything, because it's now a singleton.
        assert container.get(dep) is value

        container.override_singletons({dep: 'Hello'})
        assert container.get(dep) == 'Hello'


def test_errors(container: OverridableRawContainer):
    container.override_factory('cycle', factory=lambda: container.get('cycle'),
                               scope=None)
    with pytest.raises(DependencyCycleError):
        container.get('cycle')

    def factory():
        raise RuntimeError()

    container.override_factory('error', factory=factory, scope=None)
    with pytest.raises(DependencyInstantiationError):
        container.get('error')
