import json
import tempfile
from pathlib import Path

from agentplane.domain.app.catalog import resolve_app_contract_reference
from agentplane.runtime.host_profile import HostProfile
from agentplane.runtime.target_resolver import TargetResolver


def test_workspace_resolver_returns_canonical_and_resolved_paths() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        app_root = repo_root / "sub2api"
        contract_file = app_root / "deploy" / "agentplane" / "contract.yaml"
        contract_file.parent.mkdir(parents=True, exist_ok=True)
        contract_file.write_text("app_id: sub2api\n", encoding="utf-8")
        catalog_root = repo_root / "inventory" / "apps"
        catalog_root.mkdir(parents=True, exist_ok=True)
        (catalog_root / "catalog.json").write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "app": "sub2api",
                            "repo_name": "sub2api",
                            "repo_root": str(app_root),
                            "service_key": "sub2api",
                            "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        _, result = resolve_app_contract_reference(repo_root, target="prod0-main", app="sub2api")

        assert result.canonical_ref == "apps/sub2api/contracts/prod0-main"
        assert result.resolved_path == contract_file.resolve()


def test_target_resolver_distinguishes_local_and_remote_execution_policies() -> None:
    resolver = TargetResolver(HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True))

    local = resolver.resolve("wsl")
    remote = resolver.resolve("prod0-main")

    assert local.execution_backend == "windows-wsl"
    assert local.ssh_alias is None
    assert local.is_local is True
    assert remote.execution_backend == "ssh-linux"
    assert remote.ssh_alias == "prod0-main"
    assert remote.is_local is False
