from . import world
from .constants import const, Constants
from .core import inject, wire, Wiring, Scope
from .factory import factory, Factory
from .implementation import implementation
from .lazy import LazyCall, LazyMethodCall
from .service import service, Service
from .tag import Tag, Tagged
from .utils import is_compiled


def __version__() -> str:  # pragma: no cover
    try:
        from ._internal.scm_version import version
        return str(version)
    except ImportError:
        return ''


__all__ = ['world', 'const', 'Constants', 'inject', 'wire', 'Wiring', 'factory',
           'Factory', 'implementation', 'LazyCall', 'LazyMethodCall',
           'service', 'Service', 'Tag', 'Tagged', 'is_compiled']
