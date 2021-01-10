import pytest

from antidote import world, factory, implementation, Service


def test_implicits():
    with world.test.new():
        world.singletons.add('b', object())
        world.implicits.set({
            'a': 'b'
        })

        assert world.get('a') is world.get('b')


def test_invalid_implicits():
    with world.test.new():
        with pytest.raises(TypeError):
            world.implicits.set(object())


def test_classes_implicits():
    class Interface:
        pass

    with world.test.new():
        class A(Interface, Service):
            pass

        world.implicits.set({Interface: A})
        assert world.get(Interface) is world.get(A)

    with world.test.new():
        class B(Interface):
            pass

        @factory
        def build_interface() -> B:
            return B()

        world.implicits.set({Interface: B @ build_interface})
        assert world.get(Interface) is world.get(B @ build_interface)

    with world.test.new():
        class C(Interface):
            pass

        class D(C, Service):
            pass

        @implementation(C)
        def build_interface():
            return D

        world.implicits.set({Interface: C @ build_interface})
        assert world.get(Interface) is world.get(D)


def test_invalid_classes_implicits():
    class Interface:
        pass

    with world.test.new():
        class A(Service):
            pass

        with pytest.raises(TypeError):
            world.implicits.set({Interface: A})

    with world.test.new():
        class B:
            pass

        @factory
        def build_interface() -> B:
            return B()

        with pytest.raises(TypeError):
            world.implicits.set({Interface: B @ build_interface})

    with world.test.new():
        class C:
            pass

        class D(C, Service):
            pass

        @implementation(C)
        def build_interface():
            return D

        with pytest.raises(TypeError):
            world.implicits.set({Interface: C @ build_interface})
