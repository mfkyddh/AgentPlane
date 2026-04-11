import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_TO_CHECK = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "architecture" / "README.md",
    REPO_ROOT / "docs" / "history" / "index.md",
    REPO_ROOT / "docs" / "archive" / "README.md",
    REPO_ROOT / "docs" / "architecture" / "control-plane.md",
    REPO_ROOT / "docs" / "architecture" / "linux-governance.md",
    REPO_ROOT / "docs" / "architecture" / "agentplane-app-collaboration.md",
    REPO_ROOT / "docs" / "maintainers" / "control-plane-authoring.md",
    REPO_ROOT / "docs" / "runbooks" / "app-project-delivery-workflow.md",
    REPO_ROOT / "docs" / "runbooks" / "bootstrap-secrets.md",
    REPO_ROOT / "docs" / "runbooks" / "control-plane-agent-execution-flow.md",
    REPO_ROOT / "docs" / "runbooks" / "control-plane-domain-onboarding.md",
    REPO_ROOT / "docs" / "runbooks" / "wsl-host-governance.md",
    REPO_ROOT / "docs" / "runbooks" / "wsl-secrets-backup.md",
    REPO_ROOT / "docs" / "runbooks" / "wsl-zzz-skills-sync.md",
)
FORBIDDEN_TERMS = (
    "ops.cli",
    "/root/work/OP_Linux",
    "op-linux-control-plane",
    "OP_Linux_Backups",
    "backups/op_linux/secrets-main",
    "wsl-op-linux-secrets-backup",
    "nginx-ui",
    "nginxwebui",
    "/data/apps/nginx-ui-official",
)
FORBIDDEN_PORT_PATTERNS = (
    re.compile(r"(?<!\d):2053\b"),
    re.compile(r"(?<!\d):2054\b"),
    re.compile(r"(?i)\bport\s+2053\b"),
    re.compile(r"(?i)\bport\s+2054\b"),
)
README_CORE_CONTRACT_LINKS = (
    "[control-plane.md](docs/architecture/control-plane.md)",
    "[linux-governance.md](docs/architecture/linux-governance.md)",
    "[agentplane-app-collaboration.md]"
    "(docs/architecture/agentplane-app-collaboration.md)",
)
ARCHITECTURE_CORE_CONTRACT_LINKS = (
    "[control-plane.md](control-plane.md)",
    "[linux-governance.md](linux-governance.md)",
    "[agentplane-app-collaboration.md](agentplane-app-collaboration.md)",
)
ARCHITECTURE_REFERENCE_LINKS = (
    "[onepanel-api-compatibility.md](../reference/onepanel-api-compatibility.md)",
    "[app-delivery-versioning.md](../reference/app-delivery-versioning.md)",
)
ARCHITECTURE_MAINTAINER_LINKS = (
    "[control-plane-authoring.md](../maintainers/control-plane-authoring.md)",
)
ARCHITECTURE_HISTORY_LINKS = (
    "[docs/history/index.md](../history/index.md)",
    "[docs/archive/README.md](../archive/README.md)",
)
LEGACY_ARCHITECTURE_ENTRY_LINKS = (
    "[automation-stack.md](automation-stack.md)",
    "[control-plane-methodology.md](control-plane-methodology.md)",
    "[control-plane-cli-contract.md](control-plane-cli-contract.md)",
    "[control-plane-task-entry-model.md](control-plane-task-entry-model.md)",
    "[control-plane-inventory-ledger-model.md](control-plane-inventory-ledger-model.md)",
    "[control-plane-skill-contract.md](control-plane-skill-contract.md)",
    "[control-plane-governance-assets.md](control-plane-governance-assets.md)",
)
HOST_DEFAULT_ENTRYPOINTS = (
    "uv run python -m agentplane.cli host inventory wsl",
    "uv run python -m agentplane.cli host audit wsl",
    "uv run python -m agentplane.cli host cleanup plan wsl --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host automation search wsl --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host network audit prod2-main --repo-root /root/work/AgentPlane",
)
SERVICE_DEFAULT_ENTRYPOINTS = (
    "uv run python -m agentplane.cli service search --target prod0-main --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli service verify --target prod0-main --name postgres --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli service verify --target prod0-main --name newapi --repo-root /root/work/AgentPlane",
)
WEBSITE_DEFAULT_ENTRYPOINTS = (
    "uv run python -m agentplane.cli website search --target prod0-main --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli website verify --target prod0-main --alias token --repo-root /root/work/AgentPlane",
)
WEBSITE_PUBLISH_ENTRYPOINTS = (
    "uv run python -m agentplane.cli website publish plan --target prod0-main --config-file /root/work/AgentPlane/secrets/services/token-public-ingress.env --cloudflare-env-file /root/work/AgentPlane/secrets/env/prod-jump.env --repo-root /root/work/AgentPlane",
)
FORMAL_WEBSITE_JSON_ENTRYPOINTS = (
    "uv run python -m agentplane.cli website verify --target prod0-main --alias token --json",
    "uv run python -m agentplane.cli website plan --target prod0-main --alias token --operation reconcile --json",
)
APP_RESOURCE_DEFAULT_ENTRYPOINTS = (
    "uv run python -m agentplane.cli app resource search --target prod0-main --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli app resource verify --target prod0-main --app sub2api --repo-root /root/work/AgentPlane",
)
FORMAL_REMOTE_RUNBOOK_ENTRYPOINTS = (
    "| uv run python -m agentplane.cli host remote bash prod0-main",
)
HOST_WSL_RUNBOOK_ENTRYPOINTS = (
    "uv run python -m agentplane.cli --help",
    "uv run python -m agentplane.cli host audit wsl --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host inventory wsl --repo-root /root/work/AgentPlane",
)
HOST_WSL_RUNBOOK_LOCAL_LINKS = (
    "[bootstrap-secrets.md](bootstrap-secrets.md)",
    "[control-plane.md](../architecture/control-plane.md)",
    "[wsl-secrets-backup.md](wsl-secrets-backup.md)",
)
HOST_WSL_RUNBOOK_FORBIDDEN_DOC_PATHS = (
    "](/root/work/AgentPlane/docs/",
)
HOST_SKILL_ENTRYPOINTS = (
    "uv run python -m agentplane.cli host inventory <target> --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host audit <target> --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host cleanup plan <target> --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host cleanup apply <target> --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host automation search wsl --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host automation get wsl --name wsl-zzz-skills-sync --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host automation verify wsl --name wsl-agentplane-secrets-backup --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host automation plan wsl --name wsl-agentplane-secrets-backup --operation reconcile --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host automation apply wsl --name wsl-agentplane-secrets-backup --operation reconcile --execute --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host network audit <target> --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host network ensure <target> --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host remote bash <target> -- whoami",
    "uv run python -m agentplane.cli host secrets init-data-services <target> --repo-root /root/work/AgentPlane",
    "uv run python -m agentplane.cli host secrets sync-layout <target> --repo-root /root/work/AgentPlane --write",
)
HOST_BRIDGE_BOUNDARIES = (
    "`automation` 已并入 `host`",
    "`network` 已并入 `host`",
    "`panel / firewall` 仍保留在 `onepanel` 域",
)
SERVICE_BRIDGE_BOUNDARIES = (
    "`service` 当前默认入口已经开放到 `uv run python -m agentplane.cli service ...`",
    "formal service 只接受 inventory 中已声明的受管运行服务对象",
    "`control_plane` 为 `compose`、`onepanel-app`、`onepanel-compose` 的 tracked runtime service",
    "`onepanel container / app / project` 已退出公开默认入口",
)
WEBSITE_BRIDGE_BOUNDARIES = (
    "| `website` | 公网入口对象与发布任务 | provider/debug 原生对象 |",
    "| `onepanel` | 1Panel provider/debug 对象，仅保留 panel、firewall、cronjob、task | 正式 website/service/app/projection 入口 |",
    "`website publish` 是 Cloudflare + 1Panel 公网入口的正式任务入口",
)
LONG_LIVED_METADATA_GLOBS = (
    "docs/reference/*.md",
    "docs/maintainers/*.md",
)


class DocsNoLegacyTermsTests(unittest.TestCase):
    def test_selected_docs_have_no_legacy_terms(self) -> None:
        for path in DOCS_TO_CHECK:
            text = path.read_text(encoding="utf-8")
            for term in FORBIDDEN_TERMS:
                with self.subTest(path=str(path), term=term):
                    self.assertNotIn(term, text)
            for pattern in FORBIDDEN_PORT_PATTERNS:
                with self.subTest(path=str(path), pattern=pattern.pattern):
                    self.assertNotRegex(text, pattern)

    def test_entry_indexes_point_to_unified_control_plane_sources(self) -> None:
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        architecture_index_text = (
            REPO_ROOT / "docs" / "architecture" / "README.md"
        ).read_text(encoding="utf-8")

        for link in README_CORE_CONTRACT_LINKS:
            with self.subTest(link=link, doc="README core contracts"):
                self.assertIn(link, readme_text)

        for link in ARCHITECTURE_CORE_CONTRACT_LINKS:
            with self.subTest(link=link, doc="architecture core contracts"):
                self.assertIn(link, architecture_index_text)

        self.assertEqual(
            {link.split("](")[0] for link in README_CORE_CONTRACT_LINKS},
            {link.split("](")[0] for link in ARCHITECTURE_CORE_CONTRACT_LINKS},
        )

        self.assertIn("Core Contracts", architecture_index_text)
        self.assertIn("Reference", architecture_index_text)
        self.assertIn("Maintainers", architecture_index_text)
        self.assertIn("History And Archive", architecture_index_text)

        for link in ARCHITECTURE_REFERENCE_LINKS:
            with self.subTest(link=link, doc="architecture reference links"):
                self.assertIn(link, architecture_index_text)

        for link in ARCHITECTURE_MAINTAINER_LINKS:
            with self.subTest(link=link, doc="architecture maintainer links"):
                self.assertIn(link, architecture_index_text)

        for link in ARCHITECTURE_HISTORY_LINKS:
            with self.subTest(link=link, doc="architecture history links"):
                self.assertIn(link, architecture_index_text)

        self.assertIn("[docs/history/index.md](docs/history/index.md)", readme_text)
        self.assertIn("[docs/archive/README.md](docs/archive/README.md)", readme_text)
        self.assertIn("[docs/history/index.md](../history/index.md)", architecture_index_text)
        self.assertIn("[docs/archive/README.md](../archive/README.md)", architecture_index_text)

        history_index_text = (
            REPO_ROOT / "docs" / "history" / "index.md"
        ).read_text(encoding="utf-8")
        archive_index_text = (
            REPO_ROOT / "docs" / "archive" / "README.md"
        ).read_text(encoding="utf-8")

        self.assertIn("[docs/superpowers/plans/](../superpowers/plans/)", history_index_text)
        self.assertIn(
            "[docs/superpowers/handoffs/](../superpowers/handoffs/)",
            history_index_text,
        )
        self.assertIn(
            "[prod0-main-sub2-control-plane-convergence.md]"
            "(../archive/runbooks/prod0-main-sub2-control-plane-convergence.md)",
            archive_index_text,
        )
        self.assertIn(
            "[1panel-v2.1.5-project.md]"
            "(../archive/architecture/1panel-v2.1.5-project.md)",
            archive_index_text,
        )

        self.assertNotIn(
            "[automation-stack.md](docs/architecture/automation-stack.md)",
            readme_text,
        )
        self.assertNotIn(
            "[control-plane-cli-contract.md]"
            "(docs/architecture/control-plane-cli-contract.md)",
            readme_text,
        )
        for link in LEGACY_ARCHITECTURE_ENTRY_LINKS:
            with self.subTest(link=link, doc="legacy architecture entry links"):
                self.assertNotIn(link, architecture_index_text)

    def test_agents_doc_declares_formal_remote_execution_entrypoint(self) -> None:
        text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(
            "Formal host-scoped network governance must prefer `uv run python -m agentplane.cli host network ...`; "
            "do not route active workflows through a top-level `uv run python -m agentplane.cli network ...` entry.",
            text,
        )
        self.assertIn(
            "Formal host-scoped remote execution must prefer `uv run python -m agentplane.cli host remote bash ...`.",
            text,
        )
        self.assertIn(
            "Formal host-scoped secrets operations must prefer `uv run python -m agentplane.cli host secrets ...`.",
            text,
        )
        self.assertIn(
            "Formal host-scoped cleanup operations must prefer `uv run python -m agentplane.cli host cleanup ...`.",
            text,
        )
        self.assertIn(
            "Formal host-scoped automation operations must prefer `uv run python -m agentplane.cli host automation ...`.",
            text,
        )

    def test_host_docs_point_to_host_cli_as_default_entry(self) -> None:
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        control_plane_text = (
            REPO_ROOT / "docs" / "architecture" / "control-plane.md"
        ).read_text(encoding="utf-8")
        wsl_host_text = (
            REPO_ROOT / "docs" / "runbooks" / "wsl-host-governance.md"
        ).read_text(encoding="utf-8")
        host_skill_text = (
            REPO_ROOT / ".codex" / "skills" / "host-ops" / "SKILL.md"
        ).read_text(encoding="utf-8")

        for text, doc in ((readme_text, "README"),):
            for entrypoint in HOST_DEFAULT_ENTRYPOINTS:
                with self.subTest(doc=doc, entrypoint=entrypoint):
                    self.assertIn(entrypoint, text)

        for entrypoint in HOST_WSL_RUNBOOK_ENTRYPOINTS:
            with self.subTest(doc="WSL host runbook", entrypoint=entrypoint):
                self.assertIn(entrypoint, wsl_host_text)

        for link in HOST_WSL_RUNBOOK_LOCAL_LINKS:
            with self.subTest(doc="WSL host runbook", link=link):
                self.assertIn(link, wsl_host_text)

        for snippet in HOST_WSL_RUNBOOK_FORBIDDEN_DOC_PATHS:
            with self.subTest(doc="WSL host runbook", snippet=snippet):
                self.assertNotIn(snippet, wsl_host_text)

        for entrypoint in HOST_SKILL_ENTRYPOINTS:
            with self.subTest(doc="host skill", entrypoint=entrypoint):
                self.assertIn(entrypoint, host_skill_text)

        for text, doc in (
            (control_plane_text, "control-plane"),
            (host_skill_text, "host skill"),
        ):
            for boundary in HOST_BRIDGE_BOUNDARIES:
                with self.subTest(doc=doc, boundary=boundary):
                    self.assertIn(boundary, text)

    def test_wsl_automation_runbooks_match_agentplane_truth(self) -> None:
        backup_text = (
            REPO_ROOT / "docs" / "runbooks" / "wsl-secrets-backup.md"
        ).read_text(encoding="utf-8")
        zzz_text = (
            REPO_ROOT / "docs" / "runbooks" / "wsl-zzz-skills-sync.md"
        ).read_text(encoding="utf-8")

        self.assertIn("/root/work/AgentPlane/secrets", backup_text)
        self.assertIn("/data/agentplane/secrets-backup/state.json", backup_text)
        self.assertIn("/tmp/agentplane-secrets-backup", backup_text)
        self.assertIn("wsl-agentplane-secrets-backup", backup_text)
        self.assertIn("AgentPlane_Backups", backup_text)
        self.assertIn("backups/agentplane/secrets-main", backup_text)
        self.assertIn(
            "uv run python -m agentplane.cli host automation apply wsl --name wsl-agentplane-secrets-backup --operation run --execute",
            backup_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli host automation verify wsl --name wsl-agentplane-secrets-backup --repo-root /root/work/AgentPlane",
            backup_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli onepanel --env wsl cronjob search --info wsl-agentplane-secrets-backup",
            backup_text,
        )
        self.assertNotIn("ops/scripts/", backup_text)
        self.assertIn("/root/work/AgentPlane", zzz_text)
        self.assertIn(
            "uv run python -m agentplane.cli host automation apply wsl --name wsl-zzz-skills-sync --operation run --execute",
            zzz_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli onepanel --env wsl cronjob search --info wsl-zzz-skills-sync",
            zzz_text,
        )
        self.assertNotIn("ops/scripts/", zzz_text)

    def test_service_docs_point_to_service_cli_as_formal_entry(self) -> None:
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        control_plane_text = (
            REPO_ROOT / "docs" / "architecture" / "control-plane.md"
        ).read_text(encoding="utf-8")
        service_runbook_text = (
            REPO_ROOT / "docs" / "runbooks" / "control-plane-agent-execution-flow.md"
        ).read_text(encoding="utf-8")

        for text, doc in (
            (readme_text, "README"),
            (control_plane_text, "control-plane"),
        ):
            for entrypoint in SERVICE_DEFAULT_ENTRYPOINTS:
                with self.subTest(doc=doc, entrypoint=entrypoint):
                    self.assertIn(entrypoint, text)

        for boundary in SERVICE_BRIDGE_BOUNDARIES:
            with self.subTest(doc="control-plane", boundary=boundary):
                self.assertIn(boundary, control_plane_text)

        self.assertIn(
            "`service` 是正式受管运行服务对象面；固定对象保留 `postgres`、`redis`、`minio`、`mihomo`、`onepanel_openresty`，并扩展到 inventory 中已声明的 tracked runtime service。",
            readme_text,
        )
        self.assertIn(
            "`service` 只接受 inventory 中已声明的受管运行服务对象，不公开 raw 1Panel install id / project id / container id。",
            readme_text,
        )
        self.assertIn(
            "`service` 只面向 inventory 中已声明的 tracked runtime service，不接受 raw 1Panel install id / project id / container id。",
            service_runbook_text,
        )

    def test_website_docs_point_to_website_cli_as_formal_entry(self) -> None:
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        control_plane_text = (
            REPO_ROOT / "docs" / "architecture" / "control-plane.md"
        ).read_text(encoding="utf-8")
        runbook_text = (
            REPO_ROOT / "docs" / "runbooks" / "control-plane-agent-execution-flow.md"
        ).read_text(encoding="utf-8")

        for text, doc in (
            (readme_text, "README"),
            (control_plane_text, "control-plane"),
        ):
            for entrypoint in WEBSITE_DEFAULT_ENTRYPOINTS:
                with self.subTest(doc=doc, entrypoint=entrypoint):
                    self.assertIn(entrypoint, text)

        for boundary in WEBSITE_BRIDGE_BOUNDARIES:
            with self.subTest(doc="control-plane", boundary=boundary):
                self.assertIn(boundary, control_plane_text)

        for entrypoint in FORMAL_WEBSITE_JSON_ENTRYPOINTS:
            with self.subTest(doc="control-plane", entrypoint=entrypoint):
                self.assertIn(entrypoint, control_plane_text)

        for entrypoint in WEBSITE_PUBLISH_ENTRYPOINTS:
            with self.subTest(doc="control-plane", entrypoint=entrypoint):
                self.assertIn(entrypoint, control_plane_text)

        self.assertIn("`website` 当前默认入口已经开放到 `uv run python -m agentplane.cli website ...`", runbook_text)
        self.assertIn("`website publish` 是 Cloudflare + 1Panel 公网入口的正式任务入口", runbook_text)
        self.assertIn("不公开 raw onepanel / cloudflare 参数", runbook_text)
        self.assertNotIn("uv run python -m agentplane.cli onepanel --env prod0-main project search", readme_text)
        self.assertNotIn("uv run python -m agentplane.cli website object verify", control_plane_text)

    def test_non_http_public_endpoints_stay_attached_to_service_truth(self) -> None:
        control_plane_text = (
            REPO_ROOT / "docs" / "architecture" / "control-plane.md"
        ).read_text(encoding="utf-8")
        runbook_text = (
            REPO_ROOT / "docs" / "runbooks" / "prod2-main-relay-trojan.md"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "非 HTTP 协议入口继续附着在 `service` 事实中，不进入 `website publish`。",
            control_plane_text,
        )
        self.assertIn("`relay.zzzai.fun:24443` 不属于 `website` 对象", runbook_text)
        self.assertIn(
            "uv run python -m agentplane.cli service verify --target prod2-main --name relay-trojan",
            runbook_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli service materialize --target prod2-main --name relay-trojan --artifact clash-local-profile",
            runbook_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli service public-endpoint verify --target prod2-main --name relay-trojan",
            runbook_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli service public-endpoint apply --target prod2-main --name relay-trojan",
            runbook_text,
        )
        self.assertNotIn("agentplane/scripts/relay_trojan/ensure_dns_record.py", runbook_text)
        self.assertNotIn("agentplane.scripts.relay_trojan.render_clash_profile", runbook_text)
        self.assertNotIn("agentplane/scripts/internal/ensure_cloudflare_dns_record.py", runbook_text)

    def test_projection_docs_stay_at_thin_contract_level(self) -> None:
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        control_plane_text = (
            REPO_ROOT / "docs" / "architecture" / "control-plane.md"
        ).read_text(encoding="utf-8")

        self.assertIn("`projection` 是正式派生任务域", readme_text)
        self.assertIn("`runtime-env`、`verification`、`fixture`、`ledger`", readme_text)
        self.assertIn(
            "`projection` 当前默认入口已经开放到 `uv run python -m agentplane.cli projection ...`",
            control_plane_text,
        )
        self.assertNotIn("常用 runtime env projection 计划", readme_text)
        self.assertNotIn("常用 runtime env projection 核验", readme_text)
        self.assertNotIn("常用 projection 验证", readme_text)
        self.assertNotIn("常用 projection fixture 计划", readme_text)
        self.assertNotIn("常用 projection ledger 刷新", readme_text)

    def test_app_resource_docs_point_to_app_resource_cli_as_formal_entry(self) -> None:
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        control_plane_text = (
            REPO_ROOT / "docs" / "architecture" / "control-plane.md"
        ).read_text(encoding="utf-8")

        for entrypoint in APP_RESOURCE_DEFAULT_ENTRYPOINTS:
            with self.subTest(doc="control-plane", entrypoint=entrypoint):
                self.assertIn(entrypoint, control_plane_text)

        self.assertIn(
            "inventory/servers/<target>/app-resources.json",
            readme_text,
        )
        self.assertIn("secrets/hosts/<target>/...", readme_text)
        self.assertIn(
            "`app resource` 当前默认入口已经开放到",
            control_plane_text,
        )

        self.assertNotIn("`tenant` 是正式资源租户对象域", readme_text)
        self.assertNotIn("uv run python -m agentplane.cli app resource search", readme_text)
        self.assertNotIn("uv run python -m agentplane.cli app resource verify", readme_text)
        self.assertNotIn("app-resources.json", control_plane_text)
        self.assertNotIn("app_resource_summary", control_plane_text)
        self.assertNotIn("secrets/app-resources/", control_plane_text)

    def test_docker_host_runtime_packaging_template_uses_none_previous_control_plane(self) -> None:
        template_text = (
            REPO_ROOT / "docs" / "runbooks" / "docker-host-runtime-packaging-template.md"
        ).read_text(encoding="utf-8")
        self.assertIn("kind: none", template_text)
        self.assertNotIn("kind: systemd", template_text)

    def test_long_lived_docs_have_metadata_block(self) -> None:
        metadata_regex = re.compile(
            r"(?s)^---\nstatus:\s+.+\nowner:\s+.+\nlast_verified:\s+\d{4}-\d{2}-\d{2}\nsuperseded_by:\s+.+\n---\n"
        )

        files = []
        for pattern in LONG_LIVED_METADATA_GLOBS:
            files.extend(sorted(REPO_ROOT.glob(pattern)))

        for path in files:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=str(path)):
                self.assertRegex(text, metadata_regex)

        authoring_text = (
            REPO_ROOT / "docs" / "maintainers" / "control-plane-authoring.md"
        ).read_text(encoding="utf-8")
        self.assertIn("当前强制 `docs/reference/**/*.md` 与 `docs/maintainers/**/*.md`", authoring_text)
        self.assertNotIn("建议为长期文档补充最小生命周期字段", authoring_text)

    def test_active_runbooks_use_host_network_and_host_remote_bash(self) -> None:
        prod2_text = (
            REPO_ROOT / "docs" / "runbooks" / "prod2-main-1panel-public-access.md"
        ).read_text(encoding="utf-8")
        prod0_access_text = (
            REPO_ROOT / "docs" / "runbooks" / "prod0-main-1panel-public-access.md"
        ).read_text(encoding="utf-8")
        prod0_text = (
            REPO_ROOT / "docs" / "runbooks" / "prod0-main-governance.md"
        ).read_text(encoding="utf-8")
        remote_bash_text = (
            REPO_ROOT / "docs" / "runbooks" / "powershell-wsl-remote-bash.md"
        ).read_text(encoding="utf-8")

        self.assertIn("uv run python -m agentplane.cli host network audit", prod2_text)
        self.assertIn("uv run python -m agentplane.cli host network ensure", prod2_text)
        self.assertNotIn("agentplane.cli network audit/ensure", prod2_text)
        self.assertIn(
            "uv run python -m agentplane.cli website verify \\\n  --target prod2-main",
            prod2_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli projection verification run \\\n  --target prod2-main",
            prod2_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli projection ledger refresh \\\n  --target prod2-main",
            prod2_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli website publish plan \\\n  --target prod2-main",
            prod2_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli website publish apply \\\n  --target prod2-main",
            prod2_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli website publish verify \\\n  --target prod2-main",
            prod2_text,
        )
        self.assertNotIn("ingress ensure-cloudflare-dns01", prod2_text)

        self.assertIn(
            "uv run python -m agentplane.cli projection verification run \\\n  --target prod0-main",
            prod0_access_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli projection ledger refresh \\\n  --target prod0-main",
            prod0_access_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli website get \\\n  --target prod0-main",
            prod0_access_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli website verify \\\n  --target prod0-main",
            prod0_access_text,
        )
        self.assertNotIn("suite run \\\n  --profile prod0-readonly", prod0_access_text)
        self.assertNotIn("--expected-proxy http://127.0.0.1:18080", prod0_access_text)

        for text, doc in (
            (prod0_text, "prod0-main-governance"),
            (remote_bash_text, "powershell-wsl-remote-bash"),
        ):
            for entrypoint in FORMAL_REMOTE_RUNBOOK_ENTRYPOINTS:
                with self.subTest(doc=doc, entrypoint=entrypoint):
                    self.assertIn(entrypoint, text)

        self.assertIn("uv run python -m agentplane.cli host remote bash prod0-main", remote_bash_text)
        self.assertIn("--dry-run", remote_bash_text)
        self.assertIn(
            "uv run python -m agentplane.cli projection verification run --target prod0-main --profile prod0-readonly --repo-root /root/work/AgentPlane --write-report",
            prod0_text,
        )
        self.assertIn(
            "uv run python -m agentplane.cli projection ledger refresh --target prod0-main --repo-root /root/work/AgentPlane --write",
            prod0_text,
        )
        self.assertIn("`prod0-readonly` 的角色是升级前预检，不是同版本验收。", prod0_text)
        self.assertIn("不表示主机已经完成 `v2.1.7` 升级。", prod0_text)
        self.assertIn(
            "--script-file /root/work/AgentPlane/agentplane/scripts/internal/remote/example.sh",
            remote_bash_text,
        )
        self.assertIn(
            "bash agentplane/scripts/internal/repo/self_check.sh",
            (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "正式远端 Bash 入口统一为 `uv run python -m agentplane.cli host remote bash ...`。",
            remote_bash_text,
        )
        self.assertNotIn("正式远端 Bash 入口统一为 `uv run python -m agentplane.cli remote bash ...`。", remote_bash_text)
        self.assertNotIn("ops/scripts/remote/run_remote_bash.sh", remote_bash_text)


if __name__ == "__main__":
    unittest.main()
