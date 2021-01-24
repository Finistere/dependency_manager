from typing import cast, Dict, Tuple, Type

from ._internal import API
from ._internal.utils import AbstractMeta
from ._providers import ServiceProvider, TagProvider
from ._providers.service import Build
from .core import inject, Provide

_ABSTRACT_FLAG = '__antidote_abstract'


@API.private
class ServiceMeta(AbstractMeta):
    def __new__(mcs: 'Type[ServiceMeta]',
                name: str,
                bases: Tuple[type, ...],
                namespace: Dict[str, object],
                **kwargs: object
                ) -> 'ServiceMeta':
        cls = cast(
            ServiceMeta,
            super().__new__(mcs, name, bases, namespace, **kwargs)  # type: ignore
        )
        if not kwargs.get('abstract'):
            _configure_service(cls)
        return cls

    @API.public
    def _with_kwargs(cls, **kwargs: object) -> object:
        """
        Creates a new dependency based on the service which will have the keyword
        arguments provided. If the service is a singleton and identical kwargs are used,
        the same instance will be given by Antidote.

        Args:
            **kwargs: Arguments passed on to :code:`__init__()`.

        Returns:
            Dependency to be retrieved from Antidote. You cannot use it directly.
        """
        return Build(cls, kwargs)


@API.private
@inject
def _configure_service(cls: type,
                       service_provider: Provide[ServiceProvider] = None,
                       tag_provider: Provide[TagProvider] = None,
                       conf: object = None) -> None:
    from .service import Service
    assert service_provider is not None

    conf = conf or getattr(cls, '__antidote__', None)
    if not isinstance(conf, Service.Conf):
        raise TypeError(f"Service configuration (__antidote__) is expected to be a "
                        f"{Service.Conf}, not a {type(conf)}")

    if conf.tags is not None and tag_provider is None:
        raise RuntimeError("No TagProvider registered, cannot use tags.")

    wiring = conf.wiring

    if wiring is not None:
        wiring.wire(cls)

    service_provider.register(cls, scope=conf.scope)
    if conf.tags:
        assert tag_provider is not None  # for Mypy
        tag_provider.register(dependency=cls, tags=conf.tags)
