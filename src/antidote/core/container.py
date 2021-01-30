import threading
from collections import deque
from contextlib import contextmanager
from typing import (Callable, Deque, Dict, Hashable, Iterator, List, Mapping, Optional,
                    Sequence, TYPE_CHECKING, Tuple, Type)
from weakref import ReferenceType, ref

from .exceptions import (DependencyCycleError, DependencyInstantiationError,
                         DependencyNotFoundError, DuplicateDependencyError,
                         FrozenWorldError)
from .._compatibility.typing import final
from .._internal import API
from .._internal.stack import DependencyStack
from .._internal.utils import FinalImmutable

if TYPE_CHECKING:
    from .utils import DependencyDebug

# PRIVATE
_CONTAINER_REF_ATTR = "_antidote__container_ref"


@API.public
@final
class Scope(FinalImmutable):
    """
    Used to identify a specific scope for dependencies. The scope of a dependency defines
    when the dependency value is valid or not. Or said differently, for how long it is
    valid. A singleton is valid forever, and no scope at all means that a new dependency
    value needs to be retrieved every time.

    Scopes can be create through :py:func:`.world.scopes.new`. The name is only used to
    have a friendly identifier when debugging.

    .. doctest:: core_container_scope

        >>> from antidote import world
        >>> REQUEST_SCOPE = world.scopes.new('request')

    To use the newly created scope, use :code:`scope` parameters:

    .. doctest:: core_container_scope

        >>> from antidote import Service
        >>> class Dummy(Service):
        ...     __antidote__ = Service.Conf(scope=REQUEST_SCOPE)

    As :code:`Dummy` has been defined with a custom scope, the dependency value will
    be kep as long as :code:`REQUEST_SCOPE` stays valid. That is to say, until you reset
    it with :py:func:`.world.scopes.reset`:

    .. doctest:: core_container_scope

        >>> dummy = world.get[Dummy]()
        >>> dummy is world.get(Dummy)
        True
        >>> world.scopes.reset(REQUEST_SCOPE)
        >>> dummy is world.get(Dummy)
        False

    .. note::

        You probably noticed that dependencies supporting scopes always offer both
        :code:`singleton` and :code:`scope` arguments. Those are mutually exclusive.
        The reason behind this is simply due to the nature of scopes. Scopes are hard
        to get right ! For example, what should happen with a service in a scope A
        which required a dependency in scope B when B resets ? What if the service kept
        the dependency as an attribute ? There are no good answers for this, hence
        scopes are a pretty advanced feature which can cause inconsistencies. Moreover
        they do have a performance impact. But at the same time, scopes aren't uncommon.
        In a webapp you'll typically need soon enough a request scope. So it shouldn't
        be hard to use it.

        So to have easy to use scopes while keeping them under the radar until you
        actually need them, Antidote exposes both :code:`singleton` and :code:`scope`
        arguments.

    """
    __slots__ = ('name',)
    name: str

    def __repr__(self) -> str:
        return f"Scope(name='{self.name}')"

    @staticmethod
    @API.public
    def singleton() -> 'Scope':
        """
        Using this scope or specifying :code:`singleton=True` is equivalent.

        Returns:
            Singleton scope (unique object).
        """
        return _SCOPE_SINGLETON

    @staticmethod
    @API.public
    def sentinel() -> 'Scope':
        """
        For functions having both :code:`singleton` and :code:`scope` argument, validation
        of those is done with :py:func:`~.utils.validated_scope`. To correctly identify
        if the scope was actually set by the user, we're using this sentinel scope as the
        default value.

        Returns:
            Sentinel scope (unique object).
        """
        return _SCOPE_SENTINEL


# Use Scope.singleton() instead.
# API.private
_SCOPE_SINGLETON = Scope('singleton')
_SCOPE_SENTINEL = Scope('__sentinel__')


@API.public
@final
class DependencyValue(FinalImmutable):
    """
    Simple wrapper of the dependency value given by a
    :py:class:`~.provider.Provider`.
    """
    __slots__ = ('unwrapped', 'scope')
    unwrapped: object
    """Actual dependency value."""
    scope: Optional[Scope]
    """Scope of the dependency."""

    def __init__(self,
                 value: object,
                 *,
                 scope: Optional[Scope] = None) -> None:
        """
        Args:
            value: Actual dependency value.
            scope: Scope of the dependency.
        """
        assert scope is not _SCOPE_SENTINEL
        super().__init__(unwrapped=value, scope=scope)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, DependencyValue) \
               and self.unwrapped == other.unwrapped \
               and self.scope is other.scope  # noqa: E126

    def is_singleton(self) -> bool:
        return self.scope is _SCOPE_SINGLETON


@API.public
class Container:
    """
    Public interface of the container used by Antidote to handles all
    dependencies. Used in a :py:class:`~.provider.Provider` to access other
    dependencies.
    """

    def get(self, dependency: Hashable) -> object:
        """
        Retrieves given dependency or raises a
        :py:exc:`~..exceptions.DependencyNotFoundError`.

        Args:
            dependency: Dependency to be retrieved.

        Returns:
            The dependency instance.
        """
        raise NotImplementedError()  # pragma: no cover

    def provide(self, dependency: Hashable) -> DependencyValue:
        """
        Similar to :py:meth:`~.get` it will retrieve a dependency. However it will
        be wrapped in a :py:class:`~.DependencyValue` if found. If not
        :py:obj:`None` will be returned. This allows to get additional information such
        as whether the dependency is a singleton or not.

        Args:
            dependency: Dependency to be retrieved.

        Returns:
            wrapped dependency instance.

        """
        raise NotImplementedError()  # pragma: no cover


###########
# PRIVATE #
###########

@API.private
class RawProvider:
    """
    Abstract base class for a Provider.

    Use either :py:class:`~.core.provider.Provider` or
    :py:class:`~.core.provider.StatelessProvider` which are easier to implement.

    :meta private:
    """

    def __init__(self) -> None:
        setattr(self, _CONTAINER_REF_ATTR, None)

    def clone(self, keep_singletons_cache: bool) -> 'RawProvider':
        raise NotImplementedError()  # pragma: no cover

    def exists(self, dependency: Hashable) -> bool:
        raise NotImplementedError()  # pragma: no cover

    def maybe_provide(self, dependency: Hashable, container: Container
                      ) -> Optional[DependencyValue]:
        raise NotImplementedError()  # pragma: no cover

    def maybe_debug(self, dependency: Hashable) -> 'Optional[DependencyDebug]':
        raise NotImplementedError()  # pragma: no cover

    @API.private
    @final
    @contextmanager
    def _bound_container_locked(self, *, freezing: bool = False) -> Iterator[None]:
        container = self.__bound_container()
        if container is not None:
            with container.locked(freezing=freezing):
                yield
        else:
            yield

    @API.private
    @final
    def _bound_container_raise_if_exists(self, dependency: Hashable) -> None:
        container = self.__bound_container()
        if container is not None:
            container.raise_if_exists(dependency)
        else:
            if self.exists(dependency):
                raise DuplicateDependencyError(
                    f"{dependency} has already been registered in {type(self)}")

    @API.private
    def __bound_container(self) -> 'Optional[RawContainer]':
        container_ref: 'ReferenceType[RawContainer]' = getattr(self,
                                                               _CONTAINER_REF_ATTR)
        if container_ref is not None:
            container = container_ref()
            assert container is not None, "Bound container does not exist anymore."
            return container
        return None

    # API.private
    @final
    @property
    def is_registered(self) -> bool:
        return getattr(self, _CONTAINER_REF_ATTR) is not None


@API.private  # Not meant for direct use. You MUST go through world to manipulate it.
class RawContainer(Container):
    def __init__(self) -> None:
        self._dependency_stack = DependencyStack()
        self._registration_lock = threading.RLock()
        self._instantiation_lock = threading.RLock()

        self.__frozen = False
        self.__singletons: Dict[object, object] = dict()
        self.__scopes: Dict[Scope, Dict[object, object]] = dict()
        self.__providers: List[RawProvider] = list()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(providers={', '.join(map(str, self.__providers))})"

    @staticmethod
    def with_same_providers_and_scopes(original: 'RawContainer') -> 'RawContainer':
        container = RawContainer()
        for provider in original.providers:
            container.add_provider(type(provider))
        container.__scopes = {scope: dict() for scope in original.__scopes.keys()}
        return container

    @property
    def scopes(self) -> Sequence[Scope]:
        return list(self.__scopes.keys())

    @property
    def providers(self) -> Sequence[RawProvider]:
        return self.__providers.copy()

    @contextmanager
    def locked(self, *, freezing: bool = False) -> Iterator[None]:
        assert isinstance(freezing, bool)
        with self._registration_lock, self._instantiation_lock:
            if freezing and self.__frozen:
                raise FrozenWorldError()
            yield

    def freeze(self) -> None:
        with self._registration_lock:
            if self.__frozen:
                raise FrozenWorldError("Container is already frozen !")
            self.__frozen = True

    def add_provider(self, provider_cls: Type[RawProvider]) -> None:
        with self.locked(freezing=True):
            assert all(provider_cls != type(p) for p in self.__providers)
            provider = provider_cls()
            setattr(provider, _CONTAINER_REF_ATTR, ref(self))
            self.__providers.append(provider)
            self.__singletons[provider_cls] = provider

    def add_singletons(self, dependencies: Mapping[Hashable, object]) -> None:
        with self.locked(freezing=True):
            for k, v in dependencies.items():
                self.raise_if_exists(k)
            self.__singletons.update(dependencies)

    def create_scope(self, name: str) -> Scope:
        scope = Scope(name)  # Name is only a helper, not a identifier by itself.
        with self.locked(freezing=True):
            assert all(s.name != name for s in self.__scopes.keys())
            assert len(self.__scopes) < 255  # Consistency with Cython.
            self.__scopes[scope] = dict()
        return scope

    def reset_scope(self, scope: Scope) -> None:
        with self._instantiation_lock:
            self.__scopes[scope].clear()

    def raise_if_exists(self, dependency: Hashable) -> None:
        with self._registration_lock:
            if dependency in self.__singletons:
                raise DuplicateDependencyError(
                    f"{dependency!r} has already been defined as a singleton pointing "
                    f"to {self.__singletons[dependency]}")

            for provider in self.__providers:
                if provider.exists(dependency):
                    debug = provider.maybe_debug(dependency)
                    message = f"{dependency!r} has already been declared " \
                              f"in {type(provider)}"
                    if debug is None:
                        raise DuplicateDependencyError(message)
                    else:
                        raise DuplicateDependencyError(message + f"\n{debug.info}")

    def clone(self,
              *,
              keep_singletons: bool = False,
              keep_scopes: bool = False) -> 'OverridableRawContainer':
        with self.locked():
            clone = OverridableRawContainer()
            clone.__frozen = True
            if keep_singletons:
                clone.__singletons = self.__singletons.copy()

            clone.__scopes = {
                scope: dependencies.copy() if keep_scopes else dict()
                for scope, dependencies in self.__scopes.items()
            }

            for p in self.__providers:
                p_clone = p.clone(keep_singletons_cache=keep_singletons)
                if p_clone is p \
                        or getattr(p_clone, _CONTAINER_REF_ATTR, None) is not None:
                    raise RuntimeError(
                        "A Provider should always return a fresh "
                        "instance when copy() is called.")

                setattr(p_clone, _CONTAINER_REF_ATTR, ref(clone))
                clone.__providers.append(p_clone)
                clone.__singletons[type(p)] = p_clone

            return clone

    def debug(self, dependency: Hashable) -> 'DependencyDebug':
        from .._internal.utils.debug import debug_repr
        from .utils import DependencyDebug

        with self.locked():
            for p in self.__providers:
                debug = p.maybe_debug(dependency)
                if debug is not None:
                    return debug
            try:
                value = self.__singletons[dependency]
                return DependencyDebug(f"Singleton: {debug_repr(dependency)} "
                                       f"-> {value!r}",
                                       scope=Scope.singleton())
            except KeyError:
                raise DependencyNotFoundError(dependency)

    def provide(self, dependency: Hashable) -> DependencyValue:
        try:
            return DependencyValue(self.__singletons[dependency],
                                   scope=Scope.singleton())
        except KeyError:
            pass
        return self._safe_provide(dependency)

    def get(self, dependency: Hashable) -> object:
        try:
            return self.__singletons[dependency]
        except KeyError:
            pass
        return self._safe_provide(dependency).unwrapped

    def _safe_provide(self, dependency: Hashable) -> DependencyValue:
        with self._instantiation_lock:
            try:
                try:
                    return DependencyValue(self.__singletons[dependency],
                                           scope=Scope.singleton())
                except KeyError:
                    pass

                for scope, dependencies in self.__scopes.items():
                    try:
                        return DependencyValue(dependencies[dependency],
                                               scope=scope)
                    except KeyError:
                        pass

                with self._dependency_stack.instantiating(dependency):
                    for provider in self.__providers:
                        value = provider.maybe_provide(dependency, self)
                        if value is not None:
                            if value.is_singleton():
                                self.__singletons[dependency] = value.unwrapped
                            elif value.scope is not None:
                                self.__scopes[value.scope][dependency] = value.unwrapped

                            return value

            except DependencyCycleError:
                raise

            except DependencyInstantiationError as e:
                if self._dependency_stack.depth == 0:
                    raise DependencyInstantiationError(dependency) from e
                else:
                    raise

            except Exception as e:
                raise DependencyInstantiationError(
                    dependency,
                    self._dependency_stack.to_list()) from e

            raise DependencyNotFoundError(dependency)


class OverridableRawContainer(RawContainer):
    def __init__(self) -> None:
        from collections import defaultdict
        super().__init__()
        self.__override_lock = threading.RLock()
        # Used to differentiate singletons from the overrides and the "normal" ones.
        self.__singletons_override: Dict[Hashable, object] = dict()
        self.__scopes_override: Dict[Scope, Dict[Hashable, object]] = defaultdict(dict)
        self.__factory_overrides: Dict[
            Hashable, Tuple[Callable[[], object], Optional[Scope]]] = {}
        self.__provider_overrides: Deque[
            Callable[[Hashable], Optional[DependencyValue]]] = deque()

    def clone(self,
              *,
              keep_singletons: bool = False,
              keep_scopes: bool = False) -> 'OverridableRawContainer':
        with self.locked():
            clone = super().clone(keep_singletons=keep_singletons,
                                  keep_scopes=keep_scopes)
            if keep_singletons:
                clone.__singletons_override = self.__singletons_override
            clone.__scopes_override = {
                scope: dependencies.copy() if keep_scopes else dict()
                for scope, dependencies in self.__scopes_override.items()
            }
            clone.__factory_overrides = self.__factory_overrides
            clone.__provider_overrides = self.__provider_overrides

            return clone

    def override_singletons(self, singletons: Dict[Hashable, object]) -> None:
        with self.__override_lock:
            self.__singletons_override.update(singletons)

    def override_factory(self,
                         dependency: Hashable,
                         *,
                         factory: Callable[[], object],
                         scope: Optional[Scope]) -> None:
        with self.__override_lock:
            try:
                del self.__singletons_override[dependency]
            except KeyError:
                pass
            for scope_dependencies in self.__scopes_override.values():
                try:
                    del scope_dependencies[dependency]
                except KeyError:
                    pass
            self.__factory_overrides[dependency] = (factory, scope)

    def override_provider(self,
                          provider: Callable[[Hashable], Optional[DependencyValue]]
                          ) -> None:
        with self.__override_lock:
            self.__provider_overrides.appendleft(provider)  # latest provider wins

    def reset_scope(self, scope: Scope) -> None:
        super().reset_scope(scope)
        self.__scopes_override[scope] = dict()

    def debug(self, dependency: Hashable) -> 'DependencyDebug':
        from .._internal.utils.debug import debug_repr
        from .utils import DependencyDebug

        with self.__override_lock:
            try:
                value = self.__singletons_override[dependency]
            except KeyError:
                pass
            else:
                return DependencyDebug(f"Override/Singleton: {debug_repr(dependency)} "
                                       f"-> {value!r}",
                                       scope=Scope.singleton())
            try:
                (factory, scope) = self.__factory_overrides[dependency]
            except KeyError:
                pass
            else:
                return DependencyDebug(f"Override/Factory: {debug_repr(dependency)} "
                                       f"-> {debug_repr(factory)}",
                                       scope=scope)

        return super().debug(dependency)

    def provide(self, dependency: Hashable) -> DependencyValue:
        return self._safe_provide(dependency)

    def get(self, dependency: Hashable) -> object:
        return self._safe_provide(dependency).unwrapped

    def _safe_provide(self, dependency: Hashable) -> DependencyValue:
        with self._instantiation_lock, self.__override_lock:
            with self._dependency_stack.instantiating(dependency):
                try:
                    return DependencyValue(self.__singletons_override[dependency],
                                           scope=Scope.singleton())
                except KeyError:
                    pass

                scope: Optional[Scope]
                for scope, dependencies in self.__scopes_override.items():
                    try:
                        return DependencyValue(dependencies[dependency], scope=scope)
                    except KeyError:
                        pass

                try:
                    for provider in self.__provider_overrides:
                        value = provider(dependency)
                        if value is not None:
                            if value.scope is Scope.singleton():
                                self.__singletons_override[dependency] = value.unwrapped
                            elif value.scope is not None:
                                self.__scopes_override[value.scope][dependency] = \
                                    value.unwrapped
                            return value

                    try:
                        (factory, scope) = self.__factory_overrides[dependency]
                    except KeyError:
                        pass
                    else:
                        obj = factory()
                        if scope is Scope.singleton():
                            self.__singletons_override[dependency] = obj
                        elif scope is not None:
                            self.__scopes_override[scope][dependency] = obj
                        return DependencyValue(obj, scope=scope)

                except DependencyCycleError:
                    raise

                except Exception as e:
                    raise DependencyInstantiationError(dependency) from e

            return super()._safe_provide(dependency)
