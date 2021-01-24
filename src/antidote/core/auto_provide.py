import inspect
from typing import (Any, Callable, Iterable, TypeVar, Union, overload)

from .injection import DEPENDENCIES_TYPE, inject
from .wiring import wire
from .._internal import API

F = TypeVar('F', bound=Callable[..., Any])
AnyF = Union[Callable[..., Any], staticmethod, classmethod]


@overload
def auto_provide(__func: staticmethod,  # noqa: E704  # pragma: no cover
                 *,
                 dependencies: DEPENDENCIES_TYPE = None,
                 use_names: Union[bool, Iterable[str]] = None
                 ) -> staticmethod: ...


@overload
def auto_provide(__func: classmethod,  # noqa: E704  # pragma: no cover
                 *,
                 dependencies: DEPENDENCIES_TYPE = None,
                 use_names: Union[bool, Iterable[str]] = None) -> classmethod: ...


@overload
def auto_provide(__func: F,  # noqa: E704  # pragma: no cover
                 *,
                 dependencies: DEPENDENCIES_TYPE = None,
                 use_names: Union[bool, Iterable[str]] = None) -> F: ...


@overload
def auto_provide(*,  # noqa: E704  # pragma: no cover
                 dependencies: DEPENDENCIES_TYPE = None,
                 use_names: Union[bool, Iterable[str]] = None) -> Callable[[F], F]: ...


@API.public
def auto_provide(__func: AnyF = None,
                 *,
                 dependencies: DEPENDENCIES_TYPE = None,
                 use_names: Union[bool, Iterable[str]] = None) -> AnyF:
    """
    Wrapper of :py:func:`.inject` with :code:`auto_provide=True` by default. Meaning
    that it'll try to inject dependencies based on the type hints contrary to
    :py:func:`.inject` where everything must be explicitly specified.


    .. doctest:: core_inject

        >>> from antidote import world, Service, auto_provide
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

    if __func is None:  # For Mypy
        return inject(auto_provide=True,
                      dependencies=dependencies,
                      use_names=use_names)
    else:
        return inject(__func,
                      auto_provide=True,
                      dependencies=dependencies,
                      use_names=use_names)
