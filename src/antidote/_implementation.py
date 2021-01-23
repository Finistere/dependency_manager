import functools
import inspect
from typing import Callable, Hashable

from ._internal import API
from ._providers.indirect import ImplementationDependency


@API.private
class ImplementationWrapper:
    def __init__(self,
                 wrapped: Callable[..., object],
                 implementation_dependency: ImplementationDependency) -> None:
        self.__wrapped__ = wrapped
        self.__implementation_dependency = implementation_dependency
        functools.wraps(wrapped, updated=())(self)

    def __call__(self, *args: object, **kwargs: object) -> object:
        return self.__wrapped__(*args, **kwargs)

    def __rmatmul__(self, left_operand: Hashable) -> object:
        if left_operand is not self.__implementation_dependency.interface:
            interface = self.__implementation_dependency.interface
            raise ValueError(f"Unsupported interface {left_operand}, "
                             f"expected {interface}")
        return self.__implementation_dependency

    def __getattr__(self, item: str) -> object:
        return getattr(self.__wrapped__, item)


@API.private
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
