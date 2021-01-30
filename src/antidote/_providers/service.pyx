import inspect
from typing import Dict, Hashable

# @formatter:off
cimport cython
from cpython.ref cimport PyObject

from antidote.core.container cimport (DependencyResult, FastProvider, Header, HeaderObject,
                                      Scope, header_flag_cacheable)
from .._internal.utils import debug_repr
# @formatter:on
from ..core import DependencyDebug

cdef extern from "Python.h":
    PyObject*Py_True
    int PyObject_IsInstance(PyObject *inst, PyObject *cls) except -1
    PyObject*PyDict_GetItem(PyObject *p, PyObject *key)
    PyObject*PyObject_Call(PyObject *callable, PyObject *args, PyObject *kwargs) except NULL
    PyObject*PyObject_CallObject(PyObject *callable, PyObject *args) except NULL


@cython.final
cdef class Build:
    def __init__(self, dependency: Hashable, kwargs: Dict):
        assert isinstance(kwargs, dict) and len(kwargs) > 0
        self.dependency = dependency  # type: Hashable
        self.kwargs = kwargs  # type: Dict

        try:
            # Try most precise hash first
            self._hash = hash((self.dependency, tuple(self.kwargs.items())))
        except TypeError:
            # If type error, return the best error-free hash possible
            self._hash = hash((self.dependency, tuple(self.kwargs.keys())))

    def __hash__(self):
        return self._hash

    def __repr__(self):
        return f"Build(dependency={self.dependency}, kwargs={self.kwargs})"

    def __antidote_debug_repr__(self):
        return f"{debug_repr(self.dependency)} with kwargs={self.kwargs}"

    def __eq__(self, other):
        return (isinstance(other, Build)
                and self._hash == other._hash
                and (self.dependency is other.dependency
                     or self.dependency == other.dependency)
                and self.kwargs == other.kwargs)  # noqa

@cython.final
cdef class ServiceProvider(FastProvider):
    """
    Provider managing factories. Also used to register classes directly.
    """
    cdef:
        dict __services
        tuple __empty_tuple

    def __init__(self):
        super().__init__()
        self.__empty_tuple = tuple()
        self.__services = dict()  # type: Dict[Hashable, HeaderObject]

    def __repr__(self):
        return f"{type(self).__name__}(services={list(self.__services.items())!r})"

    def exists(self, dependency: Hashable) -> bool:
        if isinstance(dependency, Build):
            return dependency.dependency in self.__services
        return dependency in self.__services

    def clone(self, keep_singletons_cache: bool) -> ServiceProvider:
        p = ServiceProvider()
        p.__services = self.__services.copy()
        return p

    def maybe_debug(self, build: Hashable):
        klass = build.dependency if isinstance(build, Build) else build
        try:
            header = self.__services[klass]
        except KeyError:
            return None
        return DependencyDebug(debug_repr(build),
                               scope=header.to_scope(self._bound_container()),
                               wired=[klass])

    cdef fast_provide(self,
                      PyObject*dependency,
                      PyObject*container,
                      DependencyResult*result):
        cdef:
            PyObject*service
            PyObject*ptr
            tuple args
            object factory
            int scope_or_singleton

        if PyObject_IsInstance(dependency, <PyObject*> Build):
            ptr = PyDict_GetItem(<PyObject*> self.__services,
                                 <PyObject*> (<Build> dependency).dependency)
            if ptr:
                result.header = (<HeaderObject> ptr).header
                result.value = PyObject_Call(
                    <PyObject*> (<Build> dependency).dependency,
                    <PyObject*> self.__empty_tuple,
                    <PyObject*> (<Build> dependency).kwargs
                )
        else:
            ptr = PyDict_GetItem(<PyObject*> self.__services, dependency)
            if ptr:
                result.header = (<HeaderObject> ptr).header | header_flag_cacheable()
                result.value = PyObject_CallObject( dependency, NULL)


    def register(self, klass: type, *, Scope scope):
        cdef:
            Header header
        assert inspect.isclass(klass) \
               and (isinstance(scope, Scope) or scope is None)
        with self._bound_container_ensure_not_frozen():
            self._bound_container_raise_if_exists(klass)
            self.__services[klass] = HeaderObject.from_scope(scope)
