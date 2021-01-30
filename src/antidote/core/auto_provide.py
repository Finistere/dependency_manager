from typing import (Any, Callable, Iterable, TypeVar, Union, overload)

from .injection import DEPENDENCIES_TYPE, inject
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
    that arguments having a class type hints will be automatically injected if possible,
    contrary to :py:func:`.inject` where everything must be explicitly specified. It also
    supports :code:`use_names` and :code:`dependencies` which are passed to
    :py:func:`.inject`.

    .. note::

        The only goal of this function is to provide syntactic sugar for those that
        wnat to use :code:`auto_provide=True` everywhere.


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
        __func: Callable to be wrapped. Can also be used on static methods or
            class methods.
        dependencies: Passed on to :py:func:`.inject`.
        use_names: Passed on to :py:func:`.inject`.

    Returns:
        Function decorator or the injected function if the :code:`__func` was supplied.
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
