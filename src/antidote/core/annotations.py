import builtins
import inspect
from typing import TypeVar, Callable, Hashable, Optional, Union

from .injection import Arg
from .._compatibility.typing import Annotated, Protocol, get_origin, get_args
from .._internal import API
from .._internal.argspec import Argument
from .._internal.utils import FinalImmutable


@API.private
class SupportsRMatmul(Protocol):
    def __rmatmul__(self, type_hint: object) -> Hashable:
        pass  # pragma: no cover


T = TypeVar('T')


@API.private
class AntidoteAnnotation:
    """Base class for all Antidote annotation."""


# API.private
IGNORE_SENTINEL = AntidoteAnnotation()

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


@API.private
def extract_annotated_dependency(type_hint: object) -> object:
    origin = get_origin(type_hint)

    # Dependency explicitly given through Annotated (PEP-593)
    if origin is Annotated:
        args = get_args(type_hint)
        antidote_annotations = [a
                                for a in getattr(type_hint, "__metadata__", tuple())
                                if isinstance(a, AntidoteAnnotation)]
        if len(antidote_annotations) > 1:
            raise TypeError(f"Multiple AntidoteAnnotation are not supported. "
                            f"Found {antidote_annotations}")
        elif antidote_annotations:
            annotation: AntidoteAnnotation = antidote_annotations[0]
            if isinstance(annotation, Get):
                return annotation.dependency
            elif isinstance(annotation, From):
                return args[0] @ annotation.source
            else:
                raise TypeError(f"Annotation {annotation} cannot be used"
                                f"outside of a function.")
        else:
            return args[0]

    return type_hint


_BUILTINS_TYPES = {e for e in builtins.__dict__.values() if isinstance(e, type)}


@API.private
def extract_argument_dependency(argument: Argument) -> object:
    type_hint = argument.type_hint_with_extras
    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # Optional
    if origin is Union:
        if len(args) == 2:
            if isinstance(None, args[1]) or isinstance(None, args[0]):
                type_hint = args[0] if isinstance(None, args[1]) else args[0]
                origin = get_origin(type_hint)
                args = get_args(type_hint)

    dependency = type_hint

    # Dependency explicitly given through Annotated (PEP-593)
    if origin is Annotated:
        antidote_annotations = [a
                                for a in type_hint.__metadata__
                                if isinstance(a, AntidoteAnnotation)]
        if len(antidote_annotations) > 1:
            raise TypeError(f"Multiple AntidoteAnnotation are not supported. "
                            f"Found {antidote_annotations}")
        elif antidote_annotations:
            # If antidote annotation, no additional check is done we just return
            # what was specified.
            annotation: AntidoteAnnotation = antidote_annotations[0]
            if isinstance(annotation, Get):
                return annotation.dependency
            elif isinstance(annotation, From):
                return args[0] @ annotation.source
            elif isinstance(annotation, FromArg):
                arg = Arg(argument.name,
                          argument.type_hint,
                          argument.type_hint_with_extras)
                return annotation.function(arg)  # type: ignore
            elif isinstance(annotation, FromArgName):
                return annotation.template.format(arg_name=argument.name)
            elif annotation is IGNORE_SENTINEL:
                return IGNORE_SENTINEL
            else:
                raise TypeError(f"Unsupported AntidoteAnnotation, {type(annotation)}")
        else:
            dependency = args[0]

    if (getattr(dependency, '__module__', '') != 'typing'
            and dependency not in _BUILTINS_TYPES
            and (isinstance(dependency, type) and inspect.isclass(dependency))):
        return dependency

    return None
