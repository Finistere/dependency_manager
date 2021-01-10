import threading
from typing import (Any, Dict, Generic, Hashable, Iterable, Iterator, List,
                    Optional, Sequence, Tuple, TypeVar)

from .._compatibility.typing import final
from .._internal import API
from .._internal.utils import debug_repr, short_id
from ..core import Container, DependencyDebug, DependencyValue, Provider
from ..core.exceptions import AntidoteError


@API.public
class Tag:
    """
    Tags are a way to expose a dependency indirectly. Instead of explicitly
    defining a list of dependencies to retrieve, one can just mark those with
    tags and retrieve them.

    The only requirement for a tag is to be an instance of :py:class:`.Tag`.

    .. doctest:: providers_tag_Tag

        >>> from antidote import Tag, Service, world
        >>> tag = Tag()
        >>> class Dummy(Service):
        ...     __antidote__ = Service.Conf(tags=[tag])
        >>> world.get(tag)
        <...Tagged ...>
        >>> # You can retrieve the tags and/or dependencies. Here we take both.
        ... (t, dummy) = list(world.get(tag).items())[0]
        >>> t is tag
        True
        >>> dummy is world.get(Dummy)
        True

    You may create your own subclasses to add additional information on your services.
    You can create Tags will be grouped by the output of :py:meth:`.group`. Retrieved
    dependencies will have their associated tag provided, so you can store information
    in it.

    .. doctest:: providers_tag_Tag_v2

        >>> from antidote import Tag, Service, world, Tagged
        >>> class CustomTag(Tag):
        ...     __slots__ = ('name',)  # __slots__ is recommended
        ...     name: str  # For Mypy
        ...
        ...     def __init__(self, name: str):
        ...         super().__init__(name=name)
        ...
        ...     def group(self):
        ...         return self.name.split("_")[0]
        ...
        >>> class Dummy(Service):
        ...     __antidote__ = Service.Conf(tags=[CustomTag(name="ref_dummy")])
        >>> world.get[Tagged[CustomTag, object]](CustomTag("ref_any"))
        <...Tagged ...>
        >>> (tag, dummy) = list(world.get(CustomTag("ref_any")).items())[0]
        >>> tag.name
        'ref_dummy'
        >>> dummy is world.get(Dummy)
        True

    Note that tags are immutables, well as far it goes in Python ! Tags should be used to
    group dependencies and eventually provides some *constants* information on them. It
    is not intended to store any state in it.

    """
    __slots__ = ()

    def __init__(self, **attrs: object) -> None:
        """
        :py:meth:`.__init__` is the only way to actually set attributes, to be used by
        subclasses.
        """
        for attr, value in attrs.items():
            object.__setattr__(self, attr, value)

    @final
    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"{type(self)} is immutable")

    def __antidote_debug_repr__(self) -> str:
        group = self.group()
        if group is self:
            group = f"Tag#{short_id(self)}"
        else:
            group = repr(group)
        return f"Tag: {group}"

    def __repr__(self) -> str:
        group = self.group()
        if group is self:
            group = f"Tag#{short_id(self)}"
        else:
            group = repr(group)
        return f"{type(self).__name__}(group={group})"

    def group(self) -> object:
        """Tags will be grouped by this value. By default it's the tag instance itself."""
        return self


@API.public
class DuplicateTagError(AntidoteError):
    """
    A dependency has multiple times the same tag.
    """

    def __init__(self, dependency: Hashable, existing_tag: Tag) -> None:
        super().__init__(f"Dependency {dependency} already has a tag {existing_tag}")


T = TypeVar('T', bound=Tag)
D = TypeVar('D')


# TODO: Python3.6 does not support inheriting FinalMeta and GenericMeta
#       To be added again once 3.6 support ends.
@API.public
@final
class Tagged(Generic[T, D]):
    """
    Collection containing dependencies and their tags. Dependencies are lazily
    instantiated.
    """

    @API.private  # You're not supposed to create it yourself
    def __init__(self,
                 container: Container,
                 dependencies: Sequence[Hashable],
                 tags: Sequence[T]):
        self.__lock = threading.RLock()
        self.__container = container
        self.__dependencies = list(dependencies)
        self._instances: List[Any] = []
        self._tags = list(tags)

    def __len__(self) -> int:
        return len(self._tags)

    def items(self) -> Iterator[Tuple[T, D]]:
        """
        Zips tags and values together.
        """
        return zip(self.tags(), self.values())

    # Mainly here for interface consistency with instances() (instead of _tags)
    def tags(self) -> Iterator[T]:
        """Tags associated with the retrieved dependencies."""
        return iter(self._tags)

    def values(self) -> Iterator[D]:
        """Retrieved dependencies, lazily instantiated."""
        i = -1
        for i, instance in enumerate(self._instances):
            yield instance

        i += 1
        while i < len(self):
            try:
                yield self._instances[i]
            except IndexError:
                with self.__lock:
                    # If not other thread has already added the instance.
                    if i == len(self._instances):
                        self._instances.append(
                            self.__container.get(self.__dependencies[i])
                        )
                yield self._instances[i]
            i += 1

        # Don't need to keep them anymore.
        setattr(self, "__container", None)
        setattr(self, "__dependencies", None)
        setattr(self, "__lock", None)


@API.private
class TagProvider(Provider[Tag]):
    def __init__(self) -> None:
        super().__init__()
        self.__tag_to_tagged: Dict[Any, Dict[Hashable, Tag]] = {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(tagged_dependencies={self.__tag_to_tagged})"

    def clone(self, keep_singletons_cache: bool) -> 'TagProvider':
        p = TagProvider()
        p.__tag_to_tagged = self.__tag_to_tagged.copy()
        return p

    def exists(self, dependency: Hashable) -> bool:
        return isinstance(dependency, Tag) and dependency.group() in self.__tag_to_tagged

    def debug(self, dependency: Tag) -> DependencyDebug:
        return DependencyDebug(
            debug_repr(dependency),
            scope=None,
            dependencies=list(self.__tag_to_tagged[dependency.group()].keys())
        )

    def maybe_provide(self, dependency: Hashable, container: Container
                      ) -> Optional[DependencyValue]:
        if not isinstance(dependency, Tag):
            return None

        try:
            tagged = self.__tag_to_tagged[dependency.group()]
        except KeyError:
            return None

        return DependencyValue(
            Tagged(
                container=container,
                dependencies=list(tagged.keys()),
                tags=list(tagged.values())
            ),
            # Whether the returned dependencies are singletons or not is
            # our decision to take.
            scope=None
        )

    def register(self, dependency: Hashable, *, tags: Iterable[Tag]) -> None:
        tags = list(tags)
        for tag in tags:
            if not isinstance(tag, Tag):
                raise TypeError(f"Expecting tag of type Tag, not {type(tag)}")
            if tag.group() not in self.__tag_to_tagged:
                self._assert_not_duplicate(tag)
            # else:
            #   the tag could not be declared elsewhere if other _providers also
            #   check with _assert_not_duplicate and use the freeze lock (which is
            #   enforced @does_not_freeze)

        for tag in tags:
            group = tag.group()
            if group not in self.__tag_to_tagged:
                self.__tag_to_tagged[group] = {dependency: tag}
            elif dependency not in self.__tag_to_tagged[group]:
                self.__tag_to_tagged[group][dependency] = tag
            else:
                raise DuplicateTagError(dependency,
                                        self.__tag_to_tagged[group][dependency])
