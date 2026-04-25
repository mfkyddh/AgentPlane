from pathlib import Path

from agentplane.runtime.host_profile import HostProfile
from agentplane.runtime.target_resolver import TargetResolver


def test_resolve_many_returns_list() -> None:
    resolver = TargetResolver(HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True))
    results = resolver.resolve_many(["wsl", "prod0-main"])
    assert len(results) == 2
    assert results[0].is_local is True
    assert results[1].is_local is False


def test_resolve_expression_all_returns_known_targets(tmp_path: Path) -> None:
    resolver = TargetResolver(HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True))
    # Without repo_root: only wsl
    assert resolver.resolve_expression("all") == [resolver.resolve("wsl")]
    assert resolver.resolve_expression("*") == [resolver.resolve("wsl")]

    # With repo_root containing inventory servers
    servers = tmp_path / "inventory" / "servers"
    (servers / "prod0-main").mkdir(parents=True)
    (servers / "prod2-main").mkdir(parents=True)
    results = resolver.resolve_expression("all", repo_root=tmp_path)
    assert [r.target for r in results] == ["wsl", "prod0-main", "prod2-main"]


def test_resolve_expression_comma_separated() -> None:
    resolver = TargetResolver(HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True))
    results = resolver.resolve_expression("wsl,prod0-main")
    assert [r.target for r in results] == ["wsl", "prod0-main"]


def test_resolve_expression_wildcard(tmp_path: Path) -> None:
    resolver = TargetResolver(HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True))
    servers = tmp_path / "inventory" / "servers"
    (servers / "prod0-main").mkdir(parents=True)
    (servers / "prod2-main").mkdir(parents=True)
    (servers / "staging0").mkdir(parents=True)

    results = resolver.resolve_expression("prod*", repo_root=tmp_path)
    assert [r.target for r in results] == ["prod0-main", "prod2-main"]


def test_resolve_expression_unknown_target_falls_back_to_literal() -> None:
    resolver = TargetResolver(HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True))
    results = resolver.resolve_expression("custom-target")
    assert len(results) == 1
    assert results[0].target == "custom-target"
    assert results[0].execution_backend == "ssh-linux"
