import inspect
from typing import Callable, Dict, Hashable, Optional, Union

# @formatter:off
cimport cython
from cpython.ref cimport PyObject, Py_XDECREF

from antidote._providers.service cimport Build
from antidote.core.container cimport (DependencyResult, FastProvider, Header,
                                      HeaderObject, header_is_singleton, Scope,
                                      RawContainer, header_flag_cacheable)
from .._internal.utils import debug_repr
from ..core import Dependency, DependencyDebug
from ..core.exceptions import DependencyNotFoundError
# @formatter:on

cdef extern from "Python.h":
    int PyObject_IsInstance(PyObject *inst, PyObject *cls) except -1
    PyObject*PyDict_GetItem(PyObject *p, PyObject *key)
    PyObject*PyObject_Call(PyObject *callable, PyObject *args,
                           PyObject *kwargs) except NULL
    PyObject*PyObject_CallObject(PyObject *callable, PyObject *args) except NULL


@cython.final
cdef class FactoryProvider(FastProvider):
    cdef:
        dict __factories
        tuple __empty_tuple
        object __weakref__

    def __init__(self):
        super().__init__()
        self.__factories = dict()  # type: Dict[FactoryDependency, Factory]
        self.__empty_tuple = tuple()

    def __repr__(self):
        return f"{type(self).__name__}(factories={self.__factories})"

    def clone(self, keep_singletons_cache: bool) -> FactoryProvider:
        cdef:
            Factory f
            FactoryProvider p

        p = FactoryProvider()
        if keep_singletons_cache:
            factories = {
                k: (f.copy() if f.dependency is not None else f)
                for k, f in self.__factories.items()
            }
        else:
            factories = {
                k: (f.copy_without_function() if f.dependency is not None else f)
                for k, f in self.__factories.items()
            }
        p.__factories = factories
        return p

    def exists(self, dependency: Hashable) -> bool:
        if isinstance(dependency, Build):
            dependency = dependency.dependency
        return (isinstance(dependency, FactoryDependency)
                and dependency in self.__factories)

    def maybe_debug(self, build: Hashable) -> Optional[DependencyDebug]:
        cdef:
            Factory factory

        dependency_factory = build.dependency if isinstance(build, Build) else build
        if not isinstance(dependency_factory, FactoryDependency):
            return None

        try:
            factory = self.__factories[dependency_factory]
        except KeyError:
            return None

        dependencies = []
        wired = []
        if factory.dependency is not None:
            dependencies.append(factory.dependency)
            if isinstance(factory.dependency, type) \
                    and inspect.isclass(factory.dependency):
                wired.append(factory.dependency.__call__)
        else:
            wired.append(factory.function)

        header = HeaderObject(factory.header)
        return DependencyDebug(
            debug_repr(build),
            scope=header.to_scope(self._bound_container()),
            wired=wired,
            dependencies=dependencies)

    cdef fast_provide(self,
                      PyObject*dependency,
                      PyObject*container,
                      DependencyResult*result):
        cdef:
            PyObject*factory
            bint is_build_dependency = PyObject_IsInstance(dependency, <PyObject*> Build)
            PyObject*dependency_factory = (<PyObject*> (<Build> dependency).dependency
                                           if is_build_dependency else
                                           dependency)

        if not PyObject_IsInstance(dependency_factory, <PyObject*> FactoryDependency):
            return

        factory = PyDict_GetItem(<PyObject*> self.__factories, dependency_factory)
        if factory is NULL:
            return

        if (<Factory> factory).function is None:
            (<RawContainer> container).fast_get(
                <PyObject*> (<Factory> factory).dependency,
                result)
            if result.value is NULL:
                raise DependencyNotFoundError((<Factory> factory).dependency)
            assert header_is_singleton(
                result.header), "factory dependency is expected to be a singleton"
            (<Factory> factory).function = <object> result.value
            Py_XDECREF(result.value)

        if is_build_dependency:
            result.header = (<Factory> factory).header
            result.value = PyObject_Call(
                <PyObject*> (<Factory> factory).function,
                <PyObject*> self.__empty_tuple,
                <PyObject*> (<Build> dependency).kwargs
            )
        else:
            result.header = (<Factory> factory).header | header_flag_cacheable()
            result.value = PyObject_CallObject(
                <PyObject*> (<Factory> factory).function,
                NULL
            )

    def register(self,
                 output: type,
                 *,
                 factory: Union[Callable, Dependency],
                 Scope scope) -> FactoryDependency:
        cdef:
            Header header
        assert inspect.isclass(output) \
               and (callable(factory) or isinstance(factory, Dependency)) \
               and (isinstance(scope, Scope) or scope is None)
        with self._bound_container_ensure_not_frozen():
            factory_dependency = FactoryDependency(output, factory)
            self._bound_container_raise_if_exists(factory_dependency)

            header = HeaderObject.from_scope(scope).header
            if isinstance(factory, Dependency):
                self.__factories[factory_dependency] = Factory.__new__(
                    Factory,
                    header,
                    dependency=factory.unwrapped
                )
            else:
                self.__factories[factory_dependency] = Factory.__new__(
                    Factory,
                    header,
                    function=factory
                )

            return factory_dependency

@cython.final
cdef class FactoryDependency:
    cdef:
        readonly object output
        readonly object factory
        int _hash

    def __init__(self, object output, object factory):
        self.output = output
        self.factory = factory.unwrapped if isinstance(factory, Dependency) else factory
        self._hash = hash((output, factory))

    def __repr__(self) -> str:
        return f"FactoryDependency({self})"

    def __antidote_debug_repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"{debug_repr(self.output)} @ {debug_repr(self.factory)}"

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: object) -> bool:
        cdef:
            FactoryDependency fd

        if not isinstance(other, FactoryDependency):
            return False

        fd = <FactoryDependency> other
        return (self._hash == fd._hash
                and (self.output is fd.output
                     or self.output == fd.output)
                and (self.factory is fd.factory
                     or self.factory == fd.factory))  # noqa

@cython.final
cdef class Factory:
    cdef:
        Header header
        object function
        object dependency

    def __cinit__(self,
                  Header header,
                  function: Callable = None,
                  dependency: Hashable = None):
        assert function is not None or dependency is not None
        self.header = header
        self.function = function
        self.dependency = dependency

    def __repr__(self):
        return (f"{type(self).__name__}(function={self.function}, "
                f"dependency={self.dependency})")

    def copy(self):
        return Factory(self.header, self.function, self.dependency)

    def copy_without_function(self):
        assert self.dependency is not None
        return Factory(self.header, None, self.dependency)
