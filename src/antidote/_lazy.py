import weakref
from typing import Callable, Dict, Optional, TYPE_CHECKING, Tuple, Union, cast

from ._compatibility.typing import final
from ._internal import API
from ._internal.utils import FinalImmutable, debug_repr, short_id
from ._providers import Lazy
from .core import Container, DependencyDebug, DependencyValue, Scope

if TYPE_CHECKING:
    from .lazy import LazyMethodCall


@API.private
@final
class LazyCallWithArgsKwargs(FinalImmutable, Lazy):
    """
    :meta private:
    """
    __slots__ = ('func', '_scope', '_args', '_kwargs')
    func: Callable[..., object]
    _scope: Optional[Scope]
    _args: Tuple[object, ...]
    _kwargs: Dict[str, object]

    def __antidote_debug_repr__(self) -> str:
        s = f"Lazy: {debug_repr(self.func)}(*{self._args}, **{self._kwargs})"
        if self._scope is not None:
            s += f"  #{short_id(self)}"
        return s

    def debug_info(self) -> DependencyDebug:
        return DependencyDebug(self.__antidote_debug_repr__(),
                               scope=self._scope,
                               wired=[self.func])

    def lazy_get(self, container: Container) -> DependencyValue:
        return DependencyValue(self.func(*self._args, **self._kwargs),
                               scope=self._scope)


@API.private
@final
class LazyMethodCallWithArgsKwargs(FinalImmutable):
    """
    :meta private:
    """
    __slots__ = ('_method_name', '_scope', '_args', '_kwargs', '__cache_attr')
    _method_name: str
    _scope: Optional[Scope]
    _args: Tuple[object, ...]
    _kwargs: Dict[str, object]
    __cache_attr: str

    def __init__(self,
                 method_name: str,
                 scope: Optional[Scope],
                 args: Tuple[object, ...],
                 kwargs: Dict[str, object]
                 ) -> None:
        super().__init__(method_name, scope, args, kwargs,
                         f"__antidote_dependency_{hex(id(self))}")

    def __get__(self, instance: object, owner: type) -> object:
        if instance is None:
            try:
                return getattr(owner, self.__cache_attr)
            except AttributeError:
                dependency = LazyMethodCallDependency(self, weakref.ref(owner))
                setattr(owner, self.__cache_attr, dependency)
                return dependency
        return getattr(instance, self._method_name)(*self._args, **self._kwargs)

    def __str__(self) -> str:
        s = f"Lazy Method: {self._method_name}(*{self._args}, **{self._kwargs})"
        if self._scope is not None:
            s += f"  #{short_id(self)}"
        return s


@API.private
@final
class LazyMethodCallDependency(FinalImmutable, Lazy):
    """
    :meta private:
    """
    __slots__ = ('__descriptor', '__owner_ref')
    __descriptor: 'Union[LazyMethodCall, LazyMethodCallWithArgsKwargs]'
    __owner_ref: 'weakref.ReferenceType[type]'

    def debug_info(self) -> DependencyDebug:
        owner = self.__owner_ref()
        assert owner is not None
        descriptor = cast('LazyMethodCall', self.__descriptor)
        return DependencyDebug(str(descriptor),
                               scope=descriptor._scope,
                               wired=[getattr(owner, descriptor._method_name)],
                               dependencies=[owner])

    def lazy_get(self, container: Container) -> DependencyValue:
        owner = self.__owner_ref()
        assert owner is not None
        descriptor = cast('LazyMethodCall', self.__descriptor)
        return DependencyValue(descriptor.__get__(container.get(owner), owner),
                               scope=descriptor._scope)
