from typing import Callable, Hashable, Optional, TypeVar

from .injection import Arg
from .._compatibility.typing import Annotated, Protocol
from .._internal import API
from .._internal.utils import FinalImmutable


@API.private
class SupportsRMatmul(Protocol):
    def __rmatmul__(self, type_hint: object) -> Hashable:
        pass  # pragma: no cover


T = TypeVar('T')


@API.private
class AntidoteAnnotation:
    """Base class for all Antidote annotation."""


@API.public
class Get(FinalImmutable, AntidoteAnnotation):
    """
    Annotation specifying explicitly which dependency to inject.

    .. doctest:: core_annotation_give

        >>> from typing import Annotated
        >>> from antidote import Service, world, inject, Get
        >>> world.singletons.add("db_host", 'localhost:6789')
        >>> class Database(Service):
        ...     # Reminder: __init__ is automatically injected in a Service by default.
        ...     def __init__(self, host: Annotated[str, Get("db_host")]):
        ...         self.host = host
        >>> world.get[Database]().host == world.get("db_host")
        True
        >>> DifferentDatabase = Annotated[Database,
        ...                               Get(Database.with_kwargs(host='different'))]
        >>> @inject
        ... def load_db(db: DifferentDatabase):
        ...     return db
        >>> load_db().host
        'different'
        >>> # Annotations are also supported in world.get()
        ... world.get[Database](DifferentDatabase).host
        'different'
        >>> # But aren't necessary. However, it's more convenient if you use them
        ... # already as type hints.
        ... world.get[Database](Database.with_kwargs(host='different')).host
        'different'

    """
    __slots__ = ('dependency',)
    dependency: Hashable

    def __init__(self, __dependency: Hashable) -> None:
        super().__init__(dependency=__dependency)


@API.public
class From(FinalImmutable, AntidoteAnnotation):
    """
    Annotation specifying from where a dependency must be provided. To be used with
    :py:func:`~.antidote.factory`, :py:class:`.Factory` and :py:func:`.implementation`
    typically.

    .. doctest:: core_annotations_from

        >>> from typing import Annotated
        >>> from antidote import factory, world, inject, From
        >>> class Database:
        ...     def __init__(self, host: str):
        ...         self.host = host
        >>> @factory
        ... def build_db(host: str = 'localhost:6789') -> Database:
        ...     return Database(host=host)
        >>> @inject
        ... def f(db: Annotated[Database, From(build_db)]) -> Database:
        ...     return db
        >>> f().host
        'localhost:6789'
        >>> DifferentDatabase = Annotated[Database,
        ...                               From(build_db.with_kwargs(host='different'))]
        >>> # Annotations are also supported in world.get()
        ... world.get[Database](DifferentDatabase).host
        'different'
        >>> # But aren't necessary. However, it's more convenient if you use them
        ... # already as type hints.
        ... world.get[Database](Database @ build_db.with_kwargs(host='different')).host
        'different'

    """
    __slots__ = ('source',)
    source: SupportsRMatmul

    def __init__(self, __source: SupportsRMatmul) -> None:
        super().__init__(source=__source)


@API.public
class FromArg(FinalImmutable, AntidoteAnnotation):
    """
    Annotation specifying which dependency should be provided based on the argument. The
    function should accept a single argument of type :py:class:`~..injection.Arg` and
    return either a dependency or :py:obj:`None`.

    .. doctest:: core_annotations_from_arg

        >>> from typing import Annotated, TypeVar
        >>> from antidote import world, inject, FromArg
        >>> T = TypeVar('T')
        >>> Conf = Annotated[T, FromArg(lambda arg: "conf:" + arg.name)]
        >>> world.singletons.add('conf:port', 6789)
        >>> @inject
        ... def f(port: Conf[int]) -> int:
        ...     return port
        >>> f()
        6789
    """
    __slots__ = ('function',)
    function: 'Callable[[Arg], Optional[Hashable]]'

    def __init__(self,
                 __function: 'Callable[[Arg], Optional[Hashable]]'
                 ) -> None:
        if callable(__function):
            super().__init__(function=__function)
        else:
            raise TypeError(f"Expected a function, not {type(__function)}")


@API.public
class FromArgName(FinalImmutable, AntidoteAnnotation):
    """
    Annotation specifying which dependency should be provided based on the argument name
    with a template. It is very similar to :py:class:`.FromArg` but simpler when only the
    argument name is needed.

    .. doctest:: core_annotations_from_arg_name

        >>> from typing import Annotated, TypeVar
        >>> from antidote import world, inject, FromArgName
        >>> T = TypeVar('T')
        >>> Conf = Annotated[T, FromArgName("conf:{arg_name}")]
        >>> world.singletons.add('conf:port', 6789)
        >>> @inject
        ... def f(port: Conf[int]) -> int:
        ...     return port
        >>> f()
        6789
    """
    __slots__ = ('template',)
    template: str

    def __init__(self,
                 __template: str
                 ) -> None:
        if isinstance(__template, str):
            if "{arg_name}" not in __template:
                raise ValueError("Missing formatting parameter {arg_name} in template.")
            super().__init__(template=__template)
        else:
            raise TypeError(f"Expected a string, not {type(__template)}")


# API.private
INJECT_SENTINEL = AntidoteAnnotation()
IGNORE_SENTINEL = AntidoteAnnotation()

# API.public
Inject = Annotated[T, INJECT_SENTINEL]
Inject.__doc__ = """
No injection will be done.

.. doctest:: core_annotation_ignore

    >>> from typing import Annotated
    >>> from antidote import Service, world, inject, Ignore
    >>> class Database(Service):
    ...     pass
    >>> @inject
    ... def load_db(db: Database = None):
    ...     return db
    >>> load_db()
    <Database ...>
    >>> @inject
    ... def no_db(db: Ignore[Database] = None):
    ...     return db
    >>> no_db()
    None
"""

# API.public
Ignore = Annotated[T, IGNORE_SENTINEL]
Ignore.__doc__ = """
No injection will be done.

.. doctest:: core_annotation_ignore

    >>> from typing import Annotated
    >>> from antidote import Service, world, inject, Ignore
    >>> class Database(Service):
    ...     pass
    >>> @inject
    ... def load_db(db: Database = None):
    ...     return db
    >>> load_db()
    <Database ...>
    >>> @inject
    ... def no_db(db: Ignore[Database] = None):
    ...     return db
    >>> no_db()
    None
"""

# API.public
UseArgName = Annotated[T, FromArgName("{arg_name}")]  # type: ignore
UseArgName.__doc__ = """
The name of the argument will be used as the dependency.
"""
