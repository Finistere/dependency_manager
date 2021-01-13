import inspect
from typing import Callable, Dict, Hashable, Optional

# @formatter:off
cimport cython
from cpython.ref cimport PyObject, Py_XDECREF

from antidote.core.container cimport (DependencyResult, FastProvider, RawContainer,
                                     header_flag_cacheable)
from .._internal.utils import debug_repr
from ..core import DependencyDebug, Scope
from ..core.exceptions import DependencyNotFoundError

# @formatter:on

cdef extern from "Python.h":
    int PyDict_SetItem(PyObject *p, PyObject *key, PyObject *val) except -1
    PyObject*PyDict_GetItem(PyObject *p, PyObject *key)
    PyObject*PyObject_CallObject(PyObject *callable, PyObject *args) except NULL
    int PySet_Contains(PyObject *anyset, PyObject *key) except -1


@cython.final
cdef class IndirectProvider(FastProvider):
    cdef:
        dict __indirect
        set __implementations
        bint __implicits_registered

    def __init__(self):
        super().__init__()
        self.__implicits_registered = False
        self.__implementations = set()
        self.__indirect = dict()  # type: Dict[Hashable, Hashable]

    def __repr__(self):
        return f"{type(self).__name__}(implementations={self.__implementations}, " \
               f"indirect={self.__indirect}, implicits={self.__implicits_registered})"

    def clone(self, keep_singletons_cache: bool) -> IndirectProvider:
        p = IndirectProvider()
        p.__implicits_registered = self.__implicits_registered
        p.__implementations = self.__implementations.copy()
        p.__indirect = self.__indirect.copy()
        return p

    def exists(self, dependency) -> bool:
        return dependency in self.__indirect or dependency in self.__implementations

    def maybe_debug(self, dependency: Hashable) -> Optional[DependencyDebug]:
        cdef:
            ImplementationDependency impl

        if dependency in self.__implementations:
            impl = <ImplementationDependency> dependency
            if dependency in self.__indirect:
                target = self.__indirect[dependency]
            else:
                target = impl.implementation()  # type: ignore

            return DependencyDebug(debug_repr(dependency),
                                   scope=Scope.singleton() if impl.permanent else None,
                                   wired=[impl.implementation],  # type: ignore
                                   dependencies=[target])

        try:
            target = self.__indirect[dependency]
        except KeyError:
            pass
        else:
            repr_d = debug_repr(dependency)
            return DependencyDebug(f"Implicit: {repr_d} -> {debug_repr(target)}",
                                   scope=Scope.singleton(),
                                   dependencies=[target])
        return None

    cdef fast_provide(self,
                      PyObject*dependency,
                      PyObject*container,
                      DependencyResult*result):
        cdef:
            PyObject*ptr
            PyObject*target

        ptr = PyDict_GetItem(<PyObject*> self.__indirect, dependency)
        if ptr:
            (<RawContainer> container).fast_get(ptr, result)
            result.header |= header_flag_cacheable()
            if result.value is NULL:
                raise DependencyNotFoundError(<object> ptr)
        elif PySet_Contains(<PyObject*> self.__implementations, dependency):
            target = PyObject_CallObject(
                <PyObject*> (<ImplementationDependency> dependency).implementation,
                NULL
            )
            (<RawContainer> container).fast_get(target, result)
            if result.value is NULL:
                error = DependencyNotFoundError(<object> target)
                Py_XDECREF(target)
                raise error

            if (<ImplementationDependency> dependency).permanent:
                result.header |= header_flag_cacheable()
                PyDict_SetItem(<PyObject*> self.__indirect,
                               dependency,
                               target)
            else:
                result.header = 0

            Py_XDECREF(target)

    def register_implicits(self, dependency_to_target: Dict[Hashable, Hashable]) -> None:
        assert isinstance(dependency_to_target, dict)

        with self._bound_container_ensure_not_frozen():
            if self.__implicits_registered:
                raise RuntimeError(f"Implicits have already been defined once.")
            for dependency in dependency_to_target.keys():
                self._bound_container_raise_if_exists(dependency)
            self.__implicits_registered = True
            self.__indirect.update(dependency_to_target)

    def register_implementation(self,
                                interface: type,
                                implementation: Callable[[], Hashable],
                                *,
                                permanent: bool
                                ) -> 'ImplementationDependency':
        assert callable(implementation) \
               and inspect.isclass(interface) \
               and isinstance(permanent, bool)
        impl = ImplementationDependency(interface, implementation, permanent)
        with self._bound_container_ensure_not_frozen():
            self._bound_container_raise_if_exists(impl)
            self.__implementations.add(impl)
            return impl

@cython.final
cdef class ImplementationDependency:
    cdef:
        readonly object interface
        readonly object implementation
        readonly bint permanent
        int _hash

    def __init__(self,
                 interface: Hashable,
                 implementation: Callable[[], Hashable],
                 permanent: bool):
        self.interface = interface
        self.implementation = implementation
        self.permanent = permanent
        self._hash = hash((interface, implementation))

    def __repr__(self) -> str:
        return f"Implementation({self})"

    def __antidote_debug_repr__(self) -> str:
        if self.permanent:
            return f"Permanent implementation: {self}"
        else:
            return f"Implementation: {self}"

    def __str__(self) -> str:
        impl = self.implementation  # type: ignore
        return f"{debug_repr(self.interface)} @ {debug_repr(impl)}"

    # Custom hash & eq necessary to find duplicates
    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: object) -> bool:
        cdef:
            ImplementationDependency imd

        if not isinstance(other, ImplementationDependency):
            return False

        imd = <ImplementationDependency> other
        return (self._hash == imd._hash
                and (self.interface is imd.interface
                     or self.interface == imd.interface)
                and (self.implementation is imd.implementation  # type: ignore
                     or self.implementation == imd.implementation)  # type: ignore
                )  # noqa
