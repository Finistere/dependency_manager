from typing import (Any, Callable, Dict, Hashable, Optional, TypeVar, Union, overload)

from ..._compatibility.typing import get_type_hints
from ..._internal import API, state
from ...core.container import (DependencyValue, Scope)
from ...utils import validated_scope

__sentinel = object()


@overload
def singleton(dependency: Hashable,  # noqa: E704  # pragma: no cover
              value: object
              ) -> None: ...


@overload
def singleton(dependency: Dict[Hashable, object]  # noqa: E704  # pragma: no cover
              ) -> None: ...


@API.public
def singleton(dependency: Union[Dict[Hashable, object], Hashable],
              value: object = __sentinel) -> None:
    """
    Override one or multiple dependencies with one/multiple singletons.

    .. doctest:: world_test_override_singleton

        >>> from antidote import world
        >>> world.singletons.add("test", 1)
        >>> world.get[int]("test")
        1
        >>> with world.test.clone():
        ...     world.test.override.singleton("test", 2)
        ...     world.test.override.singleton({'test': 2})
        ...     world.get[int]("test")
        2
        >>> # Overrides works only within the test world.
        ... world.get[int]("test")
        1

    Args:
        dependency: Singleton to declare, must be hashable. If a dict is provided, it'll
            be treated as a dictionary of singletons to add.
        value: Associated value for the dependency.

    """
    if value is __sentinel:
        if isinstance(dependency, dict):
            state.current_overridable_container().override_singletons(dependency)
        else:
            raise TypeError("If only a single argument is provided, "
                            "it must be a dictionary of singletons.")
    else:
        if isinstance(dependency, dict):
            raise TypeError("A dictionary cannot be used as a key.")
        state.current_overridable_container().override_singletons({dependency: value})


F = TypeVar('F', bound=Callable[..., Any])


@API.public
def factory(dependency: Hashable = None,
            *,
            singleton: bool = None,
            scope: Optional[Scope] = Scope.sentinel()
            ) -> Callable[[F], F]:
    """
    Override a dependency with the result of a factory. To be used as a function
    decorator. The result of the underlying function, the factory, will be used as the
    associated value of the dependency.

    .. doctest:: world_test_override_factory

        >>> from antidote import world
        >>> world.singletons.add("test", 1)
        >>> world.get[int]("test")
        1
        >>> with world.test.clone():
        ...     @world.test.override.factory('test', singleton=True)
        ...     def test():
        ...         return 2
        ...     world.get[int]("test")
        2
        >>> # Overrides works only within the test world.
        ... world.get[int]("test")
        1
        >>> class Dummy:
        ...     pass
        >>> with world.test.clone():
        ...     # If not specified explicitly, the return type hint will be used
        ...     # as the dependency.
        ...     @world.test.override.factory()
        ...     def test() -> Dummy:
        ...         return Dummy()
        ...     world.get[Dummy]()
        <Dummy ...>

    Args:
        dependency: Dependency to override.
        singleton: Whether the returned dependency  is a singleton or not. If yes,
            the factory will be called at most once and the result re-used. Mutually
            exclusive with :code:`scope`. Defaults to :py:obj:`True`.
        scope: Scope of the returned dependency. Mutually exclusive with
            :code:`singleton`. The scope defines if and how long the returned dependency
            will be cached. See :py:class:`~.core.container.Scope`. Defaults to
            :py:meth:`~.core.container.Scope.singleton`.

    .. note::

        As all override work as a single layer on top of the usual dependencies, if the
        dependency is already overridden as a singleton, the factory won't be called.
        Overrides done with a provider also have a higher priority. See
        :py:mod:`.world.test.override`.

    Returns:
        The decorated function, unchanged.
    """
    scope = validated_scope(scope, singleton, default=None)

    def decorate(f: F) -> F:
        if not callable(f):
            raise TypeError(f"factory must be a callable, not a {type(f)}")
        if dependency is None:
            output = get_type_hints(f).get('return')
            if output is None:
                raise ValueError("Either the dependency argument or the return type hint "
                                 "of the factory must be specified")
        else:
            output = dependency
        state.current_overridable_container() \
            .override_factory(output, factory=f, scope=scope)
        return f

    return decorate


P = TypeVar('P', bound=Callable[[Any], Optional[DependencyValue]])


@API.public
def provider() -> Callable[[P], P]:
    """
    Function decorator used to declare a simplified provider to override some
    dependencies. The function will be called for each dependency and should
    return :py:class:`.core.DependencyValue` if it can be provided or :py:obj:`None`
    if not.

    .. doctest:: world_test_override_provider

        >>> from antidote import world, Scope
        >>> from antidote.core import DependencyValue
        >>> world.singletons.add("test", 1)
        >>> world.get[int]("test")
        1
        >>> with world.test.clone():
        ...     @world.test.override.provider()
        ...     def test(dependency):
        ...         if dependency == 'test':
        ...             return DependencyValue(2, scope=Scope.singleton())
        ...     world.get[int]("test")
        2
        >>> # Overrides works only within the test world.
        ... world.get[int]("test")
        1

    .. note::

        As all override work as a single layer on top of the usual dependencies, singleton
        overrides won't pass through the provider. See :py:mod:`.world.test.override`.

    .. warning::

        Currently, provider overrides won't appear in :py:func:`.world.debug`.

    Returns:
        Function decorator.
    """

    def decorate(p: P) -> P:
        if not callable(p):
            raise TypeError(f"provider must be a callable, not {type(p)}")
        state.current_overridable_container().override_provider(p)
        return p

    return decorate
