import functools
from typing import Callable, Dict, Hashable, List, Sequence, Union

from . import API
from .utils import FinalImmutable
from ..core.container import Container
from ..core.exceptions import DependencyNotFoundError

AnyF = Union[Callable[..., object], staticmethod, classmethod]

compiled = False


@API.private
class Injection(FinalImmutable):
    """
    Maps an argument name to its dependency and if the injection is required,
    which is equivalent to no default argument.
    """
    __slots__ = ('arg_name', 'required', 'dependency')
    arg_name: str
    required: bool
    dependency: Hashable


@API.private
class InjectionBlueprint(FinalImmutable):
    """
    Stores all the injections for a function.
    """
    __slots__ = ('injections',)
    injections: Sequence[Injection]

    def is_empty(self) -> bool:
        return all(injection.dependency is None for injection in self.injections)


@API.private
def build_wrapper(blueprint: InjectionBlueprint,
                  wrapped: AnyF,
                  skip_self: bool = False) -> 'InjectedWrapper':
    """Used for consistency with Cython implementation."""
    return InjectedWrapper(blueprint, wrapped, skip_self)


@API.private
def get_wrapper_dependencies(wrapper: Callable[..., object]) -> List[Hashable]:
    if not isinstance(wrapper, InjectedWrapper):
        raise TypeError(f"Argument must be an {InjectedWrapper}")

    blueprint: InjectionBlueprint = getattr(wrapper,
                                            f"_{InjectedWrapper.__name__}__blueprint")
    return [inj.dependency for inj in blueprint.injections if inj.dependency is not None]


@API.private
def is_wrapper(x: object) -> bool:
    return isinstance(x, InjectedWrapper)


@API.private
def get_wrapped(x: object) -> object:
    assert isinstance(x, InjectedWrapper)
    return x.__wrapped__


@API.private
class InjectedWrapper:
    """
    Wrapper which injects all the dependencies not supplied in the passed
    arguments. An InjectionBlueprint is used to store the mapping of the
    arguments to their dependency if any and if the injection is required.
    """

    def __init__(self,
                 blueprint: InjectionBlueprint,
                 wrapped: AnyF,
                 skip_self: bool = False):
        """
        Args:
            blueprint: Injection blueprint for the underlying function
            wrapped:  real function to be called
            skip_self:  whether the first argument must be skipped. Used internally
        """
        self.__blueprint = blueprint
        self.__wrapped__ = wrapped
        self.__injection_offset = 1 if skip_self else 0
        functools.wraps(wrapped, updated=())(self)  # type: ignore

    def __call__(self, *args: object, **kwargs: object) -> object:
        from .state import current_container
        kwargs = _inject_kwargs(
            current_container(),
            self.__blueprint,
            self.__injection_offset + len(args),
            kwargs
        )
        return self.__wrapped__(*args, **kwargs)  # type: ignore

    def __get__(self, instance: object, owner: type) -> object:
        return InjectedBoundWrapper(
            self.__blueprint,
            self.__wrapped__.__get__(instance, owner),  # type: ignore
            isinstance(self.__wrapped__, classmethod)
            or (not isinstance(self.__wrapped__, staticmethod) and instance is not None)
        )

    def __getattr__(self, item: str) -> object:
        return getattr(self.__wrapped__, item)


@API.private
class InjectedBoundWrapper(InjectedWrapper):
    """
    Behaves like Python bound methods. Unsure whether this is really necessary
    or not.
    """

    def __get__(self, instance: object, owner: type) -> object:
        return self  # pragma: no cover


@API.private
def _inject_kwargs(container: Container,
                   blueprint: InjectionBlueprint,
                   offset: int,
                   kwargs: Dict[str, object]) -> Dict[str, object]:
    """
    Does the actual injection of the dependencies. Used by InjectedCallableWrapper.
    """
    dirty_kwargs = False
    for injection in blueprint.injections[offset:]:
        if injection.dependency is not None and injection.arg_name not in kwargs:
            try:
                arg = container.get(injection.dependency)
                if not dirty_kwargs:
                    kwargs = kwargs.copy()
                    dirty_kwargs = True
                kwargs[injection.arg_name] = arg
            except DependencyNotFoundError:
                if injection.required:
                    raise

    return kwargs
