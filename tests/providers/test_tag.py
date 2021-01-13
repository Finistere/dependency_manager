import pytest

from antidote import world
from antidote._internal.utils import short_id
from antidote._providers import Tag, Tagged, TagProvider
from antidote.core import DependencyValue
from antidote.exceptions import (DependencyNotFoundError, DuplicateTagError,
                                 FrozenWorldError)


class Service:
    pass


@pytest.fixture()
def provider():
    with world.test.empty():
        world.provider(TagProvider)
        yield world.get(TagProvider)


def test_tag():
    # id is unique
    assert repr(Tag()) != repr(Tag())

    # Immutable
    with pytest.raises(AttributeError):
        Tag().x = 1

    tagB = Tag('friendly')
    assert tagB.name == 'friendly'
    assert repr('friendly') in repr(tagB)

    with pytest.raises(TypeError):
        Tag(object())


def test_repr(provider: TagProvider):
    class A:
        pass

    tag = Tag()
    provider.register(A, tags=[tag])

    assert str(tag) in repr(provider)
    assert str(A) in repr(provider)


def test_tagged_dependencies():
    with world.test.empty():
        world.singletons.add({
            'd': object(),
            'd2': object()
        })
        tag = Tag()

        from antidote._internal.state import current_container
        tagged = Tagged(
            tag=tag,
            container=current_container(),
            dependencies=['d', 'd2']
        )

        assert tagged.tag is tag
        assert len(tagged) == 2

        expected = [world.get('d'), world.get('d2')]
        assert list(tagged.values()) == expected

        # tagged dependencies should only be retrieved once.
        with world.test.empty():
            world.singletons.add({
                'd': object(),
                'd2': object()
            })
            assert list(tagged.values()) == expected


def test_tagged_dependencies_invalid_dependency():
    with world.test.empty():
        tag = Tag()

        from antidote._internal.state import current_container
        tagged = Tagged(
            tag=tag,
            container=current_container(),
            dependencies=['d']
        )
        assert tagged.tag is tag
        assert len(tagged) == 1

        with pytest.raises(DependencyNotFoundError):
            list(tagged.values())


def test_exists():
    provider = TagProvider()
    assert not provider.exists(Tag())

    tag = Tag()
    provider.register('test', tags=[tag])
    assert provider.exists(Tagged.with_(tag))


def test_provide_unknown_tag():
    provider = TagProvider()
    assert world.test.maybe_provide_from(provider, Tag()) is None


def test_provide_tags():
    with world.test.empty():
        provider = TagProvider()
        world.singletons.add(dict(test=object(), test2=object()))
        tagA = Tag()
        tagB = Tag()
        provider.register('test', tags=[tagA, tagB])
        provider.register('test2', tags=[tagB])

        result = world.test.maybe_provide_from(provider, Tagged.with_(tagA))
        assert isinstance(result, DependencyValue)
        assert not result.is_singleton()
        tagged: Tagged = result.unwrapped
        assert len(tagged) == 1
        assert tagged.tag is tagA
        assert {world.get('test')} == set(tagged.values())

        result = world.test.maybe_provide_from(provider, Tagged.with_(tagB))
        assert isinstance(result, DependencyValue)
        assert not result.is_singleton()
        tagged: Tagged = result.unwrapped
        assert len(tagged) == 2
        assert tagged.tag is tagB
        assert {world.get('test'), world.get('test2')} == set(tagged.values())


def test_duplicate_tag_error(provider: TagProvider):
    tag = Tag()

    provider.register('test', tags=[tag])
    with pytest.raises(DuplicateTagError) as exc_info:
        provider.register('test', tags=[tag])
    # short_id being base64 can contain the chars '+/' which interfere with regex
    # matching.
    assert short_id(tag) in str(exc_info.value)

    provider = world.get(TagProvider)
    with pytest.raises(DuplicateTagError) as exc_info:
        provider.register('test2', tags=[tag, tag])
    assert short_id(tag) in str(exc_info.value)


@pytest.mark.parametrize(
    'tags',
    [
        [object],
        [lambda _: False],
        ['test', object],
    ]
)
def test_invalid_tags(provider: TagProvider, tags):
    with pytest.raises(TypeError):
        provider.register('test', tags=tags)


def test_all_must_be_valid_for_tag():
    provider = TagProvider()
    tag = Tag()
    with pytest.raises(TypeError):
        provider.register('test', tags=[tag, 3])

    assert world.test.maybe_provide_from(provider, Tagged.with_(tag)) is None


@pytest.mark.parametrize('dependency', ['test', Service, object()])
def test_unknown_dependency(dependency):
    provider = TagProvider()
    assert world.test.maybe_provide_from(provider, dependency) is None


@pytest.mark.parametrize('keep_singletons_cache', [True, False])
def test_copy(provider: TagProvider,
              keep_singletons_cache: bool):
    world.singletons.add(dict(test=object(), test2=object(), test3=object()))
    tag = Tag()
    provider.register('test', tags=[tag])
    cloned = provider.clone(keep_singletons_cache=keep_singletons_cache)

    with pytest.raises(DuplicateTagError):
        cloned.register('test', tags=[tag])

    tagged: Tagged = world.test.maybe_provide_from(cloned, Tagged.with_(tag)).unwrapped
    assert tagged.tag is tag
    assert list(tagged.values()) == [world.get('test')]

    tag2 = Tag()
    provider.register('test2', tags=[tag2])
    assert world.test.maybe_provide_from(cloned, Tagged.with_(tag2)) is None

    tag3 = Tag()
    cloned.register('test3', tags=[tag3])
    with pytest.raises(DependencyNotFoundError):
        world.get(tag3)


def test_freeze(provider: TagProvider):
    world.freeze()

    with pytest.raises(FrozenWorldError):
        provider.register("test", tags=[Tag()])
