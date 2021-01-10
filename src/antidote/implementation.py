import functools
import inspect
from typing import Callable, Iterable, TypeVar, Union, cast

from ._compatibility.typing import Protocol
from ._implementation import ImplementationWrapper
from ._internal import API
from ._providers import IndirectProvider
from .core import inject, DEPENDENCIES_TYPE
from .utils import validate_injection, validate_provided_class

F = TypeVar('F', bound=Callable[[], object])


@API.private
class ImplementationProtocol(Protocol[F]):
    """
    :meta private:
    """

    def __rmatmul__(self, klass: type) -> object:
        pass  # pragma: no cover

    __call__: F


@API.public
def implementation(interface: type,
                   *,
                   permanent: bool = True,
                   auto_wire: bool = True,
                   dependencies: DEPENDENCIES_TYPE = None,
                   use_names: Union[bool, Iterable[str]] = None,
                   use_type_hints: Union[bool, Iterable[str]] = None
                   ) -> Callable[[F], ImplementationProtocol[F]]:
    """
    Function decorator which decides which implementation should be used for
    :code:`interface`.

    The underlying function is expected to return a dependency, typically the class of
    the implementation when defined as a service. You may also use a factory dependency.

    The function will not be wired, you'll need to do it yourself if you need it.

    .. doctest:: helpers_implementation

        >>> from antidote import implementation, Service, factory, world
        >>> class Interface:
        ...     pass
        >>> class A(Interface, Service):
        ...     pass
        >>> class B(Interface):
        ...     pass
        >>> @factory
        ... def build_b() -> B:
        ...     return B()
        >>> @implementation(Interface, dependencies=['choice'])
        ... def choose_interface(choice: str):
        ...     if choice == 'a':
        ...         return A  # One could also use A.with_kwargs(...)
        ...     else:
        ...         return B @ build_b  # or B @ build_b.with_kwargs(...)
        >>> world.singletons.add('choice', 'b')
        >>> world.get(Interface)
        <B ...>
        >>> # Changing choice doesn't matter anymore as the implementation is permanent.
        ... with world.test.clone():
        ...     world.test.override.singleton('choice', 'a')
        ...     world.get(Interface)
        <B ...>

    Args:
        interface: Interface for which an implementation will be provided
        permanent: Whether the function should be called each time the interface is needed
            or not. Defaults to :py:obj:`True`.
        auto_wire: Whether the function should have its arguments injected or not
            with :py:func:`~.injection.inject`.
        dependencies: Propagated to :py:func:`~.injection.inject`.
        use_names: Propagated to :py:func:`~.injection.inject`.
        use_type_hints: Propagated to :py:func:`~.injection.inject`.

    Returns:
        The decorated function, unmodified.
    """
    validate_injection(dependencies, use_names, use_type_hints)
    if not isinstance(permanent, bool):
        raise TypeError(f"permanent must be a bool, not {type(permanent)}")
    if not inspect.isclass(interface):
        raise TypeError(f"interface must be a class, not {type(interface)}")
    if not (auto_wire is None or isinstance(auto_wire, bool)):
        raise TypeError(f"auto_wire must be a boolean or None, not {type(auto_wire)}")

    @inject
    def register(func: F,
                 indirect_provider: IndirectProvider = None
                 ) -> ImplementationProtocol[F]:
        assert indirect_provider is not None

        if inspect.isfunction(func):
            if auto_wire:
                func = inject(func,
                              dependencies=dependencies,
                              use_names=use_names,
                              use_type_hints=use_type_hints)

            @functools.wraps(func)
            def impl() -> object:
                dep = func()
                validate_provided_class(dep, expected=interface)
                return dep

            dependency = indirect_provider.register_implementation(interface, impl,
                                                                   permanent=permanent)
        else:
            raise TypeError(f"implementation must be applied on a function, "
                            f"not a {type(func)}")
        return cast(ImplementationProtocol[F], ImplementationWrapper(func, dependency))

    return register
