import collections.abc as c_abc
import inspect
from typing import (Any, Callable, Hashable, Iterable, Mapping, Optional, Sequence,
                    TypeVar, Union, overload)

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
    __slots__ = ('name', 'type_hint', 'type_hint_with_extras')
    name: str
    """Name of the argument"""
    type_hint: Any
    """Type hint of the argument if any"""
    type_hint_with_extras: Any
    """
    Type hint of the argument if any with include_extras=True, so with annotations.
    """


# API.experimental
DEPENDENCIES_TYPE = Optional[Union[
    Mapping[str, Hashable],  # {arg_name: dependency, ...}
    Sequence[Optional[Hashable]],  # (dependency for arg 1, ...)
    Callable[[Arg], Optional[Hashable]],  # arg -> dependency
    str  # str.format(arg_name=arg_name) -> dependency
]]


@overload
def inject(__func: staticmethod,  # noqa: E704  # pragma: no cover
           *,
           dependencies: DEPENDENCIES_TYPE = None,
           use_names: Union[bool, Iterable[str]] = None,
           auto_provide: Union[bool, Iterable[Hashable]] = None,
           strict_validation: bool = True
           ) -> staticmethod: ...


@overload
def inject(__func: classmethod,  # noqa: E704  # pragma: no cover
           *,
           dependencies: DEPENDENCIES_TYPE = None,
           use_names: Union[bool, Iterable[str]] = None,
           auto_provide: Union[bool, Iterable[Hashable]] = None,
           strict_validation: bool = True
           ) -> classmethod: ...


@overload
def inject(__func: F,  # noqa: E704  # pragma: no cover
           *,
           dependencies: DEPENDENCIES_TYPE = None,
           use_names: Union[bool, Iterable[str]] = None,
           auto_provide: Union[bool, Iterable[Hashable]] = None,
           strict_validation: bool = True
           ) -> F: ...


@overload
def inject(*,  # noqa: E704  # pragma: no cover
           dependencies: DEPENDENCIES_TYPE = None,
           use_names: Union[bool, Iterable[str]] = None,
           auto_provide: Union[bool, Iterable[Hashable]] = None,
           strict_validation: bool = True
           ) -> Callable[[F], F]: ...


@API.public
def inject(__func: AnyF = None,
           *,
           dependencies: DEPENDENCIES_TYPE = None,
           use_names: Union[bool, Iterable[str]] = None,
           auto_provide: Union[bool, Iterable[Hashable]] = None,
           strict_validation: bool = True
           ) -> AnyF:
    """
    Inject the dependencies into the function lazily, they are only retrieved
    upon execution. As several options can apply to the same argument, the priority is
    defined as:

    1. Annotated type hints (PEP-593)
    2. Dependencies declared explicitly if any declared with :code:`dependencies`.
    3. Class type hints if specified with :code:`auto_provide`.
    4. Argument names if specified with :code:`use_names`.

    .. doctest:: core_inject

        >>> from antidote import inject, Service, Provide
        >>> class A(Service):
        ...     pass
        >>> class B(Service):
        ...     pass
        >>> # PEP-593 annotation
        ... @inject
        ... def f(a: Provide[A]):
        ...     pass # a = world.get(A)
        >>> # All possibilities for dependency argument.
        >>> @inject(dependencies=None)  # default
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
        >>> # All possibilities for auto_provide argument.
        >>> @inject(auto_provide=True)
        ... def f(a: A):
        ...     pass  # a = world.get(A)
        >>> @inject(auto_provide=[B])
        ... def f(a: A, b: B):
        ...     pass  # a, b = <not injected>, world.get(B)
        >>> @inject(auto_provide=False)  # default
        ... def f(a: A):
        ...     pass  # a = <not injected>
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

    Args:
        __func: Callable to be wrapped. Can also be used on static methods or class
            methods.
        dependencies: Explicit definition of the dependencies which overrides
            :code:`use_names` and :code:`auto_provide`. Defaults to :py:obj:`None`.
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
        auto_provide: Whether or not the type hints should be used as the arguments
            dependency. An iterable of argument names may also be supplied to activate
            this feature only for those. Any type hints from the builtins (str, int...)
            or the typing (except :py:class:`~typing.Optional`) are ignored. It overrides
            :code:`use_names`. Defaults to :code:`False`.

    Returns:
        The decorator to be applied or the injected function if the
        argument :code:`func` was supplied.

    """

    from ._injection import raw_inject

    def decorate(f: AnyF) -> AnyF:
        return raw_inject(
            f,
            dependencies=dependencies,
            use_names=use_names if use_names is not None else False,
            auto_provide=auto_provide if auto_provide is not None else False,
            strict_validation=strict_validation)

    return __func and decorate(__func) or decorate


@API.public  # Function will be kept in sync with @inject, so you may use it.
def validate_injection(dependencies: DEPENDENCIES_TYPE = None,
                       use_names: Union[bool, Iterable[str]] = None,
                       auto_provide: Union[bool, Iterable[Hashable]] = None) -> None:
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
            raise ValueError("Missing formatting parameter {arg_name} in dependencies.")
    if isinstance(dependencies, c_abc.Mapping):
        if not all(isinstance(k, str) for k in dependencies.keys()):
            raise TypeError("Dependencies keys must be argument names (str)")

    if isinstance(use_names, str) \
            or not (use_names is None or isinstance(use_names, (bool, c_abc.Iterable))):
        raise TypeError(
            f"use_names must be either a boolean or a whitelist of argument names, "
            f"not {type(use_names)!r}.")

    # If we can iterate over it safely
    if isinstance(use_names, (list, set, tuple, frozenset)):
        if not all(isinstance(arg_name, str) for arg_name in use_names):
            raise TypeError("use_names must be list of argument names (str) or a boolean")

    if isinstance(auto_provide, str) \
            or not (auto_provide is None
                    or isinstance(auto_provide, (bool, c_abc.Iterable))):
        raise TypeError(
            f"auto_provide must be either a boolean or an iterable of classes, "
            f"not {type(auto_provide)!r}.")

    # If we can iterate over it safely
    if isinstance(auto_provide, (list, set, tuple, frozenset)):
        for cls in auto_provide:
            if not (isinstance(cls, type) and inspect.isclass(cls)):
                raise TypeError(f"auto_provide must be a boolean or an iterable of "
                                f"classes, but contains {cls!r} which is not a class.")
