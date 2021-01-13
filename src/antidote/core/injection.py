import collections.abc as c_abc
from typing import (Any, Callable, Hashable, Iterable, Mapping,
                    Optional, overload, Sequence, TypeVar, Union)

from ._injection import raw_inject
from .._compatibility.typing import final
from .._internal import API
from .._internal.utils import FinalImmutable

F = TypeVar('F', bound=Callable[..., Any])
AnyF = Union[Callable[..., Any], staticmethod, classmethod]


@API.public
@final
class Arg(FinalImmutable):
    """
    Represents an argument (name and type hint) if you need a very custom injection
    logic.
    """
    __slots__ = ('name', 'type_hint')
    name: str
    """Name of the argument"""
    type_hint: Any
    """Type hint of the argument if any"""


# This type is experimental.
DEPENDENCIES_TYPE = Union[
    Mapping[str, Hashable],  # {arg_name: dependency, ...}
    Sequence[Optional[Hashable]],  # (dependency for arg 1, ...)
    Callable[[Arg], Optional[Hashable]],  # arg -> dependency
    str  # str.format(arg_name=arg_name) -> dependency
]


@overload
def inject(func: staticmethod,  # noqa: E704  # pragma: no cover
           *,
           dependencies: DEPENDENCIES_TYPE = None,
           use_names: Union[bool, Iterable[str]] = None,
           use_type_hints: Union[bool, Iterable[str]] = None
           ) -> staticmethod: ...


@overload
def inject(func: classmethod,  # noqa: E704  # pragma: no cover
           *,
           dependencies: DEPENDENCIES_TYPE = None,
           use_names: Union[bool, Iterable[str]] = None,
           use_type_hints: Union[bool, Iterable[str]] = None
           ) -> classmethod: ...


@overload
def inject(func: F,  # noqa: E704  # pragma: no cover
           *,
           dependencies: DEPENDENCIES_TYPE = None,
           use_names: Union[bool, Iterable[str]] = None,
           use_type_hints: Union[bool, Iterable[str]] = None
           ) -> F: ...


@overload
def inject(*,  # noqa: E704  # pragma: no cover
           dependencies: DEPENDENCIES_TYPE = None,
           use_names: Union[bool, Iterable[str]] = None,
           use_type_hints: Union[bool, Iterable[str]] = None
           ) -> Callable[[F], F]: ...


@API.public
def inject(func: AnyF = None,
           *,
           dependencies: DEPENDENCIES_TYPE = None,
           use_names: Union[bool, Iterable[str]] = None,
           use_type_hints: Union[bool, Iterable[str]] = None
           ) -> AnyF:
    """
    Inject the dependencies into the function lazily, they are only retrieved
    upon execution. As several options can apply to the same argument, the priority is
    defined as:

    1. Dependencies declared explicitly if any declared with :code:`dependencies`.
    2. Type hints (unless deactivated through :code:`use_type_hints`)
    3. Argument names if specified with :code:`use_names`

    .. doctest:: core_inject

        >>> from antidote import inject
        >>> # All possibilities for dependency argument.
        ... @inject(dependencies=None)  # default
        ... def f(a):
        ...     pass  # a = <not injected>
        >>> @inject(dependencies=dict(b='dependency'))
        ... def f(a, b):
        ...     pass  # a, b = <not injected>, world.get('dependency')
        >>> @inject(dependencies=[None, 'dependency'])  # Nothing will be injected a
        ... def f(a, b):
        ...     pass  # a, b = <not injected>, world.get('dependency')
        >>> @inject(dependencies=lambda arg: 'dependency' if arg.name == 'b' else None)
        ... def f(a, b):
        ...     pass  # a, b = <not injected>, world.get('dependency')
        >>> @inject(dependencies="conf:{arg_name}")
        ... def f(a):
        ...     pass  # a = world.get('conf:a')
        >>> # All possibilities for use_names argument.
        ... @inject(use_names=False)  # default
        ... def f(a):
        ...     pass  # a = <not injected>
        >>> @inject(use_names=True)
        ... def f(a):
        ...     pass  # a = world.get('a')
        >>> @inject(use_names=['b'])
        ... def f(a, b):
        ...     pass  # a, b = <not injected>, world.get('b')
        >>> # All possibilities for use_type_hints argument.
        ... class Service:
        ...     pass
        >>> @inject(use_type_hints=True)  # default
        ... def f(a: Service):
        ...     pass  # a = world.get(Service)
        >>> @inject(use_type_hints=['b'])
        ... def f(a: Service, b: Service):
        ...     pass  # a, b = <not injected>, world.get(Service)
        >>> @inject(use_type_hints=False)
        ... def f(a: Service):
        ...     pass  # a = <not injected>

    Args:
        func: Callable to be wrapped. Can also be used on static methods or class methods.
        dependencies: Explicit definition of the dependencies which overrides
            :code:`use_names` and :code:`use_type_hints`. Defaults to :py:obj:`None`.
            Can be one of:

            - Mapping from argument name to its dependency
            - Sequence of dependencies which will be mapped with the position
              of the arguments. :py:obj:`None` can be used as a placeholder.
            - Callable which receives :py:class:`~.Arg` as arguments and should
              return the matching dependency. :py:obj:`None` should be used for
              arguments without dependency.
            - String which must have :code:`{arg_name}` as format parameter
        use_names: Whether or not the arguments' name should be used as their
            respective dependency. An iterable of argument names may also be
            supplied to activate this feature only for those. Defaults to :code:`False`.
        use_type_hints: Whether or not the type hints should be used as the arguments
            dependency. An iterable of argument names may also be supplied to activate
            this feature only for those. Any type hints from the builtins (str, int...)
            or the typing (except :py:class:`~typing.Optional`) are ignored. It overrides
            :code:`use_names`. Defaults to :code:`True`.

    Returns:
        The decorator to be applied or the injected function if the
        argument :code:`func` was supplied.

    """
    if func is None:
        return raw_inject(dependencies=dependencies,
                          use_names=use_names,
                          use_type_hints=use_type_hints)
    else:
        return raw_inject(func,
                          dependencies=dependencies,
                          use_names=use_names,
                          use_type_hints=use_type_hints)


@API.public  # Function will be kept in sync with @inject, so you may use it.
def validate_injection(dependencies: DEPENDENCIES_TYPE = None,
                       use_names: Union[bool, Iterable[str]] = None,
                       use_type_hints: Union[bool, Iterable[str]] = None) -> None:
    if not (dependencies is None
            or isinstance(dependencies, (str, c_abc.Sequence, c_abc.Mapping))
            or callable(dependencies)):
        raise TypeError(
            f"dependencies can be None, a mapping of arguments names to dependencies, "
            f"a sequence of dependencies, a function or a string, "
            f"not a {type(dependencies)!r}"
        )
    if isinstance(dependencies, str):
        if "{arg_name}" not in dependencies:
            raise ValueError("Missing formatting parameter {arg_name} in dependencies. "
                             "If you really want a constant injection, "
                             "consider using a defaultdict.")
    if isinstance(dependencies, c_abc.Mapping):
        if not all(isinstance(k, str) for k in dependencies.keys()):
            raise TypeError("Dependencies keys must be argument names (str)")

    if not (use_names is None or isinstance(use_names, (bool, c_abc.Iterable))):
        raise TypeError(
            f"use_names must be either a boolean or a whitelist of argument names, "
            f"not {type(use_names)!r}.")
    if isinstance(use_names, c_abc.Iterable):
        if not all(isinstance(arg_name, str) for arg_name in use_names):
            raise TypeError("use_names must be list of argument names (str) or a boolean")

    if not (use_type_hints is None or isinstance(use_type_hints,
                                                 (bool, c_abc.Iterable))):
        raise TypeError(
            f"use_type_hints must be either a boolean or a whitelist of argument names, "
            f"not {type(use_type_hints)!r}.")
    if isinstance(use_type_hints, c_abc.Iterable):
        if not all(isinstance(arg_name, str) for arg_name in use_type_hints):
            raise TypeError(
                "use_type_hints must be list of argument names (str) or a boolean")
