from contextlib import contextmanager

import pytest

from antidote import Scope, Tag, world, factory, Service, implementation
from antidote.utils import validated_scope, validated_tags, validate_provided_class

tag = Tag()
dummy_scope = Scope('dummy')


@contextmanager
def does_not_raise():
    yield


@pytest.mark.parametrize('expectation, tags, result', [
    pytest.param(pytest.raises(TypeError), object(), None, id='object'),
    pytest.param(pytest.raises(TypeError), [1], None, id='wrong iterable'),
    pytest.param(does_not_raise(), None, None, id='None'),
    pytest.param(does_not_raise(), [], tuple(), id='[]'),
    pytest.param(does_not_raise(), [tag], (tag,), id='[tag]'),
    pytest.param(does_not_raise(), iter([tag]), (tag,), id='iter')
])
def test_validated_tags(expectation, tags, result):
    with expectation:
        assert result == validated_tags(tags)


@pytest.mark.parametrize('expectation, kwargs', [
    pytest.param(pytest.raises(TypeError, match='.*scope.*'),
                 dict(scope=object(), default=None),
                 id='scope=object'),
    pytest.param(pytest.raises(TypeError, match='.*default.*'),
                 dict(scope=None, default=object()),
                 id='default=object'),
    pytest.param(pytest.raises(TypeError, match='.*singleton.*'),
                 dict(scope=Scope.sentinel(), singleton=object(), default=None),
                 id='singleton=object'),
    pytest.param(pytest.raises(TypeError, match='.*both.*'),
                 dict(scope=None, singleton=False, default=None),
                 id='singleton & scope'),
])
def test_invalid_validated_scope(expectation, kwargs):
    with expectation:
        assert validated_scope(**kwargs)


@pytest.mark.parametrize('scope, singleton, default, expected', [
    pytest.param(Scope.sentinel(), True, None, Scope.singleton(), id='singleton=True'),
    pytest.param(Scope.sentinel(), False, None, None, id='singleton=False'),
    pytest.param(None, None, None, None, id='scope=None'),
    pytest.param(Scope.singleton(), None, None, Scope.singleton(), id='scope=singleton'),
    pytest.param(dummy_scope, None, None, dummy_scope, id='scope=dummy'),
    pytest.param(Scope.sentinel(), None, None, None, id='default=None'),
    pytest.param(Scope.sentinel(), None, Scope.singleton(), Scope.singleton(),
                 id='default=singleton'),
    pytest.param(Scope.sentinel(), None, dummy_scope, dummy_scope, id='default=dummy'),
])
def test_validated_scope(scope, singleton, default, expected):
    assert expected == validated_scope(scope, singleton, default=default)


def test_validate_provided_class():
    class Interface:
        pass

    with pytest.raises(TypeError):
        validate_provided_class(object(), expected=Interface)

    class A(Interface, Service):
        pass

    class B(Service):
        pass

    validate_provided_class(A, expected=Interface)
    validate_provided_class(B, expected=B)
    with pytest.raises(TypeError):
        validate_provided_class(B, expected=Interface)

    validate_provided_class(A.with_kwargs(a=1), expected=Interface)
    validate_provided_class(B.with_kwargs(a=1), expected=B)
    with pytest.raises(TypeError):
        validate_provided_class(B.with_kwargs(a=1), expected=Interface)

    @implementation(Interface)
    def choose_a():
        return A

    @implementation(B)
    def choose_b():
        return B

    validate_provided_class(Interface @ choose_a, expected=Interface)
    validate_provided_class(B @ choose_b, expected=B)
    with pytest.raises(TypeError):
        validate_provided_class(B @ choose_b, expected=Interface)


def test_validate_provided_class_factory():
    class Interface:
        pass

    class A(Interface):
        pass

    class B:
        pass

    with world.test.new():
        @factory
        def build_a() -> A:
            return A()

        @factory
        def build_b() -> B:
            return B()

        validate_provided_class(A @ build_a, expected=Interface)
        validate_provided_class(B @ build_b, expected=B)
        with pytest.raises(TypeError):
            validate_provided_class(B @ build_b, expected=Interface)

        validate_provided_class(A @ build_a.with_kwargs(a=1), expected=Interface)
        validate_provided_class(B @ build_b.with_kwargs(a=1), expected=B)
        with pytest.raises(TypeError):
            validate_provided_class(B @ build_b.with_kwargs(a=1), expected=Interface)
