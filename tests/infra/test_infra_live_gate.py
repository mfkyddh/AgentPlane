import tomllib
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from agentplane.domain.infra.live_gate import (
    assert_live_gate_checkout,
    plan_live_gate,
    run_live_gate,
    summarize_capabilities,
)
from agentplane.runtime.host_profile import HostProfile
from agentplane.runtime.platform import HostPlatform
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.integration


class RecordingRunner:
    def __init__(self, returncodes: list[int] | None = None, stdout: str = "ok\n") -> None:
        self.returncodes = list(returncodes or [])
        self.stdout = stdout
        self.calls: list[tuple[tuple[str, ...], Path | str | None, int | None]] = []

    def run(self, argv, *, cwd=None, env=None, timeout=None):  # noqa: ANN001
        self.calls.append((tuple(argv), cwd, timeout))
        returncode = self.returncodes.pop(0) if self.returncodes else 0
        return CompletedProcess(
            args=list(argv),
            returncode=returncode,
            stdout=self.stdout if returncode == 0 else "",
            stderr="" if returncode == 0 else "failed\n",
        )


def test_live_gate_plan_is_default_pytest_excluded_contract() -> None:
    payload = plan_live_gate(REPO_ROOT, profile="wsl")

    assert payload["live_only"] is True
    assert payload["default_pytest"] == "excluded"
    assert payload["required_checkout"] == "single-checkout"
    assert "clone once" in payload["checkout_policy"]
    assert {"live_gate", "integration_wsl", "integration_remote", "docker_required", "ssh_required"}.issubset(
        set(payload["pytest_markers"])
    )
    assert "docker" in summarize_capabilities(payload["steps"])
    assert [step["key"] for step in payload["steps"]][-1] == "service.verify"
    assert "app" not in [step["argv"][5] for step in payload["steps"] if len(step["argv"]) > 5]


def test_wsl_live_gate_keeps_formal_cli_on_host_entry() -> None:
    payload = plan_live_gate(REPO_ROOT, profile="wsl")
    steps = {step["key"]: step for step in payload["steps"]}

    assert steps["toolchain.uv"]["execution"] == "linux-backend"
    assert steps["toolchain.docker"]["execution"] == "linux-backend"
    assert steps["toolchain.docker-compose"]["execution"] == "linux-backend"
    assert steps["host.inventory"]["execution"] == "infra"
    assert steps["projection.verification"]["execution"] == "infra"
    assert steps["projection.runtime-env.verify"]["execution"] == "infra"
    assert steps["service.verify"]["execution"] == "infra"


def test_default_pytest_excludes_live_gate_marker() -> None:
    payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_options = payload["tool"]["pytest"]["ini_options"]

    assert "not live_gate" in pytest_options["addopts"]
    assert any(marker.startswith("live_gate:") for marker in pytest_options["markers"])


def test_prod_live_gate_plan_uses_ssh_and_docker_capabilities() -> None:
    payload = plan_live_gate(REPO_ROOT, profile="prod0-main", app="sub2api")

    assert payload["profile"] == "prod0-main"
    assert "ssh" in summarize_capabilities(payload["steps"])
    assert "docker" in summarize_capabilities(payload["steps"])
    assert payload["steps"][0]["argv"][:5] == ["uv", "run", "python", "-m", "agentplane.cli"]
    assert payload["steps"][0]["argv"][5:9] == ["infra", "remote", "bash", "prod0-main"]


def test_live_gate_run_without_execute_only_returns_plan() -> None:
    runner = RecordingRunner()

    payload = run_live_gate(REPO_ROOT, profile="wsl", execute=False, runner=runner)

    assert payload["ok"] is True
    assert payload["executed"] is False
    assert payload["execute_requested"] is False
    assert payload["results"] == []
    assert runner.calls == []


def test_live_gate_execute_accepts_single_checkout_when_wsl_backend_is_available(tmp_path: Path) -> None:
    assert_live_gate_checkout(
        tmp_path,
        profile="wsl",
        host_platform=HostPlatform(os_name="windows", has_wsl=True, is_wsl=False),
    )

    with pytest.raises(ValueError, match="requires WSL"):
        assert_live_gate_checkout(
            tmp_path,
            profile="wsl",
            host_platform=HostPlatform(os_name="windows", has_wsl=False, is_wsl=False),
        )

    with pytest.raises(ValueError, match="Windows with WSL or inside WSL"):
        assert_live_gate_checkout(
            Path("/"),
            profile="wsl",
            host_platform=HostPlatform(os_name="linux", has_wsl=False, is_wsl=False),
        )


def test_live_gate_execute_uses_command_runner_and_stops_on_first_failure() -> None:
    runner = RecordingRunner(returncodes=[0, 1, 0])

    payload = run_live_gate(
        Path("/"),
        profile="wsl",
        execute=True,
        runner=runner,
        host_platform=HostPlatform(os_name="linux", has_wsl=True, is_wsl=True),
    )

    assert payload["executed"] is True
    assert payload["ok"] is False
    assert [result["ok"] for result in payload["results"]] == [True, False]
    assert len(runner.calls) == 2


def test_live_gate_results_redact_nested_command_stdout() -> None:
    runner = RecordingRunner(stdout='{"apiKey": "secret", "status": "ok"}\n')

    payload = run_live_gate(
        Path("/"),
        profile="wsl",
        execute=True,
        runner=runner,
        host_platform=HostPlatform(os_name="linux", has_wsl=True, is_wsl=True),
    )

    assert payload["ok"] is True
    assert "<redacted>" in payload["results"][0]["stdout"]
    assert "secret" not in payload["results"][0]["stdout"]


def test_run_step_with_backend_resolves_backend_from_host_profile(monkeypatch) -> None:
    from agentplane.domain.infra.live_gate import LiveGateStep, _run_step_with_backend

    captured: dict[str, object] = {}

    class FakeResult:
        backend_type: str = ""
        argv: tuple[str, ...] = ()

        def to_payload(self) -> dict[str, object]:
            return {
                "backend_type": self.backend_type,
                "argv": list(self.argv),
                "returncode": 0,
                "stdout": "ok",
                "stderr": "",
                "ok": True,
            }

    class FakeRunner:
        def execute_spec(self, spec, *, bindings=None):  # noqa: ANN001
            captured["backend_type"] = spec.backend_type
            result = FakeResult()
            result.backend_type = spec.backend_type
            result.argv = spec.argv
            return result

    monkeypatch.setattr(
        "agentplane.domain.infra.live_gate.build_backend_runner",
        FakeRunner,
    )

    step = LiveGateStep(
        key="test.toolchain",
        argv=("docker", "ps"),
        capabilities=("docker",),
        cwd=Path("/"),
        execution="linux-backend",
    )

    # Windows host → windows-wsl
    monkeypatch.setattr(
        "agentplane.domain.infra.live_gate.detect_host_profile",
        lambda: HostProfile(
            os_name="windows",
            linux_backend="windows-wsl",
            supports_docker=True,
            has_wsl=True,
        ),
    )
    _run_step_with_backend(step)
    assert captured["backend_type"] == "windows-wsl"

    # WSL inside → linux-native
    monkeypatch.setattr(
        "agentplane.domain.infra.live_gate.detect_host_profile",
        lambda: HostProfile(
            os_name="linux",
            linux_backend="linux-native",
            supports_docker=True,
            is_wsl=True,
        ),
    )
    _run_step_with_backend(step)
    assert captured["backend_type"] == "linux-native"

    # macOS → macos-lima
    monkeypatch.setattr(
        "agentplane.domain.infra.live_gate.detect_host_profile",
        lambda: HostProfile(
            os_name="macos",
            linux_backend="macos-lima",
            supports_docker=True,
        ),
    )
    _run_step_with_backend(step)
    assert captured["backend_type"] == "macos-lima"
