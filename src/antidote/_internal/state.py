"""
Antidote has a global container which is managed in this module.
"""
import threading
from contextlib import contextmanager
from typing import Callable, Iterator, Optional

from ..core.container import OverridableRawContainer, RawContainer

__container: Optional[RawContainer] = None
__container_lock = threading.RLock()


def current_container() -> RawContainer:
    assert __container is not None
    return __container


def current_overridable_container() -> OverridableRawContainer:
    assert __container is not None
    if not isinstance(__container, OverridableRawContainer):
        raise RuntimeError("Current world does not support overrides. "
                           "Consider using world.test.clone(override=True)")
    return __container


# Used only for tests
def reset() -> None:
    global __container
    __container = None


def init() -> None:
    global __container
    if __container is None:
        with __container_lock:
            if __container is None:
                from antidote._internal.world import new_container
                __container = new_container()


@contextmanager
def override(create: Callable[[RawContainer], RawContainer]) -> Iterator[None]:
    global __container
    with __container_lock:
        assert __container is not None
        old = __container
        try:
            __container = create(old)
            yield
        finally:
            __container = old
