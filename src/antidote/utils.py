import collections.abc as c_abc
import inspect
from typing import Iterable, Optional, Tuple, Hashable

from ._internal import API
from .core import Scope
from .core.injection import validate_injection
from .tag import Tag

__all__ = ['is_compiled', 'validate_injection', 'validated_tags',
           'validated_scope', 'validate_provided_class']


@API.public
def is_compiled() -> bool:
    """
    Whether current Antidote implementations is the compiled (Cython) version or not
    """
    from ._internal.wrapper import compiled
    return compiled


@API.public
def validated_tags(tags: Optional[Iterable[Tag]]) -> Optional[Tuple[Tag, ...]]:
    """
    Validates given argument to be either None or an iterable of tags. If the latter, it
    is transformed to a tuple.

    Args:
        tags: Iterable of tags to be validated.
    """
    if not (tags is None or isinstance(tags, c_abc.Iterable)):
        raise TypeError(f"tags must be an iterable of Tag instances or None, "
                        f"not {type(tags)}")
    elif tags is not None:
        tags = tuple(tags)
        if not all(isinstance(t, Tag) for t in tags):
            unexpected = [t for t in tags if not isinstance(t, Tag)]
            raise TypeError(f"Some tags are not Tag instances: {unexpected}")
        return tags
    return None


@API.public
def validated_scope(scope: Optional[Scope] = Scope.sentinel(),
                    singleton: Optional[bool] = None,
                    *,
                    default: Optional[Scope]) -> Optional[Scope]:
    """
    Validates given arguments and ensures consistency between singleton and scope.

    Top-level APIs exposes both singleton and scope arguments. Users can choose either,
    but not both. This function does all validation necessary in those APIs.

    Args:
        scope: Scope argument to validate. Neutral value is :py:meth:`.Scope.sentinel`.
        singleton: Singleton argument to validate. Neutral value is :py:obj:`None`.
        default: Default value to use if both scope and singleton have neutral values.

    Returns:

    """
    if not (scope is None or isinstance(scope, Scope)):
        raise TypeError(f"scope must be a Scope or None, not {type(scope)}")
    if not (default is None or isinstance(default, Scope)):
        raise TypeError(f"default must be a Scope or None, not {type(default)}")

    if isinstance(singleton, bool):
        if scope is not Scope.sentinel():
            raise TypeError("Use either singleton or scope argument, not both.")
        return Scope.singleton() if singleton else None
    if singleton is not None:
        raise TypeError(f"singleton must be a boolean or None, "
                        f"not {type(singleton)}")

    return default if scope is Scope.sentinel() else scope


@API.experimental
def validate_provided_class(dependency: Hashable, *, expected: type) -> None:
    """
    Verify that the dependency will provide a class which is a subclass
    of :code:`expected`.

    :meta: private
    """
    # import private stuff
    from ._providers.factory import FactoryDependency
    from ._providers.service import Build
    from ._providers.indirect import ImplementationDependency

    cls: object = dependency
    if isinstance(cls, Build):
        cls = cls.dependency
    if isinstance(cls, FactoryDependency):
        cls = cls.output
    if isinstance(cls, ImplementationDependency):
        cls = cls.interface

    if not (isinstance(cls, type) and inspect.isclass(cls)):
        raise TypeError(f"{dependency} does not provide any class")

    if not issubclass(cls, expected):
        raise TypeError(f"Expected a subclass of {expected}, not {cls}")
