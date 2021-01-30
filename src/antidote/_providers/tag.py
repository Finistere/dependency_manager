import threading
from typing import (Dict, Generic, Hashable, Iterable, Iterator, List, Optional, Sequence,
                    Set, TypeVar, cast)

from .._compatibility.typing import final
from .._internal import API
from .._internal.utils import debug_repr, short_id
from .._internal.utils.immutable import FinalImmutable, Immutable, ImmutableGenericMeta
from ..core import Container, DependencyDebug, DependencyValue, Provider
from ..core.exceptions import AntidoteError


@API.public
class Tag(FinalImmutable):
    """
    Tags are a way to expose a dependency indirectly. Instead of explicitly
    defining a list of dependencies to retrieve, one can just mark those with
    tags and retrieve them. Typically used to support plugins or similar patterns where
    you allow others to add functionnality.

    .. doctest:: providers_tag_Tag

        >>> from antidote import Tag, Service, world, Tagged
        >>> tag = Tag()
        >>> class Plugin(Service):
        ...     __antidote__ = Service.Conf(tags=[tag])
        >>> tagged = world.get[Tagged[Plugin]](Tagged.with_(tag))
        >>> list(tagged.values()) == [world.get(Plugin)]
        True

    """
    __slots__ = ('name',)
    name: str

    def __init__(self, name: str = ''):
        """
        Args:
            name: friendly name for easier debugging. Not used for anything else.
        """
        if not isinstance(name, str):
            raise TypeError(f"name must be a str, not {type(name)}")
        super().__init__(name)

    def __repr__(self) -> str:
        if self.name:
            return f"Tag({self.name!r})#{short_id(self)}"
        else:
            return f"Tag#{short_id(self)}"


@API.public
class DuplicateTagError(AntidoteError):
    """
    The same tag is used twice on the same dependency.
    """

    def __init__(self, tag: Tag, dependency: Hashable) -> None:
        super().__init__(f"Dependency {dependency} already has the tag {tag}")


T = TypeVar('T', bound=Tag)
D = TypeVar('D')


# TODO: Python3.6 does not support inheriting FinalMeta and GenericMeta
#       To be added again once 3.6 support ends.
@API.public
@final
class Tagged(Immutable, Generic[D], metaclass=ImmutableGenericMeta):
    """
    Collection containing all tagged dependencies with the specified tag.
    Dependencies are lazily instantiated.
    """
    __slots__ = ('tag', '__lock', '__container', '__dependencies', '__instances')
    tag: Tag
    __lock: threading.RLock
    __container: Container
    __dependencies: List[object]
    __instances: List[D]

    @staticmethod
    def with_(tag: Tag) -> object:
        return TagDependency(tag)

    @API.private  # You're not supposed to create it yourself
    def __init__(self,
                 *,
                 tag: Tag,
                 container: Container,
                 dependencies: Sequence[Hashable]):
        super().__init__(
            tag,
            threading.RLock(),
            container,
            list(dependencies),
            []
        )

    def __len__(self) -> int:
        return len(self.__dependencies)

    def values(self) -> Iterator[D]:
        """Retrieved dependencies, lazily instantiated."""
        i = -1
        for i, instance in enumerate(self.__instances):
            yield instance

        i += 1
        while i < len(self):
            try:
                yield self.__instances[i]
            except IndexError:
                with self.__lock:
                    # If not other thread has already added the instance.
                    if i == len(self.__instances):
                        self.__instances.append(
                            cast(D, self.__container.get(self.__dependencies[i]))
                        )
                yield self.__instances[i]
            i += 1


@API.private
class TagDependency(FinalImmutable):
    __slots__ = ('tag',)
    tag: Tag

    def __antidote_debug_repr__(self) -> str:
        return f"Tagged with {self.tag}"


@API.private
class TagProvider(Provider[TagDependency]):
    def __init__(self) -> None:
        super().__init__()
        self.__tag_to_tagged: Dict[Tag, Set[Hashable]] = {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(tagged_dependencies={self.__tag_to_tagged})"

    def clone(self, keep_singletons_cache: bool) -> 'TagProvider':
        p = TagProvider()
        p.__tag_to_tagged = self.__tag_to_tagged.copy()
        return p

    def exists(self, dependency: Hashable) -> bool:
        return (isinstance(dependency, TagDependency)
                and dependency.tag in self.__tag_to_tagged)

    def debug(self, dependency: TagDependency) -> DependencyDebug:
        return DependencyDebug(
            debug_repr(dependency),
            scope=None,
            # Deterministic order for tests.
            dependencies=list(sorted(self.__tag_to_tagged[dependency.tag], key=repr))
        )

    def maybe_provide(self, dependency: Hashable, container: Container
                      ) -> Optional[DependencyValue]:
        if not isinstance(dependency, TagDependency):
            return None

        try:
            tagged = self.__tag_to_tagged[dependency.tag]
        except KeyError:
            return None

        return DependencyValue(
            Tagged(
                tag=dependency.tag,
                container=container,
                dependencies=list(tagged)
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
            if tag not in self.__tag_to_tagged:
                self._assert_not_duplicate(tag)
            # else:
            #   the tag could not be declared elsewhere if other _providers also
            #   check with _assert_not_duplicate and use the freeze lock (which is
            #   enforced @does_not_freeze)

        for tag in tags:
            if tag not in self.__tag_to_tagged:
                self.__tag_to_tagged[tag] = {dependency}
            elif dependency not in self.__tag_to_tagged[tag]:
                self.__tag_to_tagged[tag].add(dependency)
            else:
                raise DuplicateTagError(tag, dependency)
