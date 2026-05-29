from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from agentplane.runtime.execution import (
    BackendRunner,
    CommandSpec,
    ConcurrentExecutor,
    ExecutionResult,
)

pytestmark = pytest.mark.unit


def _make_result(spec: CommandSpec, ok: bool = True) -> ExecutionResult:
    return ExecutionResult(
        backend_type=spec.backend_type,
        argv=spec.argv,
        display_command=" ".join(spec.argv),
        cwd=spec.cwd,
        returncode=0 if ok else 1,
        stdout=f"output:{spec.argv[-1]}",
        stderr="",
        ok=ok,
    )


def _fake_runner(delay: float = 0.0) -> BackendRunner:
    """Create a BackendRunner whose execute_spec sleeps then returns."""
    runner = MagicMock(spec=BackendRunner)

    def _execute(spec: CommandSpec) -> ExecutionResult:
        if delay > 0:
            time.sleep(delay)
        return _make_result(spec)

    runner.execute_spec.side_effect = _execute
    return runner


class TestConcurrentExecutor:
    def test_execute_single(self) -> None:
        runner = _fake_runner()
        with ConcurrentExecutor(runner, max_workers=2) as executor:
            spec = CommandSpec(backend_type="linux-native", argv=("echo", "hi"))
            result = executor.execute(spec)
        assert result.ok
        assert result.stdout == "output:hi"

    def test_execute_parallel_collects_all_results(self) -> None:
        runner = _fake_runner()
        specs = [
            CommandSpec(backend_type="linux-native", argv=("echo", f"task-{i}"))
            for i in range(6)
        ]
        with ConcurrentExecutor(runner, max_workers=3) as executor:
            results = executor.execute_parallel(specs)
        assert len(results) == 6
        for i, result in enumerate(results):
            assert result.ok
            assert result.stdout == f"output:task-{i}"

    def test_execute_parallel_preserves_order(self) -> None:
        runner = _fake_runner(delay=0.05)
        specs = [
            CommandSpec(backend_type="linux-native", argv=("echo", f"task-{i}"))
            for i in range(4)
        ]
        with ConcurrentExecutor(runner, max_workers=4) as executor:
            results = executor.execute_parallel(specs)
        for i, result in enumerate(results):
            assert result.stdout == f"output:task-{i}"

    def test_execute_parallel_with_failure(self) -> None:
        runner = MagicMock(spec=BackendRunner)

        def _execute(spec: CommandSpec) -> ExecutionResult:
            ok = spec.argv[-1] != "fail"
            return _make_result(spec, ok=ok)

        runner.execute_spec.side_effect = _execute
        specs = [
            CommandSpec(backend_type="linux-native", argv=("echo", "ok-0")),
            CommandSpec(backend_type="linux-native", argv=("echo", "fail")),
            CommandSpec(backend_type="linux-native", argv=("echo", "ok-2")),
        ]
        with ConcurrentExecutor(runner, max_workers=2) as executor:
            results = executor.execute_parallel(specs)
        assert len(results) == 3
        assert results[0].ok
        assert not results[1].ok
        assert results[2].ok

    def test_execute_parallel_stress_eight_commands(self) -> None:
        runner = _fake_runner(delay=0.02)
        specs = [
            CommandSpec(backend_type="linux-native", argv=("echo", f"stress-{i}"))
            for i in range(8)
        ]
        with ConcurrentExecutor(runner, max_workers=4) as executor:
            results = executor.execute_parallel(specs)
        assert len(results) == 8
        assert all(r.ok for r in results)

    def test_context_manager_shutdown(self) -> None:
        runner = _fake_runner()
        executor = ConcurrentExecutor(runner, max_workers=2)
        with executor:
            pass
        assert executor._executor is None

    def test_shutdown_idempotent(self) -> None:
        runner = _fake_runner()
        executor = ConcurrentExecutor(runner, max_workers=2)
        executor.shutdown()
        executor.shutdown()  # should not raise

    def test_max_workers_configurable(self) -> None:
        runner = _fake_runner()
        executor = ConcurrentExecutor(runner, max_workers=8)
        assert executor._max_workers == 8

    def test_concurrent_execution_actually_parallel(self) -> None:
        """Verify tasks run in parallel, not sequentially."""
        observed_threads: list[int] = []
        lock = threading.Lock()

        runner = MagicMock(spec=BackendRunner)

        def _execute(spec: CommandSpec) -> ExecutionResult:
            tid = threading.current_thread().ident
            with lock:
                observed_threads.append(tid)
            time.sleep(0.05)
            return _make_result(spec)

        runner.execute_spec.side_effect = _execute
        specs = [
            CommandSpec(backend_type="linux-native", argv=("echo", f"t-{i}"))
            for i in range(4)
        ]
        with ConcurrentExecutor(runner, max_workers=4) as executor:
            start = time.monotonic()
            results = executor.execute_parallel(specs)
            elapsed = time.monotonic() - start

        assert len(results) == 4
        # 4 tasks each sleeping 50ms with 4 workers should finish in ~50-100ms,
        # not 200ms (sequential)
        assert elapsed < 0.15
        # Multiple distinct thread IDs observed
        assert len(set(observed_threads)) > 1
