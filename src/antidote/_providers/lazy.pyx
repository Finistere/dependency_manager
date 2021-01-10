# @formatter:off
from typing import Hashable

cimport cython
from cpython.object cimport PyObject

from antidote.core.container cimport (Container, DependencyValue, DependencyResult,
                                     FastProvider)
from .._internal.utils import debug_repr
from ..core.exceptions import DebugNotAvailableError
from ..core import DependencyDebug

# @formatter:on

cdef extern from "Python.h":
    int PyObject_IsInstance(PyObject *inst, PyObject *cls) except -1


cdef class Lazy:
    def debug_info(self) -> DependencyDebug:
        raise DebugNotAvailableError()  # pragma: no cover

    cdef fast_lazy_get(self, PyObject*container, DependencyResult*result):
        cdef:
            DependencyValue dependency_instance
        dependency_instance = self.lazy_get(<Container> container)
        if dependency_instance is not None:
            dependency_instance.to_result(result)

    cpdef lazy_get(self, container: Container):
        raise NotImplementedError()  # pragma: no cover

@cython.final
cdef class LazyProvider(FastProvider):
    def clone(self, keep_singletons_cache: bool) -> FastProvider:
        return LazyProvider()

    def exists(self, dependency: Hashable) -> bool:
        return isinstance(dependency, Lazy)

    def maybe_debug(self, dependency: Hashable):
        if isinstance(dependency, Lazy):
            try:
                return dependency.debug_info()
            except DebugNotAvailableError:
                import warnings
                warnings.warn(f"Debug information for {debug_repr(dependency)} "
                              f"not available in {type(self)}")

    cdef fast_provide(self,
                      PyObject*dependency,
                      PyObject*container,
                      DependencyResult*result):
        if PyObject_IsInstance(dependency, <PyObject*> Lazy):
            return (<Lazy> dependency).fast_lazy_get(container, result)
