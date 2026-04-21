# AgentPlane Windows Host And Open-Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` for inline execution in fresh sessions. Every phase must also load `pua`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把本机正式控制面迁移到 `D:\Projects\AgentPlane\`，建立 `Windows 主控制面 + WSL Linux backend + SSH` 的正式执行模型，并把 `sub2api` 接入 `Artifact-First` 交付链路。

**Architecture:** 先把平台、路径、backend 三类差异抽成统一 runtime contract，再把 Windows 本机 bootstrap、迁移复制、artifact-first 合同和 `sub2api` 试点逐阶段接上。每一阶段都以“主线程直接实现 + 最小必要验证 + 立即提交”为默认节奏，不单独插入低效 review 环节。

**Tech Stack:** Python 3.12+, `uv`, `pytest`, `pwsh`, WSL, Bash, Docker, SSH, YAML, repo-owned Codex skills

---

## Phase Protocol

- 每一阶段必须在**新的会话**中开始。
- 每一阶段开场都必须明确声明使用 `pua` 和 `executing-plans`。
- 默认只做主线程直接实现，不额外插入大范围 review。
- 每一阶段结束前必须先提交变更，再做总结。
- 每一阶段只运行与改动直接相关的最小验证；不能验证的部分要明确记录。
- 每一阶段总结必须固定包含以下三段：

### Phase Closeout Template

1. `目标完成情况`
   - 原定目标是否全部完成
   - 未完成项是什么

2. `问题回顾与处理`
   - 执行中遇到的问题
   - 是否已经彻底解决
   - 若未彻底解决，给出简要解决方案和建议

3. `后续规划（按一步到位口径，不展开兼容方案）`
   - 下一步计划
   - 当前剩余未完成工作

### Next Session Starter Rule

- 不手写泛化模板。
- 直接复制当前计划中每个任务末尾的 `next session starter` 段落，作为下一会话的启动指令。

## Windows Host Hardening Rules

- Windows 侧执行 `.ps1` 时，一律使用 `pwsh -NoProfile -ExecutionPolicy Bypass -File ...`；不要在 `\\wsl.localhost\...` 上直接 `.\script.ps1`。
- Windows 侧在 `\\wsl.localhost\...` 工作树里跑 Python 正式入口时，一律经由 `.codex/environments/lib/invoke-agentplane-windows-uv.ps1`；不要直接在 UNC 路径上执行 `uv run ...`。
- `invoke-agentplane-windows-uv.ps1` 必须固定使用 checkout-local `.venv`，并拒绝在 WSL UNC checkout 中启动 Windows 侧 Python 入口。
- 迁移完成后，Windows 正式命令优先在 `D:\Projects\AgentPlane` 执行；wrapper 仍作为统一正式入口保留，避免后续回归到 UNC 直跑。

## File Structure Map

### AgentPlane runtime and CLI

- Create: `agentplane/runtime/__init__.py`
- Create: `agentplane/runtime/platform.py`
- Create: `agentplane/runtime/workspace.py`
- Create: `agentplane/runtime/wsl_bridge.py`
- Create: `agentplane/cli/local_host.py`
- Modify: `agentplane/cli/app.py`
- Modify: `agentplane/cli/host.py`
- Modify: `agentplane/ssh.py`
- Modify: `agentplane/scripts/onepanel/env_targets.py`
- Modify: `agentplane/scripts/onepanel/executor.py`
- Modify: `agentplane/scripts/automation/backup_secrets_r2.py`
- Modify: `agentplane/domain/website/lifecycle.py`
- Modify: `pyproject.toml`

### App delivery and artifact contract

- Create: `agentplane/domain/app/artifacts.py`
- Modify: `agentplane/domain/app/models.py`
- Modify: `agentplane/domain/app/lifecycle.py`
- Modify: `agentplane/domain/app/delivery_handlers.py`
- Modify: `agentplane/cli/apps.py`

### Docs, skills, and repo-owned environment actions

- Modify: `README.md`
- Modify: `AGENTS.md`
- Create: `docs/runbooks/windows-host-governance.md`
- Modify: `docs/reference/app-repository-standard.md`
- Modify: `.codex/environments/environment.toml`
- Create: `.codex/environments/lib/invoke-agentplane-windows-uv.ps1`
- Modify: `.codex/environments/setup/setup.windows.ps1`
- Modify: `.codex/environments/setup/setup.sh`
- Modify: `.codex/environments/setup/setup.linux.sh`
- Modify: `.codex/skills/app-delivery-ops/SKILL.md`
- Modify: `.codex/skills/host-ops/SKILL.md`
- Modify: `.codex/skills/projection-ops/SKILL.md`

### Tests

- Create: `tests/test_runtime_platform.py`
- Create: `tests/test_runtime_workspace.py`
- Create: `tests/test_local_host_cli.py`
- Create: `tests/test_app_artifact_contract.py`
- Modify: `tests/test_cli_entrypoints.py`
- Modify: `tests/test_host_cli.py`
- Modify: `tests/test_ssh_targets.py`
- Modify: `tests/test_app_cli.py`
- Modify: `tests/test_app_delivery_lifecycle.py`
- Modify: `tests/test_project_lifecycle_acceptance.py`
- Modify: `tests/test_app_object_cli.py`
- Modify: `tests/test_pyproject_config.py`
- Modify: `tests/test_docs_no_legacy_terms.py`
- Modify: `tests/test_wsl_first_docs.py`
- Modify: `tests/test_onepanel_plugin_and_skills.py`

### Sub2api pilot

- Modify: `/root/work/sub2api/deploy/agentplane/contract.wsl.yaml`
- Modify: `/root/work/sub2api/deploy/agentplane/contract.yaml`
- Modify: `/root/work/sub2api/deploy/agentplane/contract.prod2.yaml`
- Modify: `/root/work/sub2api/deploy/build-runtime-artifacts.sh`
- Modify: `/root/work/sub2api/deploy/package-runtime-image.sh`
- Modify: `/root/work/sub2api/deploy/README.md`

## Task 1: 建立平台、路径与 backend 基础抽象

**Files:**
- Create: `agentplane/runtime/__init__.py`
- Create: `agentplane/runtime/platform.py`
- Create: `agentplane/runtime/workspace.py`
- Modify: `agentplane/ssh.py`
- Modify: `agentplane/scripts/onepanel/env_targets.py`
- Modify: `agentplane/scripts/onepanel/executor.py`
- Modify: `agentplane/scripts/automation/backup_secrets_r2.py`
- Modify: `agentplane/domain/website/lifecycle.py`
- Modify: `pyproject.toml`
- Test: `tests/test_runtime_platform.py`
- Test: `tests/test_runtime_workspace.py`
- Test: `tests/test_ssh_targets.py`
- Test: `tests/test_pyproject_config.py`

- [ ] **Step 1: 写 failing tests，锁定 host/platform/workspace contract**

```python
def test_selects_wsl_linux_backend_for_windows_host() -> None:
    facts = HostPlatform(os_name="windows", has_wsl=True, is_wsl=False)
    backend = select_linux_backend(facts)
    assert backend.backend_type == "wsl-linux"

def test_workspace_resolves_windows_control_root_and_wsl_backend_root() -> None:
    workspace = resolve_workspace(
        control_root=Path("D:/Projects/AgentPlane"),
        legacy_control_root=Path("/root/work/AgentPlane"),
        private_root=Path("D:/Projects/AgentPlane/secrets"),
        linux_backend_root=Path("/root/work/AgentPlane"),
    )
    assert workspace.control_root.as_posix().endswith("Projects/AgentPlane")
    assert str(workspace.linux_backend_root) == "/root/work/AgentPlane"
```

- [ ] **Step 2: 运行基础测试，确认当前实现还不支持这些 contract**

Run:

```bash
cd /root/work/AgentPlane
uv run pytest tests/test_runtime_platform.py tests/test_runtime_workspace.py tests/test_ssh_targets.py tests/test_pyproject_config.py -q
```

Expected:

- `tests/test_runtime_platform.py` / `tests/test_runtime_workspace.py` 报 `file not found` 或 import error
- 现有测试仍能帮助确认没有误伤现有 SSH contract

- [ ] **Step 3: 实现 runtime 模块和统一 console entry**

```python
@dataclass(frozen=True)
class HostPlatform:
    os_name: str
    has_wsl: bool
    is_wsl: bool

@dataclass(frozen=True)
class LinuxBackend:
    backend_type: Literal["native-posix", "wsl-linux", "ssh-linux"]
    executable: tuple[str, ...]

@dataclass(frozen=True)
class WorkspaceContext:
    control_root: Path
    legacy_control_root: Path | None
    private_root: Path
    linux_backend_root: Path | None
```

`pyproject.toml` 同步加入：

```toml
[project.scripts]
agentplane = "agentplane.cli.app:main"
```

- [ ] **Step 4: 把现有硬编码调用改为 shared runtime helper**

要点：

- `agentplane/ssh.py` 不再只假定 repo 在 Linux 根目录；统一从 `WorkspaceContext` 取 `private_root`
- `agentplane/scripts/onepanel/env_targets.py` 与 `executor.py` 不再直接写死本地 bash/路径策略
- `backup_secrets_r2.py` 与 `agentplane/domain/website/lifecycle.py` 去掉 `/root/work/AgentPlane` 直写，改为通过 workspace resolver 生成

```python
workspace = resolve_workspace_from_repo(repo_root)
secrets_root = workspace.private_root
control_root = workspace.control_root
```

- [ ] **Step 5: 运行最小验证**

Run:

```bash
cd /root/work/AgentPlane
uv run pytest tests/test_runtime_platform.py tests/test_runtime_workspace.py tests/test_ssh_targets.py tests/test_pyproject_config.py -q
uv run python -m agentplane.cli --help
uv run agentplane --help
```

Expected:

- 相关测试通过
- `agentplane` console script 可用
- `agentplane.cli` 帮助输出保持正式入口不变

- [ ] **Step 6: 提交本阶段代码**

```bash
cd /root/work/AgentPlane
git add pyproject.toml agentplane/runtime agentplane/ssh.py agentplane/scripts/onepanel/env_targets.py agentplane/scripts/onepanel/executor.py agentplane/scripts/automation/backup_secrets_r2.py agentplane/domain/website/lifecycle.py tests/test_runtime_platform.py tests/test_runtime_workspace.py tests/test_ssh_targets.py tests/test_pyproject_config.py
git commit -m "feat: add platform and workspace runtime contracts"
```

### Task 1 next session starter

```text
使用 `pua` + `executing-plans`，继续执行 `/root/work/AgentPlane/docs/superpowers/plans/2026-04-11-agentplane-windows-host-opensource-implementation.md` 的 Task 2。
要求：主线程直接实现；只做本阶段直接相关的最小验证；结束后先提交再汇报。
```

## Task 2: 正式化 Windows 主控制面入口与本机迁移 CLI

**Files:**
- Create: `agentplane/runtime/wsl_bridge.py`
- Create: `agentplane/cli/local_host.py`
- Modify: `agentplane/cli/host.py`
- Modify: `agentplane/cli/app.py`
- Modify: `.codex/environments/environment.toml`
- Create: `.codex/environments/lib/invoke-agentplane-windows-uv.ps1`
- Modify: `.codex/environments/setup/setup.windows.ps1`
- Modify: `.codex/environments/setup/setup.sh`
- Modify: `.codex/environments/setup/setup.linux.sh`
- Test: `tests/test_local_host_cli.py`
- Test: `tests/test_host_cli.py`
- Test: `tests/test_cli_entrypoints.py`
- Test: `tests/test_app_onboarding_standard.py`

- [ ] **Step 1: 写 failing tests，锁定 Windows 本机命令面**

```python
def test_host_local_inspect_reports_windows_control_root() -> None:
    payload = run_cli_json("host", "local", "inspect", "--repo-root", "D:/Projects/AgentPlane")
    assert payload["payload"]["control_root"].endswith("D:\\Projects\\AgentPlane")
    assert payload["payload"]["linux_backend"]["backend_type"] == "wsl-linux"

def test_host_local_migration_plan_includes_private_dirs() -> None:
    payload = run_cli_json("host", "local", "migrate", "plan", "--windows-root", "D:\\Projects\\AgentPlane")
    assert "secrets" in payload["payload"]["private_dirs"]
```

- [ ] **Step 2: 实现 `host local` 子命令与 WSL bridge helper**

建议子命令：

- `host local inspect`
- `host local migrate plan`
- `host local migrate copy`
- `host local migrate verify`

核心输出字段：

```json
{
  "control_root": "D:\\Projects\\AgentPlane",
  "legacy_control_root": "/root/work/AgentPlane",
  "private_dirs": ["secrets"],
  "linux_backend": {"backend_type": "wsl-linux", "available": true}
}
```

- [ ] **Step 3: 把 Windows setup 从提示层升级为正式 bootstrap 入口**

`setup.windows.ps1` 需要从只打印提示改为：

- 检查 `wsl.exe` 是否可用
- 检查目标目录 `D:\Projects\AgentPlane\`
- 输出建议使用的 formal CLI
- 能桥接到 WSL backend 做最小探活

```powershell
$wslOk = Get-Command wsl.exe -ErrorAction Stop
Write-Host "Windows control root: D:\Projects\AgentPlane"
Write-Host "Linux backend: WSL"
```

- [ ] **Step 4: 执行最小验证**

Run:

```bash
cd /root/work/AgentPlane
uv run pytest tests/test_local_host_cli.py tests/test_host_cli.py tests/test_cli_entrypoints.py tests/test_app_onboarding_standard.py -q
pwsh -NoProfile -ExecutionPolicy Bypass -File "\\\\wsl.localhost\\Ubuntu\\root\\work\\AgentPlane\\.codex\\environments\\lib\\invoke-agentplane-windows-uv.ps1" python -m agentplane.cli host local inspect
pwsh -NoProfile -ExecutionPolicy Bypass -File "\\\\wsl.localhost\\Ubuntu\\root\\work\\AgentPlane\\.codex\\environments\\setup\\setup.windows.ps1"
```

Expected:

- CLI 能输出本机迁移计划
- Windows setup 不再只是提示语
- `host local inspect` 能明确返回 `wsl-linux`

- [ ] **Step 5: 提交本阶段代码**

```bash
cd /root/work/AgentPlane
git add agentplane/runtime/wsl_bridge.py agentplane/cli/local_host.py agentplane/cli/host.py agentplane/cli/app.py .codex/environments/environment.toml .codex/environments/lib/invoke-agentplane-windows-uv.ps1 .codex/environments/setup/setup.windows.ps1 .codex/environments/setup/setup.sh .codex/environments/setup/setup.linux.sh tests/test_local_host_cli.py tests/test_host_cli.py tests/test_cli_entrypoints.py tests/test_app_onboarding_standard.py
git commit -m "feat: add windows host bootstrap and migration cli"
```

### Task 2 next session starter

```text
使用 `pua` + `executing-plans`，继续执行 `/root/work/AgentPlane/docs/superpowers/plans/2026-04-11-agentplane-windows-host-opensource-implementation.md` 的 Task 3。
要求：主线程直接实现；只做本阶段直接相关的最小验证；结束后先提交再汇报。
```

## Task 3: 把 app delivery 改成 Artifact-First 正式合同

**Files:**
- Create: `agentplane/domain/app/artifacts.py`
- Modify: `agentplane/domain/app/models.py`
- Modify: `agentplane/domain/app/lifecycle.py`
- Modify: `agentplane/domain/app/delivery_handlers.py`
- Modify: `agentplane/cli/apps.py`
- Test: `tests/test_app_artifact_contract.py`
- Test: `tests/test_app_cli.py`
- Test: `tests/test_app_delivery_lifecycle.py`
- Test: `tests/test_project_lifecycle_acceptance.py`

- [ ] **Step 1: 写 failing tests，锁定 artifact-only contract**

```python
def test_validate_contract_requires_artifact_output_path_and_packaging_backend() -> None:
    payload = contract_payload()
    payload["artifact"] = {
        "build_command": "bash deploy/build-runtime-artifacts.sh",
        "output_path": "dist/oplinux",
        "runtime_os": "linux",
        "runtime_arch": "amd64",
    }
    payload["packaging"] = {
        "backend": "wsl-linux",
        "image_name": "sub2api-prod",
        "package_command": "bash deploy/package-runtime-image.sh",
    }
    result = run_validate(payload)
    assert result["ok"] is True
```

- [ ] **Step 2: 把合同从“产镜像”改成“先产 artifact，再装箱”**

建议 contract 结构：

```yaml
schema_version: 2
artifact:
  build_command: bash deploy/build-runtime-artifacts.sh
  output_path: dist/oplinux
  runtime_os: linux
  runtime_arch: amd64
packaging:
  backend: wsl-linux
  image_name: sub2api-prod
  image_tag_rule: <upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>
  package_command: bash deploy/package-runtime-image.sh
```

实现要点：

- `build-artifact` 只构建并校验 artifact，不再宣称已经产出 image
- 新增 `package-runtime` 命令，负责在 Linux backend 执行装箱
- `ship-image` 只接受明确的 image ref

- [ ] **Step 3: 调整 CLI 和 delivery handlers**

关键代码骨架：

```python
def build_artifact(...):
    result = _run_backend_command(contract["artifact"]["build_command"], cwd=app_root)
    return {
        "artifact": {
            "output_path": str(app_root / contract["artifact"]["output_path"]),
            "runtime_os": contract["artifact"]["runtime_os"],
            "runtime_arch": contract["artifact"]["runtime_arch"],
        }
    }

def package_runtime(...):
    return _run_backend_command(contract["packaging"]["package_command"], cwd=app_root)
```

- [ ] **Step 4: 运行最小验证**

Run:

```bash
cd /root/work/AgentPlane
uv run pytest tests/test_app_artifact_contract.py tests/test_app_cli.py tests/test_app_delivery_lifecycle.py tests/test_project_lifecycle_acceptance.py -q
uv run python -m agentplane.cli app delivery validate-contract --target wsl --app sub2api --repo-root /root/work/AgentPlane
```

Expected:

- schema v2 contract 验证通过
- `build-artifact` / `package-runtime` / `ship-image` 语义分离

- [ ] **Step 5: 提交本阶段代码**

```bash
cd /root/work/AgentPlane
git add agentplane/domain/app/artifacts.py agentplane/domain/app/models.py agentplane/domain/app/lifecycle.py agentplane/domain/app/delivery_handlers.py agentplane/cli/apps.py tests/test_app_artifact_contract.py tests/test_app_cli.py tests/test_app_delivery_lifecycle.py tests/test_project_lifecycle_acceptance.py
git commit -m "feat: switch app delivery to artifact first packaging"
```

### Task 3 next session starter

```text
使用 `pua` + `executing-plans`，继续执行 `/root/work/AgentPlane/docs/superpowers/plans/2026-04-11-agentplane-windows-host-opensource-implementation.md` 的 Task 4。
要求：主线程直接实现；只做本阶段直接相关的最小验证；结束后先提交再汇报。
```

## Task 4: 适配 `sub2api` 并完成 `D:\Projects\AgentPlane\` 真实迁移验证

**Files:**
- Modify: `/root/work/sub2api/deploy/agentplane/contract.wsl.yaml`
- Modify: `/root/work/sub2api/deploy/agentplane/contract.yaml`
- Modify: `/root/work/sub2api/deploy/agentplane/contract.prod2.yaml`
- Modify: `/root/work/sub2api/deploy/build-runtime-artifacts.sh`
- Modify: `/root/work/sub2api/deploy/package-runtime-image.sh`
- Modify: `/root/work/sub2api/deploy/README.md`
- Modify: `inventory/apps/catalog.json`
- Modify: `tests/test_app_object_cli.py`
- Modify: `tests/test_sub2api_compose_layout.py`

- [ ] **Step 1: 先让 `sub2api` 合同切到 schema v2 artifact-first**

`/root/work/sub2api/deploy/agentplane/contract.wsl.yaml` 目标形态：

```yaml
schema_version: 2
artifact:
  build_command: bash deploy/build-runtime-artifacts.sh
  output_path: dist/oplinux
  runtime_os: linux
  runtime_arch: amd64
packaging:
  backend: wsl-linux
  image_name: sub2api-prod
  image_tag_rule: <upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>
  package_command: bash deploy/package-runtime-image.sh
```

- [ ] **Step 2: 拆分 `sub2api` 的构建与装箱脚本**

要求：

- `build-runtime-artifacts.sh` 只负责产出 `dist/oplinux`
- `package-runtime-image.sh` 只负责消费 `dist/oplinux` 装箱
- 不允许再在一个脚本里同时承担“构建 artifact + Docker 装箱 + 发布”

```bash
bash deploy/build-runtime-artifacts.sh
test -f dist/oplinux/sub2api
docker build -f deploy/Dockerfile.runtime -t "${IMAGE_NAME}:${IMAGE_TAG}" .
```

- [ ] **Step 3: 执行真实本机迁移复制到 `D:\Projects\AgentPlane\``**

Run:

```powershell
$src = "\\wsl.localhost\Ubuntu\root\work\AgentPlane"
$dst = "D:\Projects\AgentPlane"
robocopy $src $dst /MIR /XD .git .venv tmp __pycache__
robocopy "$src\secrets" "$dst\secrets" /E
```

然后执行：

```powershell
Set-Location D:\Projects\AgentPlane
pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli host local migrate verify --windows-root D:\Projects\AgentPlane
```

- [ ] **Step 4: 用 Windows 主控制面跑 `sub2api` 试点链路**

Run:

```powershell
Set-Location D:\Projects\AgentPlane
pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli app delivery validate-contract --target wsl --app sub2api --repo-root D:\Projects\AgentPlane
pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli app delivery build-artifact --target wsl --app sub2api --repo-root D:\Projects\AgentPlane --execute
pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli app delivery package-runtime --target wsl --app sub2api --repo-root D:\Projects\AgentPlane --image-tag local --execute
pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli app delivery verify --target wsl --app sub2api --repo-root D:\Projects\AgentPlane --dry-run
```

Expected:

- Windows 主控制面可以消费位于 WSL 的 `sub2api` 源码路径
- artifact 在源码环境构建
- Linux packaging 仍在 WSL backend 完成

- [ ] **Step 5: 提交本阶段代码**

AgentPlane:

```bash
cd /root/work/AgentPlane
git add inventory/apps/catalog.json tests/test_app_object_cli.py tests/test_sub2api_compose_layout.py
git commit -m "feat: adapt sub2api for windows hosted control plane"
```

Sub2api:

```bash
cd /root/work/sub2api
git add deploy/agentplane/contract.wsl.yaml deploy/agentplane/contract.yaml deploy/agentplane/contract.prod2.yaml deploy/build-runtime-artifacts.sh deploy/package-runtime-image.sh deploy/README.md
git commit -m "feat: split sub2api artifact build from packaging"
```

### Task 4 next session starter

```text
使用 `pua` + `executing-plans`，继续执行 `/root/work/AgentPlane/docs/superpowers/plans/2026-04-11-agentplane-windows-host-opensource-implementation.md` 的 Task 5。
要求：主线程直接实现；只做本阶段直接相关的最小验证；结束后先提交再汇报。
```

## Task 5: 收口文档、Skill 与开源平台表达

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Create: `docs/runbooks/windows-host-governance.md`
- Modify: `docs/reference/app-repository-standard.md`
- Modify: `.codex/skills/app-delivery-ops/SKILL.md`
- Modify: `.codex/skills/host-ops/SKILL.md`
- Modify: `.codex/skills/projection-ops/SKILL.md`
- Modify: `tests/test_docs_no_legacy_terms.py`
- Modify: `tests/test_wsl_first_docs.py`
- Modify: `tests/test_onepanel_plugin_and_skills.py`

- [ ] **Step 1: 先写 failing docs tests，禁止旧默认叙述继续回流**

```python
def test_readme_declares_windows_host_plus_wsl_backend() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "D:\\Projects\\AgentPlane" in text
    assert "Windows 需要 WSL 作为 Linux backend" in text
```

- [ ] **Step 2: 重写文档口径**

必须达成：

- 不再把 `/root/work/AgentPlane` 当本机默认正式根目录
- 不再把 `WSL-first` 当开源默认叙述
- 明确 `Windows 主控制面 + WSL backend`
- 明确 Linux/macOS 是一等平台
- 明确 Skill 只调用 formal CLI

- [ ] **Step 3: 重写 repo-owned skills**

例如：

```md
- Windows host: run formal CLI from `D:\Projects\AgentPlane`
- Linux backend actions must route through WSL on Windows
- Do not hardcode `/root/work/AgentPlane` as the only local control root
```

- [ ] **Step 4: 运行最小验证**

Run:

```bash
cd /root/work/AgentPlane
uv run pytest tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py tests/test_onepanel_plugin_and_skills.py -q
uv run python -m agentplane.cli host local inspect --repo-root /root/work/AgentPlane
```

Expected:

- 文档回归测试通过
- 技能文本不再把旧 Linux 路径写成唯一正式本机入口

- [ ] **Step 5: 提交本阶段代码**

```bash
cd /root/work/AgentPlane
git add README.md AGENTS.md docs/runbooks/windows-host-governance.md docs/reference/app-repository-standard.md .codex/skills/app-delivery-ops/SKILL.md .codex/skills/host-ops/SKILL.md .codex/skills/projection-ops/SKILL.md tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py tests/test_onepanel_plugin_and_skills.py
git commit -m "docs: formalize windows hosted control plane guidance"
```

## Self-Review

- Spec coverage:
  - `Windows 主控制面` 对应 Task 1、Task 2、Task 4、Task 5
  - `WSL Linux backend` 对应 Task 1、Task 2、Task 4
  - `Artifact-First` 对应 Task 3、Task 4
  - `sub2api` 试点 对应 Task 4
  - `开源化表达` 对应 Task 5
- Placeholder scan:
  - 未保留 `TODO` / `TBD` / “后续补上”
- Type consistency:
  - 统一使用 `HostPlatform`、`LinuxBackend`、`WorkspaceContext`
  - 统一使用 `schema_version: 2`、`artifact` + `packaging`
  - 统一使用 `host local migrate plan|copy|verify`

## Execution Handoff

按你的要求，后续执行方式固定为：

- `Inline Execution`
- 每个阶段在新会话中执行
- 每个阶段强制加载 `pua`
- 不单独展开低效 review
- 每阶段结束时先提交，再按本计划顶部模板汇报
