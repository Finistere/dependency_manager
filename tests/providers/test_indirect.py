from typing import Callable

import pytest

from antidote import Scope, world
from antidote._providers import IndirectProvider, ServiceProvider
from antidote.core.exceptions import DependencyNotFoundError
from antidote.exceptions import DuplicateDependencyError, FrozenWorldError


class Interface:
    pass


class A(Interface):
    pass


class B(Interface):
    pass


@pytest.fixture(autouse=True)
def empty_world():
    with world.test.empty():
        yield


@pytest.fixture
def service(empty_world):
    world.provider(ServiceProvider)
    return world.get(ServiceProvider)


@pytest.fixture
def indirect(empty_world):
    world.provider(IndirectProvider)
    return world.get(IndirectProvider)


@pytest.fixture(params=[True, False])
def permanent(request):
    return request.param


def test_implementation(permanent: bool):
    indirect = IndirectProvider()
    world.singletons.add(A, A())
    impl = indirect.register_implementation(Interface, lambda: A, permanent=permanent)

    assert world.test.maybe_provide_from(indirect, impl).unwrapped is world.get(A)
    assert world.test.maybe_provide_from(indirect, impl).is_singleton() is permanent
    assert Interface.__name__ in repr(indirect)


@pytest.mark.parametrize('singleton', [True, False])
@pytest.mark.parametrize('permanent', [True, False])
def test_implementation_permanent_singleton(service: ServiceProvider,
                                            singleton: bool,
                                            permanent: bool):
    scope = Scope.singleton() if singleton else None
    choice = 'a'

    def implementation():
        return dict(a=A, b=B)[choice]

    service.register(A, scope=scope)
    service.register(B, scope=scope)
    indirect = IndirectProvider()
    impl = indirect.register_implementation(Interface,
                                            implementation,
                                            permanent=permanent)

    instance = world.test.maybe_provide_from(indirect, impl).unwrapped
    assert isinstance(instance, A)
    assert (instance is world.get(A)) is singleton
    assert world.test.maybe_provide_from(
        indirect,
        impl).is_singleton() is (singleton and permanent)

    choice = 'b'
    assert implementation() == B
    assert world.test.maybe_provide_from(
        indirect,
        impl).is_singleton() is (singleton and permanent)
    instance = world.test.maybe_provide_from(indirect, impl).unwrapped
    if permanent:
        assert isinstance(instance, A)
        assert (instance is world.get(A)) is singleton
    else:
        assert isinstance(instance, B)
        assert (instance is world.get(B)) is singleton


def test_implementation_exists(indirect: IndirectProvider, permanent: bool):
    world.singletons.add(A, A())
    impl = indirect.register_implementation(Interface, lambda: A, permanent=permanent)

    assert not indirect.exists(object())
    assert indirect.exists(impl)
    assert not indirect.exists(A)


@pytest.mark.parametrize('keep_singletons_cache', [True, False])
@pytest.mark.parametrize('register', [
    pytest.param(
        lambda indirect, inf, impl: indirect.register_implementation(inf, lambda: impl,
                                                                     permanent=False),
        id='implementation'),
    pytest.param(
        lambda indirect, inf, impl: indirect.register_implementation(inf, lambda: impl,
                                                                     permanent=True),
        id='implementation_permanent')
])
def test_clone(indirect: IndirectProvider,
               keep_singletons_cache: bool,
               register: Callable[[IndirectProvider, type, type], object]):
    world.singletons.add({A: A()})

    dep = register(indirect, Interface, A)
    a = world.get(dep)
    assert isinstance(a, Interface)

    if keep_singletons_cache:
        with world.test.clone(keep_singletons=True):
            clone = indirect.clone(True)
            assert world.test.maybe_provide_from(clone, dep).unwrapped is a
    else:
        with world.test.empty():
            world.singletons.add({A: A(), B: B()})
            clone = indirect.clone(False)
            instance = world.test.maybe_provide_from(clone, dep).unwrapped
            assert instance is world.get(A)
            assert instance is not a

    class Interface2:
        pass

    class A2(Interface2):
        pass

    class Interface3:
        pass

    class A3(Interface3):
        pass

    world.singletons.add({A2: A2(), A3: A3()})
    # Original does not modify clone
    impl = register(indirect, Interface2, A2)
    assert world.get(impl) is world.get(A2)
    assert world.test.maybe_provide_from(clone, impl) is None
    assert clone.maybe_debug(impl) is None

    # Did not modify original provider
    impl = register(clone, Interface3, A3)
    assert world.test.maybe_provide_from(clone, impl).unwrapped is world.get(A3)
    assert indirect.maybe_debug(impl) is None
    with pytest.raises(DependencyNotFoundError):
        world.get(Interface3)


def test_freeze(indirect: IndirectProvider, permanent):
    world.freeze()

    with pytest.raises(FrozenWorldError):
        indirect.register_implementation(Interface, lambda: A, permanent=False)

    with pytest.raises(FrozenWorldError):
        indirect.register_implementation(Interface, lambda: A, permanent=True)

    with pytest.raises(DependencyNotFoundError):
        world.get(Interface)


def test_register_duplicate_check(indirect: IndirectProvider, permanent: bool):
    def implementation():
        return A

    indirect.register_implementation(Interface, implementation, permanent=permanent)

    with pytest.raises(DuplicateDependencyError):
        indirect.register_implementation(Interface, implementation, permanent=False)

    with pytest.raises(DuplicateDependencyError):
        indirect.register_implementation(Interface, implementation, permanent=True)


def test_invalid_link(permanent: bool):
    indirect = IndirectProvider()
    target = 'target'

    def implementation():
        return target

    impl = indirect.register_implementation(A, implementation, permanent=permanent)

    with pytest.raises(DependencyNotFoundError, match=".*" + target + ".*"):
        world.test.maybe_provide_from(indirect, impl)
