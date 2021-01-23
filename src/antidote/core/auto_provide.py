import inspect
from typing import (Any, Callable, TypeVar, overload)

from .injection import inject
from .wiring import wire
from .._internal import API

F = TypeVar('F', bound=Callable[..., Any])


@overload
def auto_provide(__obj: staticmethod  # noqa: E704  # pragma: no cover
                 ) -> staticmethod: ...


@overload
def auto_provide(__obj: classmethod) -> classmethod: ...  # noqa: E704  # pragma: no cover


@overload
def auto_provide(__obj: F) -> F: ...  # noqa: E704  # pragma: no cover


@API.public
def auto_provide(__obj: Any = None) -> Any:
    """
    Wrapper of :py:func:`.inject` with :code:`auto_provide=True` by default. Meaning
    that it'll try to inject dependencies based on the type hints contrary to
    :py:func:`.inject` where everything must be explicitly specified.


    .. doctest:: core_inject

        >>> from antidote import world, Service
        >>> class MyService(Service):
        ...     pass
        >>> @auto_provide
        ... def f(a: MyService):
        ...     pass
        >>> # is equivalent to:
        ... @inject(auto_provide=True)
        ... def f(a: MyService):
        ...     pass  # a = world.get(MyService)

    Args:
        func: Callable to be wrapped. Can also be used on static methods or class methods.
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

    Returns:
        The decorator to be applied or the injected function if the
        argument :code:`func` was supplied.
    """

    if isinstance(__obj, type) and inspect.isclass(__obj):
        return wire(__obj, auto_provide=True)
    elif callable(__obj) or isinstance(__obj, (classmethod, staticmethod)):
        return inject(__obj, auto_provide=True)

    raise TypeError(f"Only classes, methods and functions can be wired, "
                    f"not {type(__obj)}")
