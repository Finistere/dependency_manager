import random
import threading
import time
from typing import Callable

from antidote import factory, Tag, Tagged, world
from antidote.core import Container


class A:
    pass


class B:
    pass


class ThreadSafetyTest:
    n_threads = 10
    __state = None

    @classmethod
    def run(cls, target: Callable[[], object], n_threads=None):
        threads = [threading.Thread(target=target)
                   for _ in range(n_threads or cls.n_threads)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

    @staticmethod
    def random_delay(a=0.01, b=None):
        b = b or a
        time.sleep(a + b * random.random())

    @staticmethod
    def unique_id():
        return threading.get_ident(), random.random()

    @classmethod
    def check_locked(cls, failures: list):
        tid = ThreadSafetyTest.unique_id()
        cls.__state = tid
        ThreadSafetyTest.random_delay()
        if cls.__state != tid:
            failures.append(1)


def delayed_new_class(cls):
    def f() -> cls:
        ThreadSafetyTest.random_delay()
        return cls()

    return f


def test_container_instantiation_safety():
    with world.test.new():
        build_a = factory(delayed_new_class(A), singleton=True)
        build_b = factory(delayed_new_class(B), singleton=False)

        singleton_got = []
        non_singleton_got = []

        def worker():
            singleton_got.append(world.get(A @ build_a))
            non_singleton_got.append(world.get(B @ build_b))

        ThreadSafetyTest.run(worker)
        assert len(set(singleton_got)) == 1
        assert len(set(non_singleton_got)) == ThreadSafetyTest.n_threads


def test_tagged_dependencies_instantiation_safety():
    with world.test.new():
        tag = Tag()
        n_dependencies = 40

        for i in range(n_dependencies):
            factory(delayed_new_class(type(f'Service{i}', (object,), {})),
                    singleton=False,
                    tags=[tag])

        tagged: Tagged = world.get(Tagged.with_(tag))
        dependencies = []

        def worker():
            for i, dep in enumerate(tagged.values()):
                dependencies.append((i, dep))

        ThreadSafetyTest.run(worker)

        assert len(set(dependencies)) == n_dependencies
        assert set(enumerate(tagged.values())) == set(dependencies)


# Be sure not have used a fixture to create a new test world as it will
# interfere with this test.
def test_world_safety():
    singletons = []

    def worker():
        with world.test.empty():
            tid = ThreadSafetyTest.unique_id()
            world.singletons.add("x", tid)
            ThreadSafetyTest.random_delay()
            singletons.append((tid, tid == world.get("x")))

    ThreadSafetyTest.run(worker)
    assert ThreadSafetyTest.n_threads == len({tid for (tid, _) in singletons})
    assert all(equal for (_, equal) in singletons)


def test_state_init_safety():
    from antidote._internal import state
    from antidote._internal import world as world_utils

    old_new_container = world_utils.new_container

    called = 0

    def new_container():
        nonlocal called
        called += 1
        ThreadSafetyTest.random_delay()
        return old_new_container()

    state.reset()
    world_utils.new_container = new_container

    try:
        ThreadSafetyTest.run(state.init)
    finally:
        world_utils.new_container = old_new_container

    assert state.current_container() is not None
    assert called == 1


def test_state_override_safety():
    from antidote._internal import state

    state.init()
    container = state.current_container()

    def create(c):
        assert c is container
        return Container()

    def worker():
        ThreadSafetyTest.random_delay()
        state.override(create)

    ThreadSafetyTest.run(worker)
