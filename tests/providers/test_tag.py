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
    assert Tag().group != Tag().group
    assert repr(Tag()) != repr(Tag())

    # Immutable
    with pytest.raises(AttributeError):
        Tag().x = 1


def test_custom_tag():
    class CustomTag(Tag):
        def group(self):
            return "hello"

    assert "hello" in repr(CustomTag())


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
        t = Tagged(
            container=current_container(),
            dependencies=['d', 'd2'],
            tags=[tag, tag]
        )

        assert set(t.tags()) == {tag}
        assert len(t) == 2

        expected = [world.get('d'), world.get('d2')]
        assert list(t.values()) == expected

        # tagged dependencies should only be retrieved once.
        with world.test.empty():
            world.singletons.add({
                'd': object(),
                'd2': object()
            })
            assert list(t.values()) == expected


def test_tagged_dependencies_invalid_dependency():
    with world.test.empty():
        tag = Tag()

        from antidote._internal.state import current_container
        t = Tagged(
            container=current_container(),
            dependencies=['d'],
            tags=[tag]
        )
        assert set(t.tags()) == {tag}
        assert len(t) == 1

        with pytest.raises(DependencyNotFoundError):
            list(t.values())


def test_exists():
    provider = TagProvider()
    assert not provider.exists(Tag())

    tag = Tag()
    provider.register('test', tags=[tag])
    assert provider.exists(tag)

    class CustomTag(Tag):
        def group(self):
            return 'group'

    assert not provider.exists(CustomTag())
    provider.register('test2', tags=[CustomTag()])
    assert provider.exists(CustomTag())


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

        result = world.test.maybe_provide_from(provider, tagA)
        assert isinstance(result, DependencyValue)
        assert not result.is_singleton()
        tagged_dependencies: Tagged = result.unwrapped
        assert len(tagged_dependencies) == 1
        assert set(tagged_dependencies.tags()) == {tagA}
        assert {world.get('test')} == set(tagged_dependencies.values())

        result = world.test.maybe_provide_from(provider, tagB)
        assert isinstance(result, DependencyValue)
        assert not result.is_singleton()
        tagged_dependencies: Tagged = result.unwrapped
        assert len(tagged_dependencies) == 2
        assert {(tagB, world.get('test')),
                (tagB, world.get('test2'))} == set(tagged_dependencies.items())
        assert set(tagged_dependencies.tags()) == {tagB}
        assert {world.get('test'), world.get('test2')} == set(
            tagged_dependencies.values())


def test_custom_tags(provider: TagProvider):
    class CustomTag(Tag):
        __slots__ = ('name', 'attr')
        name: str
        attr: int

        def __init__(self, name: str, attr: int = 0):
            super().__init__(name=name, attr=attr)

        def group(self):
            return self.name

    world.singletons.add(dict(test=object(), test2=object()))
    test_tags = [CustomTag("A", attr=1), CustomTag("B", attr=1)]
    provider.register('test', tags=test_tags)
    test2_tags = [CustomTag("B", attr=2)]
    provider.register('test2', tags=test2_tags)

    result = world.get(CustomTag("A"))
    assert list(result.tags()) == [test_tags[0]]
    assert list(result.values()) == [world.get('test')]

    result = world.get(CustomTag("B"))
    if list(result.tags()) == [test_tags[1], test2_tags[0]]:
        assert list(result.values()) == [world.get('test'), world.get('test2')]
    elif list(result.tags()) == [test2_tags[0], test_tags[1]]:
        assert list(result.values()) == [world.get('test2'), world.get('test')]
    else:
        assert False


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

    assert world.test.maybe_provide_from(provider, tag) is None


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

    assert list(world.test.maybe_provide_from(cloned, tag).unwrapped.tags()) == [tag]
    assert list(world.test.maybe_provide_from(cloned, tag).unwrapped.values()) == [
        world.get('test')]

    tag2 = Tag()
    provider.register('test2', tags=[tag2])
    assert world.test.maybe_provide_from(cloned, tag2) is None

    tag3 = Tag()
    cloned.register('test3', tags=[tag3])
    with pytest.raises(DependencyNotFoundError):
        world.get(tag3)


def test_freeze(provider: TagProvider):
    world.freeze()

    with pytest.raises(FrozenWorldError):
        provider.register("test", tags=[Tag()])
