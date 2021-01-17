import functools
import inspect
from typing import Callable, TypeVar, cast

from ._compatibility.typing import Protocol
from ._implementation import ImplementationWrapper
from ._internal import API
from ._providers import IndirectProvider
from .core import inject
from .utils import validate_provided_class

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
                   permanent: bool = True
                   ) -> Callable[[F], ImplementationProtocol[F]]:
    """
    Function decorator which decides which implementation should be used for
    :code:`interface`.

    The underlying function is expected to return a dependency, typically the class of
    the implementation when defined as a service. You may also use a factory dependency.

    The function will not be wired, you'll need to do it yourself if you need it.

    .. doctest:: helpers_implementation

        >>> from antidote import implementation, Service, factory, world
        >>> class Database:
        ...     pass
        >>> class PostgreSQL(Database, Service):
        ...     pass
        >>> class MySQL(Database):
        ...     pass
        >>> @factory
        ... def build_mysql() -> MySQL:
        ...     return MySQL()
        >>> @implementation(Database, dependencies=['choice'])
        ... def local_db(choice: str):
        ...     if choice == 'a':
        ...         return PostgreSQL  # One could also use PostgreSQL.with_kwargs(...)
        ...     else:
        ...         return MySQL @ build_mysql  # or MySQL @ build_mysql.with_kwargs(...)
        >>> world.singletons.add('choice', 'a')
        >>> world.get(Database @ local_db)
        <PostgreSQL ...>
        >>> # Changing choice doesn't matter anymore as the implementation is permanent.
        ... with world.test.clone():
        ...     world.test.override.singleton('choice', 'b')
        ...     world.get(Database @ local_db)
        <PostgreSQL ...>

    Args:
        interface: Interface for which an implementation will be provided
        permanent: Whether the function should be called each time the interface is needed
            or not. Defaults to :py:obj:`True`.

    Returns:
        The decorated function, unmodified.
    """
    if not isinstance(permanent, bool):
        raise TypeError(f"permanent must be a bool, not {type(permanent)}")
    if not inspect.isclass(interface):
        raise TypeError(f"interface must be a class, not {type(interface)}")

    @inject
    def register(func: F,
                 indirect_provider: IndirectProvider = None
                 ) -> ImplementationProtocol[F]:
        assert indirect_provider is not None

        if inspect.isfunction(func):

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
