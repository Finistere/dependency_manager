import collections.abc as c_abc
import inspect
from typing import (Any, Callable, cast, get_type_hints, Hashable, Iterable, Optional,
                    overload, Tuple, TypeVar, Union)

from ._compatibility.typing import final, Protocol
from ._factory import FactoryMeta, LambdaFactory, PreBuild
from ._internal import API
from ._internal.utils import Copy, FinalImmutable
from ._providers import FactoryProvider, Tag, TagProvider
from .core.injection import DEPENDENCIES_TYPE, inject
from .core.wiring import Wiring, WithWiringMixin

F = TypeVar('F', bound=Callable[..., Any])


@API.private
class FactoryProtocol(Protocol[F]):
    """
    :meta private:
    """

    def __rmatmul__(self, dependency: Hashable) -> object:
        pass  # pragma: no cover

    def with_kwargs(self, **kwargs: object) -> PreBuild:
        pass  # pragma: no cover

    __call__: F


@API.public
class Factory(metaclass=FactoryMeta, abstract=True):
    """
    Abstract base class for a factory which provides a single dependency. The provided
    dependency is defined through the type annotation of :py:meth:`.__call__` which will
    be used to create the dependency.

    The factory instance will only be instantiated once, whether the dependency is a
    singleton, the default, or not. Both :py:meth:`.__init__` and :py:meth:`.__call__`
    are wired by default.

    To retrieve the dependency from Antidote you need to use a specific syntax
    :code:`dependency @ factory` as presented in the following examples. The goal of it is
    twofold:

    - Ensure that the factory is loaded whenever you require the dependency.
    - Better maintainability as you know *where* the dependency comes from.

    .. note::

        If you only need a simple function, consider using :py:func:`.factory` instead.

    .. doctest:: helpers_Factory

        >>> from antidote import Factory, world
        >>> class ExternalService:
        ...     pass
        >>> class MyFactory(Factory):
        ...     def __call__(self) -> ExternalService:
        ...         return ExternalService()
        >>> world.get[ExternalService @ MyFactory]()
        <ExternalService ...>

    For customization use :py:attr:`.__antidote__`:

    .. doctest:: helpers_Factory_v2

        >>> from antidote import Factory, world
        >>> class ExternalService:
        ...     pass
        >>> class MyFactory(Factory):
        ...     __antidote__ = Factory.Conf(singleton=False) \\
        ...         .with_wiring(use_names=True)
        ...
        ...     def __call__(self) -> ExternalService:
        ...         return ExternalService()

    One can customize the instantiation and use the same service with different
    configuration:

    .. doctest:: helpers_Factory_v3

        >>> from antidote import Factory, world, inject
        >>> class ExternalService:
        ...     def __init__(self, name):
        ...         self.name = name
        >>> class MyFactory(Factory):
        ...     def __call__(self, name = 'default') -> ExternalService:
        ...         return ExternalService(name)
        >>> world.get[ExternalService](ExternalService @ MyFactory).name
        'default'
        >>> s = world.get[ExternalService](
        ...     ExternalService @ MyFactory.with_kwargs(name='perfection'))
        >>> s.name
        'perfection'
        >>> # The same instance will be returned for those keywords as MyFactory was
        ... # declared as returning a singleton.
        ... s is world.get(ExternalService @ MyFactory.with_kwargs(name='perfection'))
        True
        >>> # You can also keep the dependency and re-use it
        ... PerfectionService = ExternalService @ MyFactory.with_kwargs(name='perfection')
        >>> @inject(dependencies=dict(service=PerfectionService))
        ... def f(service):
        ...     return service
        >>> f() is s
        True

    """

    @final
    class Conf(FinalImmutable, WithWiringMixin):
        """
        Immutable factory configuration. To change parameters on a existing instance, use
        either method :py:meth:`.copy` or
        :py:meth:`.core.wiring.WithWiringMixin.with_wiring`.
        """
        __slots__ = ('wiring', 'singleton', 'tags', 'public')
        wiring: Optional[Wiring]
        singleton: bool
        tags: Optional[Tuple[Tag]]
        public: bool

        def __init__(self,
                     *,
                     wiring: Optional[Wiring] = Wiring(
                         methods=['__call__'],
                         attempt_methods=['__init__']
                     ),
                     singleton: bool = True,
                     tags: Optional[Iterable[Tag]] = None,
                     public: bool = False):
            """

            Args:
                wiring: Wiring to be applied on the factory. By default only
                    :code:`__init__()` and :code:`__call__()` will be wired. To deactivate
                    any wiring at all use :py:obj:`None`.
                singleton: Whether the returned dependency is a singleton or not. If yes,
                    the factory will only be called once and its result cached. Defaults
                    to :py:obj:`True`.
                tags: Iterable of :py:class:`~.._providers.tag.Tag` tagging to the
                      provided dependency.
                public: Whether the factory instance should be retrievable through
                    Antidote or not. Defaults to :py:obj:`False`
            """
            if not isinstance(public, bool):
                raise TypeError(f"public must be a boolean, "
                                f"but not a {type(public)}")
            if not isinstance(singleton, bool):
                raise TypeError(f"singleton must be a boolean, "
                                f"but not a {type(singleton)}")
            if not (tags is None or isinstance(tags, c_abc.Iterable)):
                raise TypeError(f"tags must be None or an iterable of strings/Tags, "
                                f"but not a {type(tags)}")
            elif tags is not None:
                tags = tuple(tags)
                if not all(isinstance(t, Tag) for t in tags):
                    raise TypeError(f"Not all tags were instances of Tag: {tags}")
            if not (wiring is None or isinstance(wiring, Wiring)):
                raise TypeError(f"wiring must be None or a Wiring, "
                                f"but not a {type(wiring)}")
            super().__init__(wiring=wiring, singleton=singleton, tags=tags, public=public)

        def copy(self,
                 *,
                 wiring: Union[Optional[Wiring], Copy] = Copy.IDENTICAL,
                 singleton: Union[bool, Copy] = Copy.IDENTICAL,
                 tags: Union[Optional[Iterable[Tag]], Copy] = Copy.IDENTICAL,
                 public: Union[bool, Copy] = Copy.IDENTICAL
                 ) -> 'Factory.Conf':
            """
            Copies current configuration and overrides only specified arguments.
            Accepts the same arguments as :py:meth:`.__init__`
            """
            return Copy.immutable(self,
                                  wiring=wiring,
                                  singleton=singleton,
                                  tags=tags,
                                  public=public)

    __antidote__: Conf = Conf()
    """
    Configuration of the factory. Defaults to wire :py:meth:`.__init__` and
    :py:meth:`.__call__`.
    """


@overload
def factory(f: F,  # noqa: E704  # pragma: no cover
            *,
            auto_wire: bool = True,
            singleton: bool = True,
            dependencies: DEPENDENCIES_TYPE = None,
            use_names: Union[bool, Iterable[str]] = None,
            use_type_hints: Union[bool, Iterable[str]] = None,
            tags: Iterable[Tag] = None
            ) -> FactoryProtocol[F]: ...


@overload
def factory(*,  # noqa: E704  # pragma: no cover
            auto_wire: bool = True,
            singleton: bool = True,
            dependencies: DEPENDENCIES_TYPE = None,
            use_names: Union[bool, Iterable[str]] = None,
            use_type_hints: Union[bool, Iterable[str]] = None,
            tags: Iterable[Tag] = None
            ) -> Callable[[F], FactoryProtocol[F]]: ...


@API.public
def factory(f: F = None,
            *,
            auto_wire: bool = True,
            singleton: bool = True,
            dependencies: DEPENDENCIES_TYPE = None,
            use_names: Union[bool, Iterable[str]] = None,
            use_type_hints: Union[bool, Iterable[str]] = None,
            tags: Iterable[Tag] = None
            ) -> Union[FactoryProtocol[F], Callable[[F], FactoryProtocol[F]]]:
    """
    Registers a factory which provides as single dependency, defined through the return
    type annotation.

    To retrieve the dependency from Antidote you need to use a specific syntax
    :code:`dependency @ factory` as presented in the following examples. The goal of it is
    twofold:

    - Ensure that the factory is loaded whenever you require the dependency.
    - Better maintainability as you know *where* the dependency comes from.

    .. note::

        If you need a stateful factory or want to implement a complex one prefer using
        :py:class:`.Factory` instead.

    .. doctest:: helpers_factory

        >>> from antidote import factory, world
        >>> class ExternalService:
        ...     pass
        >>> @factory
        ... def build_service() -> ExternalService:
        ...     return ExternalService()
        >>> world.get[ExternalService](ExternalService @ build_service)
        <ExternalService ...>

    One can customize the instantiation and use the same service with different
    configuration:

    .. doctest:: helpers_factory_v2

        >>> from antidote import factory, world, inject
        >>> class ExternalService:
        ...     def __init__(self, name):
        ...         self.name = name
        >>> @factory
        ... def build_service(name = 'default') -> ExternalService:
        ...     return ExternalService(name)
        >>> world.get[ExternalService](ExternalService @ build_service).name
        'default'
        >>> s = world.get[ExternalService](
        ...     ExternalService @ build_service.with_kwargs(name='perfection'))
        >>> s.name
        'perfection'
        >>> # The same instance will be returned for those keywords as MyFactory was
        ... # declared as returning a singleton.
        ... s is world.get(ExternalService @ build_service.with_kwargs(name='perfection'))
        True
        >>> # You can also keep the dependency and re-use it
        ... PerfectionService = \\
        ...     ExternalService @ build_service.with_kwargs(name='perfection')
        >>> @inject(dependencies=dict(service=PerfectionService))
        ... def f(service):
        ...     return service
        >>> f() is s
        True

    Args:
        f: Callable which builds the dependency.
        singleton: If True, `func` will only be called once. If not it is
            called at each injection.
        auto_wire: Whether the function should have its arguments injected or not
            with :py:func:`~.injection.inject`.
        dependencies: Propagated to :py:func:`~.injection.inject`.
        use_names: Propagated to :py:func:`~.injection.inject`.
        use_type_hints: Propagated to :py:func:`~.injection.inject`.
        tags: Iterable of :py:class:`~.._providers.tag.Tag` applied to the provided
            dependency.

    Returns:
        The factory or the function decorator.

    """
    if not (auto_wire is None or isinstance(auto_wire, bool)):
        raise TypeError(f"auto_wire can be None or a boolean, not {type(auto_wire)}")

    @inject
    def register_factory(func: F,
                         factory_provider: FactoryProvider = None,
                         tag_provider: TagProvider = None) -> FactoryProtocol[F]:
        assert factory_provider is not None

        if not inspect.isfunction(func):
            raise TypeError(f"{func} is not a function")

        dependency = get_type_hints(func).get('return')
        if dependency is None:
            raise ValueError("A return annotation is necessary. "
                             "It is used a the dependency.")
        if not inspect.isclass(dependency):
            raise TypeError(f"The return annotation is expected to be a class, "
                            f"not {type(dependency)}.")

        if auto_wire:
            func = inject(func,
                          dependencies=dependencies,
                          use_names=use_names,
                          use_type_hints=use_type_hints)

        factory_id = factory_provider.register(factory=func,
                                               singleton=singleton,
                                               dependency=dependency)

        if tags is not None:
            if tag_provider is None:
                raise RuntimeError("No TagProvider registered, cannot use tags.")
            tag_provider.register(dependency=factory_id, tags=tags)

        return cast(FactoryProtocol[F], LambdaFactory(func, factory_id))

    return f and register_factory(f) or register_factory
