# AgentPlane Agent-First Control Plane Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` for inline execution in fresh sessions. Every phase must also load `pua`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `AgentPlane` 从当前作者现场驱动的控制面仓库，收敛成面向 Agent 的可 fork 控制面模板仓库，正式建立 canonical truth、resolver、backend runner、bootstrap 和 open-source template 闭环。

**Architecture:** 先切断宿主路径对 truth 的污染，再引入统一 resolver 与 execution contract，把领域动作改成 plan-driven backend execution，最后把 bootstrap、observation、README、skills 和门禁测试全部按模板仓库口径收口。每个 Phase 都按“新会话启动、主线程直接实现、最小必要验证、先提交再总结”的固定节奏推进。

**Tech Stack:** Python 3.12+, `uv`, `pytest`, `pwsh`, WSL, SSH, YAML, JSON, repo-owned Codex skills

---

## Phase Protocol

- 每个 Phase 必须在**新的会话**中执行。
- 每个 Phase 开场必须明确声明使用 `pua` + `executing-plans`。
- 默认减少低效 review，优先主线程直接实现。
- 每个 Phase 结束前必须先提交本阶段全部变更，再输出阶段总结。
- 每个 Phase 只做与改动直接相关的最小必要验证；不能验证的部分必须明确记录。
- 不在同一会话推进下一 Phase。

### Phase Closeout Template

1. `目标完成情况`
   - 原定目标是否已经全部完成
   - 未完成项是什么

2. `问题回顾与处理`
   - 执行过程中碰到了哪些问题
   - 这些问题是否已经彻底解决，或者已经记录下来以防止后续再次发生
   - 若未彻底解决，给出简要的解决方案和建议

3. `后续规划（不考虑兼容方案，如何一步到位）`
   - 下一步计划是什么
   - 当前还有哪些工作尚未完成

### Next Session Starter Rule

- 每个 Task 末尾都提供可直接复制的新会话启动指令。
- 后续会话不再重新设计方案，直接按当前计划执行对应 Task。
- 若阶段中出现阻塞，先在本阶段范围内解决；只有当阻塞会改变后续架构边界时，才回到计划文档修订。

## File Structure Map

### Phase 1: Canonical truth, path policy, and gate tests

- Create: `docs/architecture/agent-first-template-truth-model.md`
- Create: `docs/reference/control-plane-path-policy.md`
- Create: `agentplane/runtime/path_policy.py`
- Create: `tests/test_truth_path_policy.py`
- Modify: `agentplane/domain/app/catalog.py`
- Modify: `agentplane/domain/app/object_handlers.py`
- Modify: `agentplane/domain/app/resource_paths.py`
- Modify: `agentplane/scripts/onepanel/ledger.py`
- Modify: `tests/test_app_object_cli.py`
- Modify: `tests/test_inventory_generation.py`
- Modify: `tests/test_docs_no_legacy_terms.py`

### Phase 2: Host profile and resolver layer

- Create: `agentplane/runtime/host_profile.py`
- Create: `agentplane/runtime/resolution.py`
- Create: `agentplane/runtime/secret_resolver.py`
- Create: `agentplane/runtime/target_resolver.py`
- Create: `tests/test_runtime_resolution.py`
- Modify: `agentplane/runtime/__init__.py`
- Modify: `agentplane/runtime/platform.py`
- Modify: `agentplane/runtime/workspace.py`
- Modify: `agentplane/runtime/wsl_bridge.py`
- Modify: `agentplane/cli/local_host.py`
- Modify: `agentplane/domain/app/catalog.py`
- Modify: `agentplane/ssh.py`
- Modify: `tests/test_runtime_platform.py`
- Modify: `tests/test_runtime_workspace.py`
- Modify: `tests/test_local_host_cli.py`

### Phase 3: Unified execution contract and backend runners

- Create: `agentplane/runtime/execution.py`
- Create: `agentplane/runtime/backends/__init__.py`
- Create: `agentplane/runtime/backends/linux_native.py`
- Create: `agentplane/runtime/backends/windows_wsl.py`
- Create: `agentplane/runtime/backends/macos_lima.py`
- Create: `agentplane/runtime/backends/ssh_linux.py`
- Create: `tests/test_backend_runner.py`
- Modify: `agentplane/runtime/wsl_bridge.py`
- Modify: `agentplane/cli/remote.py`
- Modify: `agentplane/cli/apps.py`
- Modify: `agentplane/domain/app/lifecycle.py`
- Modify: `agentplane/domain/app/delivery_handlers.py`
- Modify: `tests/test_app_delivery_lifecycle.py`
- Modify: `tests/test_remote_cli.py`

### Phase 4: Domain surface refactor to backend-aware execution

- Modify: `agentplane/cli/inventory.py`
- Modify: `agentplane/cli/audit.py`
- Modify: `agentplane/cli/apps.py`
- Modify: `agentplane/cli/service.py`
- Modify: `agentplane/cli/website.py`
- Modify: `agentplane/cli/projection.py`
- Modify: `agentplane/domain/service/lifecycle.py`
- Modify: `agentplane/domain/website/lifecycle.py`
- Modify: `agentplane/domain/projection/runtime_env.py`
- Modify: `agentplane/scripts/onepanel/verification.py`
- Modify: `tests/test_wsl_audit.py`
- Modify: `tests/test_host_cli.py`
- Modify: `tests/test_app_cli.py`
- Modify: `tests/test_service_cli.py`
- Modify: `tests/test_website_cli.py`
- Modify: `tests/test_projection_runtime_env_cli.py`

### Phase 5: Bootstrap and local secrets productization

- Create: `agentplane/cli/bootstrap.py`
- Create: `agentplane/runtime/bootstrap.py`
- Create: `templates/secrets/local/control-plane/README.md`
- Create: `templates/secrets/targets/_template/README.md`
- Create: `tests/test_bootstrap_cli.py`
- Modify: `agentplane/cli/app.py`
- Modify: `agentplane/cli/secrets.py`
- Modify: `README.md`
- Modify: `docs/runbooks/bootstrap-secrets.md`
- Modify: `tests/test_secrets_host_layout.py`
- Modify: `tests/test_app_onboarding_standard.py`

### Phase 6: Observation isolation and tracked output cleanup

- Create: `agentplane/runtime/observation.py`
- Create: `tests/test_observation_contracts.py`
- Modify: `agentplane/domain/app/object_handlers.py`
- Modify: `agentplane/domain/app/resource_handlers.py`
- Modify: `agentplane/domain/service/handlers.py`
- Modify: `agentplane/scripts/onepanel/ledger.py`
- Modify: `agentplane/cli/projection.py`
- Modify: `tests/test_inventory_generation.py`
- Modify: `tests/test_app_resource_object_cli.py`
- Modify: `tests/test_service_lifecycle.py`

### Phase 7: Open-source template closure

- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/architecture/README.md`
- Modify: `docs/reference/app-repository-standard.md`
- Modify: `docs/runbooks/control-plane-domain-onboarding.md`
- Modify: `docs/runbooks/control-plane-agent-execution-flow.md`
- Modify: `.codex/skills/host-ops/SKILL.md`
- Modify: `.codex/skills/app-delivery-ops/SKILL.md`
- Modify: `.codex/skills/app-resource-ops/SKILL.md`
- Modify: `.codex/skills/inventory-ledger-ops/SKILL.md`
- Modify: `.codex/skills/projection-ops/SKILL.md`
- Modify: `tests/test_docs_no_legacy_terms.py`
- Modify: `tests/test_wsl_first_docs.py`
- Modify: `tests/test_onepanel_plugin_and_skills.py`

## Task 1: Canonical Truth Cut

**Files:**
- Create: `docs/architecture/agent-first-template-truth-model.md`
- Create: `docs/reference/control-plane-path-policy.md`
- Create: `agentplane/runtime/path_policy.py`
- Create: `tests/test_truth_path_policy.py`
- Modify: `agentplane/domain/app/catalog.py`
- Modify: `agentplane/domain/app/object_handlers.py`
- Modify: `agentplane/domain/app/resource_paths.py`
- Modify: `agentplane/scripts/onepanel/ledger.py`
- Modify: `tests/test_app_object_cli.py`
- Modify: `tests/test_inventory_generation.py`
- Modify: `tests/test_docs_no_legacy_terms.py`

- [ ] **Step 1: 先写失败测试，锁定“宿主路径禁入 truth”的 contract**

```python
def test_truth_contract_rejects_windows_drive_paths() -> None:
    assert is_host_specific_path("D:/Projects/AgentPlane") is True

def test_truth_contract_rejects_unc_paths() -> None:
    assert is_host_specific_path(r"\\\\wsl.localhost\\Ubuntu\\root\\work\\sub2api") is True

def test_truth_contract_allows_canonical_refs() -> None:
    assert is_host_specific_path("apps/sub2api/contracts/prod0-main") is False
```

- [ ] **Step 2: 运行最小测试，确认当前仓库还允许这些污染进入输出**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_app_object_cli.py tests/test_inventory_generation.py tests/test_docs_no_legacy_terms.py -q
```

Expected:

- 至少一部分断言会暴露 `resolved_path` 和旧路径口径仍然渗入输出或文档。

- [ ] **Step 3: 实现 path policy，并把 truth / ledger / verification 的字段边界写成正式文档**

```python
HOST_PATH_PREFIXES = (
    "D:/",
    "C:/",
    "/root/",
    "/mnt/",
    r"\\\\wsl.localhost\\",
)

def is_host_specific_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return normalized.startswith(("D:/", "C:/", "/root/", "/mnt/")) or value.startswith("\\\\wsl.localhost\\")

def assert_canonical_ref(value: str) -> str:
    if is_host_specific_path(value):
        raise ValueError(f"host-specific path is not allowed in canonical truth: {value}")
    return value
```

文档中要明确三条规则：

- `truth` 只保存 canonical ref
- `ledger` 可以保存可消费摘要，但不写宿主访问路径
- `verification` 才允许出现宿主观察值

- [ ] **Step 4: 收口 catalog / object / ledger 输出，禁止把宿主路径回写进 tracked 字段**

要点：

- `agentplane/domain/app/catalog.py` 继续做运行时解析，但 canonical 字段保持逻辑引用
- `agentplane/domain/app/object_handlers.py` 输出同时区分 `canonical_ref` 与 `resolved_path`
- `agentplane/scripts/onepanel/ledger.py` 刷新 ledger 时不再把 `resolved_path` 当作真源字段
- `agentplane/domain/app/resource_paths.py` 负责统一 path policy 入口，不再分散判断

- [ ] **Step 5: 运行最小验证**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_truth_path_policy.py tests/test_app_object_cli.py tests/test_inventory_generation.py tests/test_docs_no_legacy_terms.py -q
uv run python -m agentplane.cli app object get --target prod0-main --app sub2api --repo-root D:/Projects/AgentPlane
```

Expected:

- gate tests 通过
- `app object get` 输出中可同时看到 `canonical_ref` 与 `resolved_path`
- tracked truth / ledger 字段不再直接泄露宿主路径

- [ ] **Step 6: 提交本阶段变更**

```bash
cd D:/Projects/AgentPlane
git add docs/architecture/agent-first-template-truth-model.md docs/reference/control-plane-path-policy.md agentplane/runtime/path_policy.py agentplane/domain/app/catalog.py agentplane/domain/app/object_handlers.py agentplane/domain/app/resource_paths.py agentplane/scripts/onepanel/ledger.py tests/test_truth_path_policy.py tests/test_app_object_cli.py tests/test_inventory_generation.py tests/test_docs_no_legacy_terms.py
git commit -m "feat: enforce canonical truth path policy"
```

- [ ] **Step 7: 按固定模板输出 Phase 1 收口总结**

直接使用本计划顶部的 `Phase Closeout Template`，不要省略“问题是否已经记录防回归”。

### Task 1 next session starter

```text
先加载 `pua` skill。

使用 `executing-plans`，执行 `D:/Projects/AgentPlane/docs/superpowers/plans/2026-04-11-agentplane-agent-first-control-plane-template-implementation.md` 的 Task 1。
要求：
1. 优先主线程直接实现，不做低效 review。
2. 只做本阶段直接相关的最小必要验证。
3. 本阶段结束前必须先提交变更，再按固定模板输出收口总结。
4. 阶段完成后停止，不进入 Task 2。
```

## Task 2: Resolver Introduction

**Files:**
- Create: `agentplane/runtime/host_profile.py`
- Create: `agentplane/runtime/resolution.py`
- Create: `agentplane/runtime/secret_resolver.py`
- Create: `agentplane/runtime/target_resolver.py`
- Create: `tests/test_runtime_resolution.py`
- Modify: `agentplane/runtime/__init__.py`
- Modify: `agentplane/runtime/platform.py`
- Modify: `agentplane/runtime/workspace.py`
- Modify: `agentplane/runtime/wsl_bridge.py`
- Modify: `agentplane/cli/local_host.py`
- Modify: `agentplane/domain/app/catalog.py`
- Modify: `agentplane/ssh.py`
- Modify: `tests/test_runtime_platform.py`
- Modify: `tests/test_runtime_workspace.py`
- Modify: `tests/test_local_host_cli.py`

- [ ] **Step 1: 先写失败测试，锁定 resolver 的输入输出**

```python
def test_workspace_resolver_returns_canonical_and_resolved_paths() -> None:
    result = resolve_app_contract(
        app_name="sub2api",
        contract_ref="apps/sub2api/contracts/prod0-main",
        host_profile=HostProfile(os_name="windows", linux_backend="windows-wsl"),
    )
    assert result.canonical_ref == "apps/sub2api/contracts/prod0-main"
    assert result.resolved_path.endswith("deploy/agentplane/contract.yaml")
```

- [ ] **Step 2: 运行 resolver 相关测试，确认当前运行时对象还不完整**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_runtime_platform.py tests/test_runtime_workspace.py tests/test_local_host_cli.py -q
```

Expected:

- 现有 runtime 测试需要补齐新的 resolver contract，当前不会全部满足。

- [ ] **Step 3: 引入 HostProfile / Resolver 族对象**

```python
@dataclass(frozen=True)
class HostProfile:
    os_name: Literal["windows", "linux", "macos"]
    linux_backend: Literal["windows-wsl", "linux-native", "macos-lima", "ssh-linux"]
    supports_docker: bool

@dataclass(frozen=True)
class ResolvedReference:
    canonical_ref: str
    resolved_path: Path
```

实现要求：

- `WorkspaceResolver` 只负责 repo、artifact staging、private root 等工作区绑定
- `SecretResolver` 只负责 `secret_ref -> local path`
- `TargetResolver` 只负责 target truth、SSH alias、execution policy
- `wsl_bridge.py` 不再承担领域判断，只保留 WSL backend 适配

- [ ] **Step 4: 把现有 CLI 和 catalog 接到 resolver 上**

要点：

- `agentplane/cli/local_host.py` 提供 `inspect-local` 风格的 profile 输出
- `agentplane/domain/app/catalog.py` 改成从 resolver 拿 `resolved_path`
- `agentplane/ssh.py` 不再自己猜测 secrets/ssh 路径

- [ ] **Step 5: 运行最小验证**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_runtime_platform.py tests/test_runtime_workspace.py tests/test_runtime_resolution.py tests/test_local_host_cli.py -q
uv run python -m agentplane.cli host local inspect --repo-root D:/Projects/AgentPlane
```

Expected:

- 新的 resolver tests 通过
- `host local inspect` 能输出 host profile、workspace bindings、path policy

- [ ] **Step 6: 提交本阶段变更**

```bash
cd D:/Projects/AgentPlane
git add agentplane/runtime/__init__.py agentplane/runtime/platform.py agentplane/runtime/workspace.py agentplane/runtime/wsl_bridge.py agentplane/runtime/host_profile.py agentplane/runtime/resolution.py agentplane/runtime/secret_resolver.py agentplane/runtime/target_resolver.py agentplane/cli/local_host.py agentplane/domain/app/catalog.py agentplane/ssh.py tests/test_runtime_platform.py tests/test_runtime_workspace.py tests/test_runtime_resolution.py tests/test_local_host_cli.py
git commit -m "feat: add host and reference resolver layer"
```

- [ ] **Step 7: 按固定模板输出 Phase 2 收口总结**

### Task 2 next session starter

```text
先加载 `pua` skill。

使用 `executing-plans`，执行 `D:/Projects/AgentPlane/docs/superpowers/plans/2026-04-11-agentplane-agent-first-control-plane-template-implementation.md` 的 Task 2。
要求：
1. 优先主线程直接实现，不做低效 review。
2. 只做本阶段直接相关的最小必要验证。
3. 本阶段结束前必须先提交变更，再按固定模板输出收口总结。
4. 阶段完成后停止，不进入 Task 3。
```

## Task 3: Backend Contract Unification

**Files:**
- Create: `agentplane/runtime/execution.py`
- Create: `agentplane/runtime/backends/__init__.py`
- Create: `agentplane/runtime/backends/linux_native.py`
- Create: `agentplane/runtime/backends/windows_wsl.py`
- Create: `agentplane/runtime/backends/macos_lima.py`
- Create: `agentplane/runtime/backends/ssh_linux.py`
- Create: `tests/test_backend_runner.py`
- Modify: `agentplane/runtime/wsl_bridge.py`
- Modify: `agentplane/cli/remote.py`
- Modify: `agentplane/cli/apps.py`
- Modify: `agentplane/domain/app/lifecycle.py`
- Modify: `agentplane/domain/app/delivery_handlers.py`
- Modify: `tests/test_app_delivery_lifecycle.py`
- Modify: `tests/test_remote_cli.py`

- [ ] **Step 1: 先写失败测试，锁定 ExecutionPlan 和 backend runner**

```python
def test_windows_wsl_backend_wraps_linux_command() -> None:
    plan = ExecutionPlan(
        backend_type="windows-wsl",
        cwd_ref="workspace.control_root",
        argv=("docker", "ps"),
        env_refs=(),
        input_refs=(),
        expected_outputs=(),
        capabilities=("docker",),
        timeout=300,
    )
    rendered = WindowsWslBackend().render(plan)
    assert rendered.argv[:3] == ("wsl.exe", "-e", "bash")
```

- [ ] **Step 2: 运行执行层相关测试，确认当前领域动作还在直调 shell**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_app_delivery_lifecycle.py tests/test_remote_cli.py -q
```

Expected:

- 当前测试和实现会暴露 `bash` / `docker` / `ssh` 直调尚未统一收口。

- [ ] **Step 3: 实现 ExecutionPlan、ExecutionResult、BackendRunner**

```python
@dataclass(frozen=True)
class ExecutionPlan:
    backend_type: Literal["linux-native", "windows-wsl", "macos-lima", "ssh-linux"]
    cwd_ref: str
    argv: tuple[str, ...]
    env_refs: tuple[str, ...]
    input_refs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    capabilities: tuple[str, ...]
    timeout: int
```

要求：

- backend runner 负责 capability 检查、cwd 解析、argv 渲染、错误封装
- `wsl_bridge.py` 退化成 `windows-wsl` backend 的底层适配器
- `agentplane/cli/remote.py` 开始走 `ssh-linux` backend，不再自己拼最终命令串

- [ ] **Step 4: 先把 app delivery 和 remote 入口切到 ExecutionPlan**

要点：

- `agentplane/domain/app/lifecycle.py` 只负责生成 plan
- `agentplane/domain/app/delivery_handlers.py` 只做参数编排和结果解释
- `agentplane/cli/apps.py` / `agentplane/cli/remote.py` 不再直接决定 `bash -lc` / `wsl.exe`

- [ ] **Step 5: 运行最小验证**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_backend_runner.py tests/test_app_delivery_lifecycle.py tests/test_remote_cli.py -q
uv run python -m agentplane.cli host remote bash prod0-main --repo-root D:/Projects/AgentPlane --dry-run
uv run python -m agentplane.cli app delivery deploy --target prod0-main --app sub2api --repo-root D:/Projects/AgentPlane --dry-run
```

Expected:

- runner tests 通过
- `remote bash --dry-run` 和 `app delivery deploy --dry-run` 输出 plan-driven backend 信息，而不是宿主命令拼接细节

- [ ] **Step 6: 提交本阶段变更**

```bash
cd D:/Projects/AgentPlane
git add agentplane/runtime/wsl_bridge.py agentplane/runtime/execution.py agentplane/runtime/backends agentplane/cli/remote.py agentplane/cli/apps.py agentplane/domain/app/lifecycle.py agentplane/domain/app/delivery_handlers.py tests/test_backend_runner.py tests/test_app_delivery_lifecycle.py tests/test_remote_cli.py
git commit -m "feat: unify execution backend contracts"
```

- [ ] **Step 7: 按固定模板输出 Phase 3 收口总结**

### Task 3 next session starter

```text
先加载 `pua` skill。

使用 `executing-plans`，执行 `D:/Projects/AgentPlane/docs/superpowers/plans/2026-04-11-agentplane-agent-first-control-plane-template-implementation.md` 的 Task 3。
要求：
1. 优先主线程直接实现，不做低效 review。
2. 只做本阶段直接相关的最小必要验证。
3. 本阶段结束前必须先提交变更，再按固定模板输出收口总结。
4. 阶段完成后停止，不进入 Task 4。
```

## Task 4: Domain Surface Refactor

**Files:**
- Modify: `agentplane/cli/inventory.py`
- Modify: `agentplane/cli/audit.py`
- Modify: `agentplane/cli/apps.py`
- Modify: `agentplane/cli/service.py`
- Modify: `agentplane/cli/website.py`
- Modify: `agentplane/cli/projection.py`
- Modify: `agentplane/domain/service/lifecycle.py`
- Modify: `agentplane/domain/website/lifecycle.py`
- Modify: `agentplane/domain/projection/runtime_env.py`
- Modify: `agentplane/scripts/onepanel/verification.py`
- Modify: `tests/test_wsl_audit.py`
- Modify: `tests/test_host_cli.py`
- Modify: `tests/test_app_cli.py`
- Modify: `tests/test_service_cli.py`
- Modify: `tests/test_website_cli.py`
- Modify: `tests/test_projection_runtime_env_cli.py`

- [ ] **Step 1: 先写失败测试，锁定 Windows 主控制面下的正式执行路径**

```python
def test_host_inventory_wsl_uses_backend_runner() -> None:
    result = run_cli_json("host", "inventory", "wsl", "--repo-root", "D:/Projects/AgentPlane")
    assert result["backend_type"] == "windows-wsl"

def test_host_audit_wsl_reads_linux_paths_via_backend() -> None:
    result = run_cli_json("host", "audit", "wsl", "--repo-root", "D:/Projects/AgentPlane")
    assert result["path_check_mode"] == "backend-exec"
```

- [ ] **Step 2: 运行直接相关测试和命令，复现实存问题**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_wsl_audit.py tests/test_host_cli.py tests/test_app_cli.py tests/test_service_cli.py tests/test_website_cli.py tests/test_projection_runtime_env_cli.py -q
uv run python -m agentplane.cli host inventory wsl --repo-root D:/Projects/AgentPlane
uv run python -m agentplane.cli host audit wsl --repo-root D:/Projects/AgentPlane
```

Expected:

- 当前失败会暴露 Windows 下仍然本机直读 Linux 路径、本机直跑 `docker` 或 `curl` 的问题。

- [ ] **Step 3: 把 host / app / service / website / projection 改成 backend-aware**

重点修改：

- `agentplane/cli/inventory.py` 和 `agentplane/cli/audit.py` 不再在 Windows 本机直接判断 `/root/...` 和 `/data/...`
- `agentplane/cli/apps.py` 不再在领域层直接跑 `bash`、`docker compose`、`curl`
- `agentplane/domain/service/lifecycle.py`、`agentplane/domain/website/lifecycle.py`、`agentplane/domain/projection/runtime_env.py` 生成 `ExecutionPlan`

```python
plan = build_inventory_plan(target="wsl", repo_root=repo_root)
result = backend_runner.execute(plan, resolver=resolver)
```

- [ ] **Step 4: 跑通最关键的正式主链路**

至少要覆盖：

- `host inventory wsl`
- `host audit wsl`
- `app delivery validate-contract`
- `app delivery deploy --dry-run`
- `projection runtime-env` 或对应正式 projection surface

- [ ] **Step 5: 运行最小验证**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_wsl_audit.py tests/test_host_cli.py tests/test_app_cli.py tests/test_service_cli.py tests/test_website_cli.py tests/test_projection_runtime_env_cli.py -q
uv run python -m agentplane.cli host inventory wsl --repo-root D:/Projects/AgentPlane
uv run python -m agentplane.cli host audit wsl --repo-root D:/Projects/AgentPlane
uv run python -m agentplane.cli app delivery validate-contract --target prod0-main --app sub2api --repo-root D:/Projects/AgentPlane
uv run python -m agentplane.cli app delivery deploy --target prod0-main --app sub2api --repo-root D:/Projects/AgentPlane --dry-run
```

Expected:

- Windows 主控制面下的 WSL 相关命令不再依赖宿主随机 PATH
- 主链路测试通过或仅剩已知、已记录的外部依赖问题

- [ ] **Step 6: 提交本阶段变更**

```bash
cd D:/Projects/AgentPlane
git add agentplane/cli/inventory.py agentplane/cli/audit.py agentplane/cli/apps.py agentplane/cli/service.py agentplane/cli/website.py agentplane/cli/projection.py agentplane/domain/service/lifecycle.py agentplane/domain/website/lifecycle.py agentplane/domain/projection/runtime_env.py agentplane/scripts/onepanel/verification.py tests/test_wsl_audit.py tests/test_host_cli.py tests/test_app_cli.py tests/test_service_cli.py tests/test_website_cli.py tests/test_projection_runtime_env_cli.py
git commit -m "feat: route domain surfaces through backend execution"
```

- [ ] **Step 7: 按固定模板输出 Phase 4 收口总结**

### Task 4 next session starter

```text
先加载 `pua` skill。

使用 `executing-plans`，执行 `D:/Projects/AgentPlane/docs/superpowers/plans/2026-04-11-agentplane-agent-first-control-plane-template-implementation.md` 的 Task 4。
要求：
1. 优先主线程直接实现，不做低效 review。
2. 只做本阶段直接相关的最小必要验证。
3. 本阶段结束前必须先提交变更，再按固定模板输出收口总结。
4. 阶段完成后停止，不进入 Task 5。
```

## Task 5: Bootstrap Productization

**Files:**
- Create: `agentplane/cli/bootstrap.py`
- Create: `agentplane/runtime/bootstrap.py`
- Create: `templates/secrets/local/control-plane/README.md`
- Create: `templates/secrets/targets/_template/README.md`
- Create: `tests/test_bootstrap_cli.py`
- Modify: `agentplane/cli/app.py`
- Modify: `agentplane/cli/secrets.py`
- Modify: `README.md`
- Modify: `docs/runbooks/bootstrap-secrets.md`
- Modify: `tests/test_secrets_host_layout.py`
- Modify: `tests/test_app_onboarding_standard.py`

- [ ] **Step 1: 先写失败测试，锁定 fork 用户的最小启动路径**

```python
def test_bootstrap_init_secrets_creates_only_expected_local_files(tmp_path: Path) -> None:
    result = run_cli("bootstrap", "init-secrets", "--repo-root", str(tmp_path))
    assert (tmp_path / "secrets" / "local" / "control-plane").exists()
    assert result.exit_code == 0

def test_bootstrap_verify_secrets_does_not_print_secret_values() -> None:
    result = run_cli("bootstrap", "verify-secrets", "--repo-root", "D:/Projects/AgentPlane")
    assert "SECRET_VALUE" not in result.output
```

- [ ] **Step 2: 运行 bootstrap / secrets 相关测试，确认当前入口仍偏作者现场**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_secrets_host_layout.py tests/test_app_onboarding_standard.py -q
```

Expected:

- 当前 README / runbook / CLI 还没有收敛成“先 inspect，再 init-secrets，再 verify-secrets”的模板路径。

- [ ] **Step 3: 增加 bootstrap formal surface**

至少新增四个动作：

- `bootstrap inspect-local`
- `bootstrap init-secrets`
- `bootstrap verify-secrets`
- `bootstrap doctor`

```python
@app.command("inspect-local")
def inspect_local(repo_root: Path) -> None: ...

@app.command("init-secrets")
def init_secrets(repo_root: Path) -> None: ...
```

- [ ] **Step 4: 把 README 和 runbook 改成“人类只填 secrets，Agent 接管其余步骤”**

要求：

- `README.md` 的上手路径只保留 fork/clone、bootstrap、填写 secrets、让 Agent 接管
- `docs/runbooks/bootstrap-secrets.md` 只保留模板仓库启动所需信息，不再夹带作者现场习惯
- `agentplane/cli/secrets.py` 只承担 secrets 读写与校验，不承担 truth 定义

- [ ] **Step 5: 运行最小验证**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_bootstrap_cli.py tests/test_secrets_host_layout.py tests/test_app_onboarding_standard.py -q
uv run python -m agentplane.cli bootstrap inspect-local --repo-root D:/Projects/AgentPlane
uv run python -m agentplane.cli bootstrap verify-secrets --repo-root D:/Projects/AgentPlane
```

Expected:

- fork 用户的 bootstrap 主路径可通过 formal CLI 表达
- secret 检查不会打印敏感值

- [ ] **Step 6: 提交本阶段变更**

```bash
cd D:/Projects/AgentPlane
git add agentplane/cli/app.py agentplane/cli/bootstrap.py agentplane/cli/secrets.py agentplane/runtime/bootstrap.py templates/secrets/local/control-plane/README.md templates/secrets/targets/_template/README.md README.md docs/runbooks/bootstrap-secrets.md tests/test_bootstrap_cli.py tests/test_secrets_host_layout.py tests/test_app_onboarding_standard.py
git commit -m "feat: add bootstrap flow for template users"
```

- [ ] **Step 7: 按固定模板输出 Phase 5 收口总结**

### Task 5 next session starter

```text
先加载 `pua` skill。

使用 `executing-plans`，执行 `D:/Projects/AgentPlane/docs/superpowers/plans/2026-04-11-agentplane-agent-first-control-plane-template-implementation.md` 的 Task 5。
要求：
1. 优先主线程直接实现，不做低效 review。
2. 只做本阶段直接相关的最小必要验证。
3. 本阶段结束前必须先提交变更，再按固定模板输出收口总结。
4. 阶段完成后停止，不进入 Task 6。
```

## Task 6: Observation Isolation

**Files:**
- Create: `agentplane/runtime/observation.py`
- Create: `tests/test_observation_contracts.py`
- Modify: `agentplane/domain/app/object_handlers.py`
- Modify: `agentplane/domain/app/resource_handlers.py`
- Modify: `agentplane/domain/service/handlers.py`
- Modify: `agentplane/scripts/onepanel/ledger.py`
- Modify: `agentplane/cli/projection.py`
- Modify: `tests/test_inventory_generation.py`
- Modify: `tests/test_app_resource_object_cli.py`
- Modify: `tests/test_service_lifecycle.py`

- [ ] **Step 1: 先写失败测试，锁定 observation 与 tracked output 的边界**

```python
def test_verification_payload_keeps_resolved_path_out_of_ledger_fields() -> None:
    payload = build_verification_payload(
        canonical_ref="apps/sub2api/contracts/prod0-main",
        resolved_path="D:/Projects/AgentPlane/.cache/runtime/contract.yaml",
    )
    assert payload["ledger_fields"]["canonical_ref"] == "apps/sub2api/contracts/prod0-main"
    assert "resolved_path" not in payload["ledger_fields"]
```

- [ ] **Step 2: 运行 inventory / object / service 相关测试，复现当前 tracked output 污染**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_inventory_generation.py tests/test_app_resource_object_cli.py tests/test_service_lifecycle.py -q
```

Expected:

- 当前至少有一部分路径、观察值或运行证据与 tracked projection 混杂。

- [ ] **Step 3: 引入 observation contract，并把 verification 输出单独归档**

```python
@dataclass(frozen=True)
class ObservationRecord:
    canonical_ref: str
    evidence: Mapping[str, Any]
    resolved_path: str | None
    observed_at: str
```

要求：

- `ledger` 只保留 canonical 字段和稳定摘要
- `verification` 才保留 `resolved_path`、runtime path、现场探测值
- `projection` surface 只刷新 projection，不顺手改 truth

- [ ] **Step 4: 修改 object / resource / service handlers 的输出模型**

重点：

- `agentplane/domain/app/object_handlers.py`
- `agentplane/domain/app/resource_handlers.py`
- `agentplane/domain/service/handlers.py`

都要统一输出：

- `canonical_ref`
- `resolved_path` 仅在 evidence/verification 区段出现
- `ledger_fields` 与 `verification_fields` 分离

- [ ] **Step 5: 运行最小验证**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_observation_contracts.py tests/test_inventory_generation.py tests/test_app_resource_object_cli.py tests/test_service_lifecycle.py -q
uv run python -m agentplane.cli projection verification --repo-root D:/Projects/AgentPlane --help
```

Expected:

- observation contract tests 通过
- tracked projection 不再携带宿主污染字段

- [ ] **Step 6: 提交本阶段变更**

```bash
cd D:/Projects/AgentPlane
git add agentplane/runtime/observation.py agentplane/domain/app/object_handlers.py agentplane/domain/app/resource_handlers.py agentplane/domain/service/handlers.py agentplane/scripts/onepanel/ledger.py agentplane/cli/projection.py tests/test_observation_contracts.py tests/test_inventory_generation.py tests/test_app_resource_object_cli.py tests/test_service_lifecycle.py
git commit -m "feat: isolate observation from tracked outputs"
```

- [ ] **Step 7: 按固定模板输出 Phase 6 收口总结**

### Task 6 next session starter

```text
先加载 `pua` skill。

使用 `executing-plans`，执行 `D:/Projects/AgentPlane/docs/superpowers/plans/2026-04-11-agentplane-agent-first-control-plane-template-implementation.md` 的 Task 6。
要求：
1. 优先主线程直接实现，不做低效 review。
2. 只做本阶段直接相关的最小必要验证。
3. 本阶段结束前必须先提交变更，再按固定模板输出收口总结。
4. 阶段完成后停止，不进入 Task 7。
```

## Task 7: Open-Source Template Closure

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/architecture/README.md`
- Modify: `docs/reference/app-repository-standard.md`
- Modify: `docs/runbooks/control-plane-domain-onboarding.md`
- Modify: `docs/runbooks/control-plane-agent-execution-flow.md`
- Modify: `.codex/skills/host-ops/SKILL.md`
- Modify: `.codex/skills/app-delivery-ops/SKILL.md`
- Modify: `.codex/skills/app-resource-ops/SKILL.md`
- Modify: `.codex/skills/inventory-ledger-ops/SKILL.md`
- Modify: `.codex/skills/projection-ops/SKILL.md`
- Modify: `tests/test_docs_no_legacy_terms.py`
- Modify: `tests/test_wsl_first_docs.py`
- Modify: `tests/test_onepanel_plugin_and_skills.py`

- [ ] **Step 1: 先写失败测试，锁定模板仓库口径**

```python
def test_readme_describes_template_bootstrap_path() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    assert "fork / clone" in text
    assert "bootstrap inspect-local" in text

def test_docs_do_not_reintroduce_root_work_default() -> None:
    assert "/root/work/AgentPlane" not in collect_active_docs()
```

- [ ] **Step 2: 运行文档和 skill 门禁测试，记录当前回流点**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py tests/test_onepanel_plugin_and_skills.py -q
```

Expected:

- 当前仍会暴露旧 README、旧 AGENTS、旧 skill 口径。

- [ ] **Step 3: 重写 active docs 与 repo-owned skills**

要求：

- `README.md` 不再把作者现场目录当成默认入口
- `AGENTS.md` 的仓库级规则以模板仓库口径描述
- repo-owned skills 只调用 formal CLI，不写第二控制面
- `docs/reference/app-repository-standard.md` 要明确 app repo 和 control plane repo 的边界

- [ ] **Step 4: 收口开源模板对外叙述**

至少明确：

- 仓库是 Agent-first control plane template repository
- Git tracked truth + local secrets 是正式真源模型
- Windows / Linux / macOS 只在 resolver/backend 层分叉
- fork 用户的人类输入面只剩 secrets 和少量 identity

- [ ] **Step 5: 运行最小验证**

Run:

```bash
cd D:/Projects/AgentPlane
uv run python -m pytest tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py tests/test_onepanel_plugin_and_skills.py -q
uv run python -m agentplane.cli --help
```

Expected:

- 文档和 skill 门禁通过
- 正式 CLI 入口不变

- [ ] **Step 6: 提交本阶段变更**

```bash
cd D:/Projects/AgentPlane
git add README.md AGENTS.md docs/architecture/README.md docs/reference/app-repository-standard.md docs/runbooks/control-plane-domain-onboarding.md docs/runbooks/control-plane-agent-execution-flow.md .codex/skills/host-ops/SKILL.md .codex/skills/app-delivery-ops/SKILL.md .codex/skills/app-resource-ops/SKILL.md .codex/skills/inventory-ledger-ops/SKILL.md .codex/skills/projection-ops/SKILL.md tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py tests/test_onepanel_plugin_and_skills.py
git commit -m "docs: close template-facing control plane guidance"
```

- [ ] **Step 7: 按固定模板输出 Phase 7 收口总结**

### Task 7 next session starter

```text
先加载 `pua` skill。

使用 `executing-plans`，执行 `D:/Projects/AgentPlane/docs/superpowers/plans/2026-04-11-agentplane-agent-first-control-plane-template-implementation.md` 的 Task 7。
要求：
1. 优先主线程直接实现，不做低效 review。
2. 只做本阶段直接相关的最小必要验证。
3. 本阶段结束前必须先提交变更，再按固定模板输出收口总结。
4. 阶段完成后停止；若本阶段完成，则整个计划进入收尾复盘，不再继续新增兼容任务。
```

## Self-Review Notes

- `Task 1` 对应 spec 中的 canonical truth、path policy、truth/ledger/verification 边界。
- `Task 2` 对应 spec 中的 HostProfile、resolver、canonical ref 与 resolved_path 分离。
- `Task 3` 对应 spec 中的 `ExecutionPlan` 和四类 backend runner。
- `Task 4` 对应 spec 中的 host / app / service / website / projection backend-aware 改造。
- `Task 5` 对应 spec 中的 bootstrap productization 和“人类只填 secrets”。
- `Task 6` 对应 spec 中的 observation isolation。
- `Task 7` 对应 spec 中的 README / AGENTS / skills / active docs 模板化收口。
- 本计划没有保留空白占位项；如后续需求边界变化，应先修 spec 再修计划。
