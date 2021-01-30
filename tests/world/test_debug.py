import textwrap

from antidote import (Constants, Factory, From, LazyCall, LazyMethodCall, Provide,
                      Service, Tag, Tagged, const, implementation, inject, world)
from antidote._compatibility.typing import Annotated
from antidote._internal.utils import short_id


class DebugTestCase:
    def __init__(self, value, expected: str, depth: int = -1, legend: bool = True):
        if expected.startswith('\n'):
            expected = textwrap.dedent(expected[1:])
        lines = expected.splitlines(keepends=True)
        while not lines[-1].strip():
            lines.pop()

        if legend:
            from antidote._internal.utils.debug import _LEGEND
            lines.append(_LEGEND)
        self.value = value
        self.expected = ''.join(lines)
        self.depth = depth


def assert_valid(*test_cases: DebugTestCase):
    for test_case in test_cases:
        assert world.debug(test_case.value,
                           depth=test_case.depth) == test_case.expected


def test_no_debug():
    def g():
        pass

    assert_valid(
        DebugTestCase(
            value=g,
            expected=f"""{g!r} is neither a dependency nor is anything injected.""",
            legend=False
        )
    )


def test_implementation_debug():
    class Interface:
        pass

    prefix = "tests.world.test_debug.test_implementation_debug.<locals>"

    with world.test.new():
        class Dummy(Interface, Service):
            pass

        @implementation(Interface)
        def f():
            return Dummy

        assert_valid(DebugTestCase(
            value=Interface @ f,
            expected=f"""
                Permanent implementation: {prefix}.Interface @ {prefix}.f
                └── {prefix}.Dummy
                    """
        ))

        world.get(Interface @ f)
        assert_valid(DebugTestCase(
            value=Interface @ f,
            expected=f"""
                Permanent implementation: {prefix}.Interface @ {prefix}.f
                └── {prefix}.Dummy
                    """
        ))

    with world.test.new():
        class Dummy2(Interface, Service):
            pass

        undefined_expectations = f"""
            <∅> Implementation: {prefix}.Interface @ {prefix}.g
            └── {prefix}.Dummy2
        """

        @implementation(Interface, permanent=False)
        def g():
            return Dummy2

        assert_valid(DebugTestCase(value=Interface @ g,
                                   expected=undefined_expectations))

        world.get(Interface @ g)
        assert_valid(DebugTestCase(value=Interface @ g,
                                   expected=undefined_expectations))


def test_lazy_call_debug():
    prefix = "tests.world.test_debug.test_lazy_call_debug.<locals>"

    with world.test.new():
        def f():
            pass

        l1 = LazyCall(f)("arg", hello="world")
        assert_valid(
            DebugTestCase(
                value=l1,
                expected=f"""
                    Lazy: {prefix}.f(*('arg',), **{{'hello': 'world'}})  #{short_id(l1)}
                    """
            ),
            DebugTestCase(
                value=LazyCall(f, singleton=False)("arg", bye="world"),
                expected=f"""
                    <∅> Lazy: {prefix}.f(*('arg',), **{{'bye': 'world'}})
                    """
            ))

    with world.test.new():
        class MyService(Service):
            pass

        @inject
        def f(service: Provide[MyService]):
            pass

        l2 = LazyCall(f)
        assert_valid(
            DebugTestCase(
                value=l2,
                expected=f"""
                    Lazy: {prefix}.f()  #{short_id(l2)}
                    └── {prefix}.f
                        └── {prefix}.MyService
                    """
            ),
            DebugTestCase(
                value=LazyCall(f, singleton=False),
                expected=f"""
                    <∅> Lazy: {prefix}.f()
                    └── {prefix}.f
                        └── {prefix}.MyService
                    """
            )
        )


def test_unknown_debug():
    prefix = "tests.world.test_debug.test_unknown_debug.<locals>"

    with world.test.new():
        class Service1:
            pass

        class Dummy(Service):
            def __init__(self, s: Provide[Service1]):
                pass

        assert_valid(DebugTestCase(
            value=Dummy,
            expected=f"""
                {prefix}.Dummy
                └── /!\\ Unknown: {prefix}.Service1
            """
        ))


def test_singleton_debug():
    with world.test.new():
        world.singletons.add("test", 1)

        assert_valid(DebugTestCase(
            value="test",
            expected="""
                Singleton: 'test' -> 1
            """
        ))


def test_wiring_debug():
    prefix = "tests.world.test_debug.test_wiring_debug.<locals>"

    with world.test.new():
        class Service1(Service):
            pass

        # Not wired, but @inject
        class DummyA(Service):
            __antidote__ = Service.Conf(wiring=None)

            @inject
            def __init__(self, service: Provide[Service1]):
                pass

        assert_valid(DebugTestCase(
            value=DummyA,
            expected=f"""
                {prefix}.DummyA
                └── {prefix}.Service1
            """
        ))

        # Multiple injections
        class DummyB(Service):
            __antidote__ = Service.Conf()

            def __init__(self, s: Provide[Service1]):
                pass

            def get(self, s: Provide[Service1]):
                pass

        assert_valid(DebugTestCase(
            value=DummyB,
            expected=f"""
                {prefix}.DummyB
                ├── {prefix}.Service1
                └── Method: get
                    └── {prefix}.Service1
            """
        ))

        # Methods specified
        class DummyC(Service):
            __antidote__ = Service.Conf().with_wiring(methods=['__init__', 'get'])

            def __init__(self):
                pass

            def get(self, my_service: Provide[Service1]):
                pass

        assert_valid(
            DebugTestCase(
                value=DummyC,
                expected=f"""
                {prefix}.DummyC
                └── Method: get
                    └── {prefix}.Service1
                    """
            ))

        # No injections
        class DummyD(Service):
            def __init__(self):
                pass

            def get(self):
                pass

        assert_valid(
            DebugTestCase(
                value=DummyD,
                expected=f"""
                    {prefix}.DummyD
                    """
            ))


def test_multiline_debug():
    prefix = "tests.world.test_debug.test_multiline_debug.<locals>"

    with world.test.new():
        class MultilineService(Service):
            @classmethod
            def __antidote_debug_repr__(cls):
                return "Multiline\nService"

        class Dummy(Service):
            def __init__(self, s: Provide[MultilineService]):
                pass

        assert_valid(DebugTestCase(
            value=Dummy,
            expected=f"""
                {prefix}.Dummy
                └── Multiline
                    Service
            """
        ))


def test_tag():
    prefix = "tests.world.test_debug.test_tag.<locals>"

    with world.test.new():
        empty_tag = Tag('empty')
        tag = Tag('dummy')

        class S1(Service):
            __antidote__ = Service.Conf(tags=[tag])

        assert_valid(
            DebugTestCase(
                value=Tagged.with_(empty_tag),
                expected=f"No dependencies tagged with "
                         f"Tag('empty')#{short_id(empty_tag)}",
                legend=False
            ),
            DebugTestCase(
                value=Tagged.with_(tag),
                expected=f"""
                <∅> Tagged with Tag('dummy')#{short_id(tag)}
                └── {prefix}.S1
                """
            )
        )


def test_lazy_method_debug():
    prefix = "tests.world.test_debug.test_lazy_method_debug.<locals>"

    with world.test.new():
        class MyService(Service):
            pass

        class Conf(Service):
            def fetch(self, value, service: Provide[MyService]):
                return value

            DATA = LazyMethodCall(fetch)
            KW = LazyMethodCall(fetch)(value='1')
            DATA2 = LazyMethodCall(fetch, singleton=False)
            KW2 = LazyMethodCall(fetch, singleton=False)(value='2')

        assert_valid(
            DebugTestCase(
                value=Conf.DATA,
                expected=f"""
                    Lazy Method: fetch()  #{short_id(Conf.__dict__['DATA'])}
                    ├── {prefix}.Conf.fetch
                    │   └── {prefix}.MyService
                    └── {prefix}.Conf
                    """
            ),
            DebugTestCase(
                value=Conf.KW,
                expected=f"""
        Lazy Method: fetch(*(), **{{'value': '1'}})  #{short_id(Conf.__dict__['KW'])}
        ├── {prefix}.Conf.fetch
        │   └── {prefix}.MyService
        └── {prefix}.Conf
                    """
            ),
            DebugTestCase(
                value=Conf.DATA2,
                expected=f"""
                    <∅> Lazy Method: fetch()
                    ├── {prefix}.Conf.fetch
                    │   └── {prefix}.MyService
                    └── {prefix}.Conf
                    """
            ),
            DebugTestCase(
                value=Conf.KW2,
                expected=f"""
                    <∅> Lazy Method: fetch(*(), **{{'value': '2'}})
                    ├── {prefix}.Conf.fetch
                    │   └── {prefix}.MyService
                    └── {prefix}.Conf
                    """
            )
        )


def test_constants_debug():
    prefix = "tests.world.test_debug.test_constants_debug.<locals>"

    with world.test.new():
        class Conf(Constants):
            TEST = const('1')

            def get(self, key):
                return key

        assert_valid(
            DebugTestCase(
                value=Conf.TEST,
                expected=f"""
                    Const: {prefix}.Conf.TEST
                    └── {prefix}.Conf
                    """
            ))

    with world.test.new():
        class MyService(Service):
            pass

        class Conf(Constants):
            TEST = const('1')

            def get(self, key, service: Provide[MyService] = None):
                return key

        assert_valid(
            DebugTestCase(
                value=Conf.TEST,
                expected=f"""
            Const: {prefix}.Conf.TEST
            ├── {prefix}.Conf.get
            │   └── {prefix}.MyService
            └── {prefix}.Conf
                    """
            ))


def test_custom_scope():
    prefix = "tests.world.test_debug.test_custom_scope.<locals>"

    with world.test.new():
        dummy_scope = world.scopes.new('dummy')

        class MyService(Service):
            __antidote__ = Service.Conf(scope=dummy_scope)

        class BigService(Service):
            def __init__(self, my_service: Provide[MyService]):
                pass

        assert_valid(
            DebugTestCase(
                value=MyService,
                expected=f"""
                    <dummy> {prefix}.MyService
                    """
            ),
            DebugTestCase(
                value=BigService,
                expected=f"""
                    {prefix}.BigService
                    └──<dummy> {prefix}.MyService
                    """
            )
        )


def test_complex_debug():
    with world.test.new():
        tag = Tag()

        class Interface:
            pass

        class Service1(Service):
            pass

        class Service2:
            def __init__(self, service1: Provide[Service1]):
                self.service1 = service1

        class BuildS2(Factory):
            def __call__(self, service1: Provide[Service1] = None) -> Service2:
                return Service2(service1)

        @implementation(Interface)
        def impl():
            return Service4

        class Service3(Service):
            __antidote__ = Service.Conf(singleton=False,
                                        tags=[tag]).with_wiring(
                dependencies=dict(
                    i=Interface @ impl,
                    service2=Service2 @ BuildS2))

            def __init__(self,
                         service1: Provide[Service1],
                         service2: Service2,
                         i: Interface):
                self.service1 = service1
                self.service2 = service2
                self.i = i

            def get(self, service1: Provide[Service1]):
                pass

            X = LazyMethodCall(get)

        class Service4(Interface, Service):
            __antidote__ = Service.Conf(tags=[tag])

            def __init__(self,
                         service1: Provide[Service1],
                         service2: Annotated[Service2, From(BuildS2)],
                         service3: Provide[Service3]):
                self.service1 = service1
                self.service2 = service2
                self.service3 = service3

        @inject
        def f(s: Provide[Service4]):
            pass

        @inject(dependencies=[Service1._with_kwargs(test=1),
                              Service2 @ BuildS2._with_kwargs(option=2)])
        def f_with_options(a, b):
            pass

        prefix = "tests.world.test_debug.test_complex_debug.<locals>"
        assert_valid(
            DebugTestCase(
                value=Tagged.with_(tag),
                depth=0,
                expected=f"""
                    <∅> Tagged with Tag#{short_id(tag)}
                        """
            ),
            DebugTestCase(
                value=Tagged.with_(tag),
                depth=1,
                expected=f"""
                    <∅> Tagged with Tag#{short_id(tag)}
                    ├── {prefix}.Service4
                    └──<∅> {prefix}.Service3
                        """
            ),
            DebugTestCase(
                value=Tagged.with_(tag),
                depth=2,
                expected=f"""
                    <∅> Tagged with Tag#{short_id(tag)}
                    ├── {prefix}.Service4
                    │   ├──<∅> {prefix}.Service3
                    │   ├── {prefix}.Service2 @ {prefix}.BuildS2
                    │   └── {prefix}.Service1
                    └──<∅> {prefix}.Service3
                        ├── Permanent implementation: {prefix}.Interface @ {prefix}.impl
                        ├── {prefix}.Service2 @ {prefix}.BuildS2
                        └── {prefix}.Service1
                        """
            ),
            DebugTestCase(
                value=Tagged.with_(tag),
                depth=3,
                expected=f"""
                <∅> Tagged with Tag#{short_id(tag)}
                ├── {prefix}.Service4
                │   ├──<∅> {prefix}.Service3
                │   │   ├── Permanent implementation: {prefix}.Interface @ {prefix}.impl
                │   │   ├── {prefix}.Service2 @ {prefix}.BuildS2
                │   │   └── {prefix}.Service1
                │   ├── {prefix}.Service2 @ {prefix}.BuildS2
                │   │   ├── {prefix}.BuildS2.__call__
                │   │   │   └── {prefix}.Service1
                │   │   └── {prefix}.BuildS2
                │   └── {prefix}.Service1
                └──<∅> {prefix}.Service3
                    ├── Permanent implementation: {prefix}.Interface @ {prefix}.impl
                    │   └── {prefix}.Service4
                    ├── {prefix}.Service2 @ {prefix}.BuildS2
                    │   ├── {prefix}.BuildS2.__call__
                    │   │   └── {prefix}.Service1
                    │   └── {prefix}.BuildS2
                    └── {prefix}.Service1
                        """
            ),
            DebugTestCase(
                value=Tagged.with_(tag),
                expected=f"""
                <∅> Tagged with Tag#{short_id(tag)}
                ├── {prefix}.Service4
                │   ├──<∅> {prefix}.Service3
                │   │   ├── Permanent implementation: {prefix}.Interface @ {prefix}.impl
                │   │   │   └── /!\\ Cyclic dependency: {prefix}.Service4
                │   │   ├── {prefix}.Service2 @ {prefix}.BuildS2
                │   │   │   ├── {prefix}.BuildS2.__call__
                │   │   │   │   └── {prefix}.Service1
                │   │   │   └── {prefix}.BuildS2
                │   │   └── {prefix}.Service1
                │   ├── {prefix}.Service2 @ {prefix}.BuildS2
                │   │   ├── {prefix}.BuildS2.__call__
                │   │   │   └── {prefix}.Service1
                │   │   └── {prefix}.BuildS2
                │   └── {prefix}.Service1
                └──<∅> {prefix}.Service3
                    ├── Permanent implementation: {prefix}.Interface @ {prefix}.impl
                    │   └── {prefix}.Service4
                    │       ├── /!\\ Cyclic dependency: {prefix}.Service3
                    │       ├── {prefix}.Service2 @ {prefix}.BuildS2
                    │       │   ├── {prefix}.BuildS2.__call__
                    │       │   │   └── {prefix}.Service1
                    │       │   └── {prefix}.BuildS2
                    │       └── {prefix}.Service1
                    ├── {prefix}.Service2 @ {prefix}.BuildS2
                    │   ├── {prefix}.BuildS2.__call__
                    │   │   └── {prefix}.Service1
                    │   └── {prefix}.BuildS2
                    └── {prefix}.Service1

                        """
            ),
            DebugTestCase(
                value=f,
                expected=f"""
                {prefix}.f
                └── {prefix}.Service4
                    ├──<∅> {prefix}.Service3
                    │   ├── Permanent implementation: {prefix}.Interface @ {prefix}.impl
                    │   │   └── /!\\ Cyclic dependency: {prefix}.Service4
                    │   ├── {prefix}.Service2 @ {prefix}.BuildS2
                    │   │   ├── {prefix}.BuildS2.__call__
                    │   │   │   └── {prefix}.Service1
                    │   │   └── {prefix}.BuildS2
                    │   └── {prefix}.Service1
                    ├── {prefix}.Service2 @ {prefix}.BuildS2
                    │   ├── {prefix}.BuildS2.__call__
                    │   │   └── {prefix}.Service1
                    │   └── {prefix}.BuildS2
                    └── {prefix}.Service1
                        """
            ),
            DebugTestCase(
                value=f_with_options,
                expected=f"""
                    {prefix}.f_with_options
                    ├── {prefix}.Service2 @ {prefix}.BuildS2 with kwargs={{'option': 2}}
                    │   ├── {prefix}.BuildS2.__call__
                    │   │   └── {prefix}.Service1
                    │   └── {prefix}.BuildS2
                    └── {prefix}.Service1 with kwargs={{'test': 1}}
                    """
            )
        )
