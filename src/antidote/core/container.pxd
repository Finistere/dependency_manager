# @formatter:off
from cpython.ref cimport PyObject

from antidote._internal.stack cimport DependencyStack
# @formatter:on

ctypedef unsigned short Header
ctypedef unsigned short ScopeId

cdef bint header_is_singleton(Header header)
cdef bint header_has_scope(Header header)
cdef bint header_is_cacheable(Header header)
cdef Header header_scope(ScopeId scope_id)
cdef Header header_strictest(Header h1, Header h2)
cdef Header header_flag_singleton()
cdef Header header_flag_no_scope()
cdef Header header_flag_cacheable()

cdef class HeaderObject:
    cdef:
        Header header

    @staticmethod
    cdef HeaderObject from_scope(Scope scope)

cdef struct DependencyResult:
    # Holds information on the dependency (singleton, etc...).
    # Only valid if value is not NULL.
    Header header
    # Pointer to dependency value. Once done using the result, you MUST use Py_XDECREF
    # NULL if not found.
    PyObject *value

cdef class Scope:
    cdef:
        readonly str name
        ScopeId id

cdef class DependencyValue:
    cdef:
        readonly object unwrapped
        readonly Scope scope

    cdef to_result(self, DependencyResult *result)

    @staticmethod
    cdef DependencyValue from_result(RawContainer container, DependencyResult *result)

cdef class Container:
    pass

cdef class RawProvider:
    cdef:
        object _container_ref

    cdef fast_provide(self,
                      PyObject *dependency,
                      PyObject *container,
                      DependencyResult *result)
    cdef RawContainer _bound_container(self)

cdef class FastProvider(RawProvider):
    pass

cdef class RawContainer(Container):
    cdef:
        object __weakref__
        list _providers
        DependencyStack _dependency_stack
        object _instantiation_lock
        object _freeze_lock
        bint __frozen
        bint _is_clone
        dict _singletons
        unsigned long __singletons_clock
        object __cache
        list _scopes
        list _scope_dependencies

    cdef Scope get_scope(self, ScopeId scope_id)
    cdef fast_get(self, PyObject *dependency, DependencyResult *result)
    cdef __safe_cache_provide(self,
                              PyObject *dependency,
                              DependencyResult *result,
                              CacheValue*cached)
    cdef __safe_provide(self,
                        PyObject *dependency,
                        DependencyResult *result,
                        unsigned long singletons_clock)

cdef struct CacheValue:
    Header header
    PyObject *ptr
