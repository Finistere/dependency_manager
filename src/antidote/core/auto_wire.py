import inspect
from typing import (Any, Callable, TypeVar, overload)

from .injection import inject
from .wiring import wire
from .._internal import API

F = TypeVar('F', bound=Callable[..., Any])


@overload
def auto_wire(__obj: staticmethod) -> staticmethod: ...


@overload
def auto_wire(__obj: classmethod) -> classmethod: ...


@overload
def auto_wire(__obj: F) -> F: ...


@overload
def auto_wire() -> Callable[[F], F]: ...


@API.public
def auto_wire(__obj: Any = None) -> Any:
    """
    Wrapper of :py:func:`.inject` with :code:`use_type_hints=True` by default. Meaning
    that it'll try to inject dependencies based on the type hints contrary to
    :py:func:`.inject` where everything must be explicitly specified.


    .. doctest:: core_inject

        >>> from antidote import world, Service
        >>> class MyService(Service):
        ...     pass
        >>> @auto_wire
        ... def f(a: MyService):
        ...     pass
        >>> # is equivalent to:
        ... @inject(use_type_hints=True)
        ... def f(a: MyService):
        ...     pass  # a = world.get(MyService)

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

    Returns:
        The decorator to be applied or the injected function if the
        argument :code:`func` was supplied.
    """

    def _auto_wire(obj: Any) -> Any:
        if isinstance(obj, type) and inspect.isclass(obj):
            return wire(obj, auto_wire=True)
        elif callable(obj) or isinstance(obj, (classmethod, staticmethod)):
            return inject(obj, use_type_hints=True)

        raise TypeError(f"Only classes, methods and functions can be wired, "
                        f"not {type(obj)}")

    return __obj and _auto_wire(__obj) or _auto_wire
