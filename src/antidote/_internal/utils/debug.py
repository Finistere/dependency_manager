import base64
import inspect
import textwrap
from collections import deque
from typing import (Deque, Hashable, List, Optional, Sequence, Set, TYPE_CHECKING, Tuple)

from .immutable import Immutable
from .. import API

if TYPE_CHECKING:
    from ...core.container import RawContainer, Scope

# Object will be allocated on the heap, so as close as possible to most user objects
# in memory.
_ID_MASK = id(object())


@API.private
def short_id(__obj: object) -> str:
    """ Produces a short, human readable, representation of the id of an object. """
    n = id(__obj) ^ _ID_MASK
    return (base64
            .b64encode(n.to_bytes(8, byteorder='little'))
            .decode('ascii')
            .rstrip('=')  # Remove padding
            .rstrip('A'))  # Remove 000000


@API.private
def debug_repr(__obj: object) -> str:
    from ..wrapper import is_wrapper
    try:
        return str(__obj.__antidote_debug_repr__())  # type: ignore
    except Exception:
        pass
    if (isinstance(__obj, type) and inspect.isclass(__obj)) \
            or inspect.isfunction(__obj) \
            or is_wrapper(__obj):
        if isinstance(__obj.__module__, str) \
                and __obj.__module__ not in {"__main__", "builtins"}:
            module = __obj.__module__ + "."
        else:
            module = ""
        return f"{module}{__obj.__qualname__}"  # type: ignore
    return repr(__obj)


@API.private
def get_injections(__func: object) -> Sequence[object]:
    from ..wrapper import get_wrapper_dependencies
    try:
        return get_wrapper_dependencies(__func)  # type: ignore
    except TypeError:
        return []


@API.private
class Task(Immutable):
    __slots__ = ()


@API.private
class DependencyTask(Task):
    __slots__ = ('dependency',)
    dependency: Hashable


@API.private
class InjectionTask(Task):
    __slots__ = ('name', 'injections')
    name: str
    injections: List[Hashable]


@API.private
def scope_repr(scope: 'Optional[Scope]', *, empty: str) -> str:
    from ...core import Scope
    if scope is None:
        return "<∅> "
    elif scope is Scope.singleton() or scope is Scope.sentinel():
        return empty
    else:
        return f"<{scope.name}> "


_LEGEND = """
Singletons have no scope markers.
<∅> = no scope (new instance each time)
<name> = custom scope
"""


@API.private
def tree_debug_info(container: 'RawContainer',
                    origin: object,
                    depth: int = -1) -> str:
    from ...core.wiring import WithWiringMixin
    from ...core.exceptions import DependencyNotFoundError
    from ...core import Scope

    @API.private
    class DebugTreeNode(Immutable):
        __slots__ = ('info', 'scope', 'children')
        info: str
        scope: 'Optional[Scope]'
        children: 'List[DebugTreeNode]'

        def __init__(self,
                     info: str,
                     *,
                     scope: 'Optional[Scope]' = Scope.sentinel(),
                     children: 'List[DebugTreeNode]' = None) -> None:
            super().__init__(info=textwrap.dedent(info),
                             scope=scope,
                             children=children or [])

    if depth < 0:
        depth = 1 << 31  # roughly infinity in this case.

    depth += 1  # To match root = depth 0
    root = DebugTreeNode(info=debug_repr(origin))
    original_root = root
    tasks: Deque[Tuple[DebugTreeNode, Set[object], Task]] = deque([
        (root, set(), DependencyTask(origin))
    ])

    def add_root_injections(parent: DebugTreeNode,
                            parent_dependencies: Set[object],
                            dependency: Hashable) -> None:
        from ...core.wiring import Methods

        if isinstance(dependency, type) and inspect.isclass(dependency):
            cls = dependency
            conf = getattr(cls, '__antidote__', None)
            if conf is not None \
                    and isinstance(conf, WithWiringMixin) \
                    and conf.wiring is not None:
                if isinstance(conf.wiring.methods, Methods):
                    for name, member in cls.__dict__.items():
                        if name != '__init__' and callable(member):
                            injections = get_injections(member)
                            if injections:
                                tasks.append((parent, parent_dependencies, InjectionTask(
                                    name=f"Method: {name}",
                                    injections=injections,
                                )))
                else:
                    for name in sorted(conf.wiring.methods):
                        if name != '__init__':
                            tasks.append((parent, parent_dependencies, InjectionTask(
                                name=f"Method: {name}",
                                injections=get_injections(getattr(cls, name)),
                            )))
        elif callable(dependency):
            for d in get_injections(dependency):
                tasks.append((parent, parent_dependencies, DependencyTask(d)))

    while tasks:
        parent, parent_dependencies, task = tasks.pop()
        if isinstance(task, DependencyTask):
            dependency = task.dependency
            try:
                debug = container.debug(dependency)
            except DependencyNotFoundError:
                if dependency is origin:
                    add_root_injections(parent, parent_dependencies, dependency)
                else:
                    parent.children.append(DebugTreeNode(f"/!\\ Unknown: "
                                                         f"{debug_repr(dependency)}"))

                continue

            if dependency in parent_dependencies:
                parent.children.append(DebugTreeNode(f"/!\\ Cyclic dependency: "
                                                     f"{debug.info}"))
                continue

            tree_node = DebugTreeNode(debug.info, scope=debug.scope)

            parent.children.append(tree_node)
            parent = tree_node
            parent_dependencies = parent_dependencies | {dependency}

            if dependency is origin:
                root = tree_node  # previous root is redundant
                add_root_injections(parent, parent_dependencies, dependency)

            if len(parent_dependencies) < depth:
                for d in debug.dependencies:
                    tasks.append((parent, parent_dependencies,
                                  DependencyTask(d)))
                for w in debug.wired:
                    if isinstance(w, type) and inspect.isclass(w):
                        for d in get_injections(getattr(w, '__init__')):
                            tasks.append((parent, parent_dependencies,
                                          DependencyTask(d)))
                    else:
                        tasks.append((parent, parent_dependencies, InjectionTask(
                            name=debug_repr(w),
                            injections=get_injections(w),
                        )))
        elif isinstance(task, InjectionTask) and task.injections:
            tree_node = DebugTreeNode(task.name)
            parent.children.append(tree_node)
            parent = tree_node
            for d in task.injections:
                tasks.append((parent, parent_dependencies, DependencyTask(d)))

    if not root.children and original_root is root:
        from ..._providers.tag import TagDependency
        if isinstance(origin, TagDependency):
            return f"No dependencies tagged with {origin.tag!r}"

        return f"{origin!r} is neither a dependency nor is anything injected."

    output = [
        scope_repr(root.scope, empty="") + root.info
    ]
    nodes: Deque[Tuple[str, bool, DebugTreeNode]] = deque([
        ("", i == 0, child)
        for i, child in enumerate(root.children[::-1])
    ])

    while nodes:
        prefix, last, node = nodes.pop()
        first_line, *rest = node.info.split("\n", 1)
        txt = prefix + ("└──" if last else "├──")
        txt += scope_repr(node.scope, empty=" ") + first_line
        new_prefix = prefix + ("    " if last else "│   ")
        if rest:
            txt += "\n" + textwrap.indent(rest[0], new_prefix)
        output.append(txt)

        for i, child in enumerate(node.children[::-1]):
            nodes.append((new_prefix, i == 0, child))

    output.append(_LEGEND)

    return "\n".join(output)
