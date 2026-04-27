from __future__ import annotations
import pytest
from agentplane.runtime.intent_guard import (
    IntentGuardViolation,
    analyze_intent,
    guard,
)

pytestmark = pytest.mark.integration

class TestAnalyzeIntent:
    def test_empty_argv_is_read_only(self) -> None:
        assert analyze_intent(()) == "read-only"

    def test_ps_is_read_only(self) -> None:
        assert analyze_intent(("ps", "aux")) == "read-only"

    def test_docker_ps_is_read_only(self) -> None:
        assert analyze_intent(("docker", "ps")) == "read-only"

    def test_docker_run_is_mutation(self) -> None:
        assert analyze_intent(("docker", "run", "hello-world")) == "mutation"

    def test_systemctl_status_is_diagnostic(self) -> None:
        assert analyze_intent(("systemctl", "status", "nginx")) == "diagnostic"

    def test_systemctl_start_is_mutation(self) -> None:
        assert analyze_intent(("systemctl", "start", "nginx")) == "mutation"

    def test_git_status_is_read_only(self) -> None:
        assert analyze_intent(("git", "status")) == "read-only"

    def test_git_push_is_mutation(self) -> None:
        # git push is not in the read-only whitelist
        assert analyze_intent(("git", "push")) == "mutation"

    def test_rm_is_mutation(self) -> None:
        assert analyze_intent(("rm", "-rf", "/tmp/foo")) == "mutation"

    def test_cat_is_read_only(self) -> None:
        assert analyze_intent(("cat", "/etc/os-release")) == "read-only"

    def test_sed_with_in_place_flag_is_mutation(self) -> None:
        assert analyze_intent(("sed", "-i", "s/old/new/g", "file.txt")) == "mutation"

    def test_redirection_token_makes_mutation(self) -> None:
        assert analyze_intent(("echo", "hello", ">", "file.txt")) == "mutation"

    def test_unknown_command_defaults_to_mutation(self) -> None:
        assert analyze_intent(("my-custom-tool", "--flag")) == "mutation"

    def test_docker_compose_config_is_read_only(self) -> None:
        assert analyze_intent(("docker", "compose", "config")) == "read-only"

    def test_docker_network_ls_is_read_only(self) -> None:
        assert analyze_intent(("docker", "network", "ls")) == "read-only"

class TestGuard:
    def test_mutation_always_passes(self) -> None:
        guard("mutation", argv=("rm", "-rf", "/"))
        guard("mutation", argv=("docker", "run", "hello"))

    def test_diagnostic_passes_for_diagnostic_command(self) -> None:
        guard("diagnostic", argv=("systemctl", "status", "nginx"))

    def test_diagnostic_fails_for_read_only_command(self) -> None:
        with pytest.raises(IntentGuardViolation):
            guard("diagnostic", argv=("cat", "/etc/passwd"))

    def test_diagnostic_fails_for_mutation_command(self) -> None:
        with pytest.raises(IntentGuardViolation):
            guard("diagnostic", argv=("rm", "-rf", "/tmp"))

    def test_read_only_passes_for_read_only_command(self) -> None:
        guard("read-only", argv=("cat", "/etc/passwd"))
        guard("read-only", argv=("docker", "ps"))

    def test_read_only_fails_for_mutation_command(self) -> None:
        with pytest.raises(IntentGuardViolation):
            guard("read-only", argv=("rm", "-rf", "/tmp"))

    def test_guard_with_stdin_script(self) -> None:
        guard("read-only", argv=("bash", "-s"), stdin_text="cat /etc/os-release")
        with pytest.raises(IntentGuardViolation):
            guard("read-only", argv=("bash", "-s"), stdin_text="rm -rf /tmp")

    def test_guard_violation_message_includes_inferred_intent(self) -> None:
        with pytest.raises(IntentGuardViolation) as exc_info:
            guard("diagnostic", argv=("rm", "-rf", "/tmp"))
        assert "inferred as 'mutation'" in str(exc_info.value)

    def test_guard_violation_suggests_correct_intent(self) -> None:
        with pytest.raises(IntentGuardViolation) as exc_info:
            guard("read-only", argv=("rm", "-rf", "/tmp"))
        assert "--intent=mutation" in str(exc_info.value)
