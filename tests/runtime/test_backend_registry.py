from agentplane.runtime.backends import BackendRunner, build_backend_runner
from agentplane.runtime.backends.registry import BackendRegistry, register_backend


def test_registry_self_registers_backends() -> None:
    runner = build_backend_runner()
    assert isinstance(runner, BackendRunner)
    # All four default backends should be present.
    assert set(runner._backends.keys()) == {"linux-native", "windows-wsl", "macos-lima", "ssh-linux"}


def test_registry_tracks_registered_types() -> None:
    registry = BackendRegistry()
    registry.register("fake", object)
    assert registry.registered_types() == ("fake",)


def test_registry_duplicate_registration_raises() -> None:
    registry = BackendRegistry()
    registry.register("fake", object)
    try:
        registry.register("fake", str)
        raise AssertionError("should have raised ValueError")
    except ValueError as exc:
        assert "already registered" in str(exc)


def test_register_backend_decorator() -> None:
    registry = BackendRegistry()

    def _decorator(cls: type) -> type:
        return registry.register("demo", cls)

    @_decorator
    class DemoBackend:
        pass

    assert "demo" in registry.registered_types()
    runner = registry.build_runner()
    assert isinstance(runner._backends["demo"], DemoBackend)
