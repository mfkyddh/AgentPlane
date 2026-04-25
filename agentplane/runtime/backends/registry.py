from __future__ import annotations

from typing import Any, Callable

from agentplane.runtime.execution import BackendRunner


class BackendRegistry:
    """Self-registration registry for execution backends.

    Backends declare themselves via the :func:`register_backend` decorator
    instead of being manually listed in a factory function.
    """

    def __init__(self) -> None:
        self._backend_classes: dict[str, type] = {}

    def register(self, backend_type: str, cls: type) -> type:
        if backend_type in self._backend_classes:
            raise ValueError(f"backend type already registered: {backend_type}")
        self._backend_classes[backend_type] = cls
        return cls

    def build_runner(self) -> BackendRunner:
        instances = {name: cls() for name, cls in self._backend_classes.items()}
        return BackendRunner(instances)

    def registered_types(self) -> tuple[str, ...]:
        return tuple(self._backend_classes.keys())


# Global singleton used by the default build path.
_default_registry: BackendRegistry | None = None


def _get_default_registry() -> BackendRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = BackendRegistry()
    return _default_registry


def register_backend(backend_type: str) -> Callable[[type], type]:
    """Class decorator that registers a backend under *backend_type*.

    Example::

        @register_backend("linux-native")
        class LinuxNativeBackend:
            ...
    """

    def decorator(cls: type) -> type:
        return _get_default_registry().register(backend_type, cls)

    return decorator


def build_backend_runner() -> BackendRunner:
    """Build a BackendRunner from all self-registered backends."""
    return _get_default_registry().build_runner()
