---
status: active
owner: AgentPlane maintainers
created: 2026-06-22
sprint: P0 — CLI coverage sprint
milestone: M1 — CLI verb inventory
audience: both
---

# CLI 动词矩阵清单

> M1 产出。用于驱动 P0（CLI 命令测试覆盖率 38% → 90%+）的冲刺范围。
> 数据基线：coverage_output.txt（2026-06-22 抓取，总覆盖 73.92%，2604 tests passed）。

---

## 1. 总览

- **CLI 入口**：`agentplane/cli/app.py:33`（`build_parser()`）
- **一级域（domain）**：7 个 — `infra` / `service` / `ingress` / `app` / `project` / `test` / `web`
- **二级表面（surface）**：17 个
- **动词（verb）**：68 个（不含 flag 分支）
- **唯一动词路径（含 surface + verb）**：约 **82** 条

### CLI 模块覆盖率（agentplane/cli/，按覆盖率升序）

| 模块 | Stmts | Cover | Miss | 优先级 |
|------|------:|------:|-----:|:------:|
| web.py | 26 | **31%** | 16 | P0 |
| infra_handlers.py | 98 | **38%** | 56 | P0 |
| service.py | 84 | **59%** | 26 | P1 |
| app.py（入口分发） | 110 | **58%** | 40 | P1 |
| project_checks.py | 94 | **58%** | 40 | P1 |
| project_commands.py | 116 | **70%** | 35 | P1 |
| project_projection.py | 40 | **78%** | 7 | P2 |
| ingress.py | 84 | **89%** | 6 | P2 |
| test_runner.py | 63 | **96%** | 1 | — |
| apps.py（dispatch） | 226 | **93%** | 11 | — |
| infra_parsers.py | 121 | **99%** | 1 | — |
| project.py | 133 | **99%** | 1 | — |
| infra_onepanel.py | 99 | **100%** | 0 | — |
| 其他 thin dispatch 模块 | — | **100%** | 0 | — |

### 间接关联的 domain 层薄弱模块（runtime/delivery_handlers 拆分产物）

| 模块 | Stmts | Cover | 关联动词 |
|------|------:|------:|----------|
| domain/app/runtime_build.py | 128 | **10%** | app delivery build-artifact |
| domain/app/runtime_rollback.py | 33 | **19%** | app delivery rollback |
| domain/app/delivery_handlers_candidate.py | 61 | **27%** | app delivery validate-contract/render-runtime |
| domain/app/delivery_handlers_deploy.py | 97 | **8%** | app delivery deploy/verify |
| domain/app/delivery_handlers_planning.py | 67 | **33%** | app delivery plan（未实现） |
| domain/app/runtime.py | 186 | **39%** | app delivery 全系列 |
| domain/app/delivery_handlers_handlers.py | 42 | **45%** | app delivery 薄入口 |
| domain/app/delivery_handlers_shared.py | 66 | **49%** | 所有 delivery 路径 |
| domain/app/delivery_handlers_verify_rollback.py | 27 | **52%** | app delivery verify/rollback |
| domain/infra/cleanup.py | 97 | **11%** | infra cleanup plan/apply |
| domain/infra/live_gate.py | 94 | **27%** | infra live-gate run/plan/apply |
| domain/infra/inventory.py | 130 | **37%** | infra inventory |
| domain/infra/audit_wsl.py | 100 | **34%** | infra audit（wsl 路径） |
| domain/project/status_html.py | 60 | **15%** | project status --format html |

---

## 2. 动词矩阵

> 测试状态图例：
> - ✅ 已测：CLI 路径有 unit 或 integration 测试（handler 级也算）
> - 🟡 部分：handler 有测试，但 CLI 分发/错误路径未覆盖
> - ❌ 未测：CLI + handler 均无有效覆盖
> - 测试文件：列出主要测试文件

### 2.1 `infra` 域

| Surface | Verb | 测试状态 | 测试文件 | 备注 |
|---------|------|:--------:|----------|------|
| inventory | (default) | ✅ | tests/inventory/test_inventory.py | 薄入口 |
| audit | (default) | 🟡 | tests/onepanel/test_onepanel_audit_*.py | prod0 路径已测，wsl 路径缺失 |
| live-gate | run / plan / apply | 🟡 | tests/infra/test_infra_live_gate.py（若有） | 覆盖率 27%，需补 |
| cleanup | plan / apply | ❌ | — | 覆盖率 11%，0 测试 |
| automation | search / get / verify / plan / apply | ✅ | tests/infra/test_infra_automation_*.py | 覆盖良好 |
| health | (default) | 🟡 | tests/infra/ | 多分支未覆盖 |
| network | audit / ensure / firewall-audit | 🟡 | tests/infra/test_infra_host_network.py | ensure 路径未覆盖 |
| network | firewall plan/apply | ❌ | — | 新增 verb，无测试 |
| remote | preflight / bash | ✅ | tests/infra/test_infra_remote.py | bash remainder 分发已测 |
| secrets | init-layout / sync-layout | 🟡 | tests/secret_management/test_secrets.py | sync-layout 路径薄 |
| bootstrap | clone / verify / apply | 🟡 | tests/project/test_repo_bootstrap.py | 部分覆盖 |
| onepanel | （所有 verb） | ✅ | tests/cli/test_infra_onepanel.py (346 行) | 覆盖良好 |

### 2.2 `service` 域

| Verb | 测试状态 | 测试文件 | 备注 |
|------|:--------:|----------|------|
| search | ✅ | tests/support/service_cli.py（调用方） | — |
| get | ✅ | tests/service/ | — |
| verify | 🟡 | tests/service/ | 失败分支未覆盖 |
| plan / apply | 🟡 | tests/service/ | execute 分支未覆盖 |
| refresh-ledger | 🟡 | tests/service/ | — |
| materialize | ❌ | — | 新增 verb，无测试 |
| public-endpoint plan/apply/verify | ❌ | — | 覆盖率依赖 domain/service/public_endpoint.py |

### 2.3 `ingress` 域

| Verb | 测试状态 | 测试文件 | 备注 |
|------|:--------:|----------|------|
| search | ✅ | tests/ingress/ | — |
| get / verify | ✅ | tests/ingress/test_ingress_website.py | — |
| plan / apply | ✅ | tests/ingress/test_ingress_publish.py | — |
| refresh-ledger | 🟡 | tests/ingress/ | — |
| publish plan / apply / verify | ✅ | tests/ingress/test_ingress_publish.py | — |

### 2.4 `app` 域

| Surface | Verb | 测试状态 | 测试文件 | 备注 |
|---------|------|:--------:|----------|------|
| object | search / get / verify / refresh-ledger / discover | ✅ | tests/cli/test_app_cli.py, tests/app/test_app_object.py | 覆盖良好 |
| resource | search / get / verify / refresh-ledger | ✅ | tests/app/test_app_resource_cli.py | 覆盖良好 |
| delivery | validate-contract | ✅ | tests/app/test_app_lifecycle.py | — |
| delivery | render-runtime | 🟡 | — | 覆盖率依赖 runtime_build |
| delivery | build-artifact | ❌ | — | runtime_build 10% |
| delivery | package-runtime | ❌ | — | — |
| delivery | ship-image | ❌ | — | — |
| delivery | deploy | ❌ | — | runtime_deploy 42%，delivery_handlers_deploy 8% |
| delivery | verify | ❌ | — | delivery_handlers_verify_rollback 52% |
| delivery | rollback | ❌ | — | runtime_rollback 19% |
| delivery | inventory-refresh | 🟡 | — | — |
| delivery | doc-sync | 🟡 | — | — |
| delivery | onboard / offboard | 🟡 | tests/app/test_app_onboarding.py | 覆盖良好但需核对写路径 |

### 2.5 `project` 域

| Surface | Verb | 测试状态 | 测试文件 | 备注 |
|---------|------|:--------:|----------|------|
| — | health-check | ✅ | tests/project/test_repo_health.py | — |
| — | status | 🟡 | tests/project/ | status_html 15%（--format html 未测） |
| — | docs-sanity | ✅ | tests/project/ | — |
| — | secret-scan / privacy-scan | ✅ | tests/project/ | — |
| — | doc-layer | 🟡 | tests/project/ | — |
| — | release-check | ✅ | tests/project/ | — |
| — | bump-version | 🟡 | tests/project/ | — |
| provider | onepanel route-fingerprint | ❌ | — | 无 CLI 测试 |
| topology | (default) | ❌ | — | — |
| skills | check / list / export / validate-commands | ✅ | tests/project/test_skills.py | — |
| projection | runtime-env plan/apply/verify | 🟡 | tests/projection/test_projection.py | — |
| projection | verification run | ❌ | — | — |
| projection | fixture plan/apply/verify | ❌ | — | — |
| projection | ledger refresh | ❌ | — | — |

### 2.6 `test` 域

| Verb | 测试状态 | 测试文件 | 备注 |
|------|:--------:|----------|------|
| test fast / full / e2e / unit / integration | ✅ | tests/cli/test_test_runner.py (366 行) | 覆盖良好 |

### 2.7 `web` 域

| Verb | 测试状态 | 测试文件 | 备注 |
|------|:--------:|----------|------|
| web (启动) | ❌ | tests/web/test_web.py（FastAPI app 有测试，但 CLI 路径无测试） | CLI 层 31% 覆盖 |

---

## 3. 覆盖率冲刺优先级（M2/M3）

### P0 冲刺包（预估 +10% 覆盖率，冲到 ~84%）

1. **runtime_build / runtime_deploy / runtime_rollback 全套测试**（~300 行新增）
   - 关联：`app delivery build-artifact / package-runtime / ship-image / deploy / verify / rollback`
   - 目标：每个模块 ≥ 70%
   - 预计覆盖率提升：+4%

2. **delivery_handlers_deploy + delivery_handlers_candidate + delivery_handlers_planning**（~250 行）
   - 关联：`app delivery` 所有动词的 CLI 分发路径
   - 目标：≥ 75%
   - 预计覆盖率提升：+2%

3. **infra cleanup + live-gate + firewall**（~200 行）
   - 关联：`infra cleanup plan/apply`、`infra live-gate run`、`infra network firewall plan/apply`
   - 目标：≥ 70%
   - 预计覆盖率提升：+2%

4. **web CLI 入口测试**（~80 行）
   - 使用 `TestClient` 或 mock uvicorn.run，覆盖 repo-root 校验、token 传递
   - 目标：≥ 90%
   - 预计覆盖率提升：+0.5%

5. **infra_handlers.py 错误分支**（~120 行）
   - 关联：所有 `infra` verb 的 CLI 分发 + ValueError 路径
   - 目标：≥ 85%
   - 预计覆盖率提升：+1%

### P1 冲刺包（预估 +5%，冲到 ~89%）

6. service plan/apply/verify/materialize 完整路径
7. app delivery render-runtime / inventory-refresh / doc-sync
8. project status --format html（status_html.py 15% → ≥ 80%）
9. project provider onepanel route-fingerprint
10. project topology / projection verification run / fixture / ledger refresh
11. app.py 入口分发的 infra/service/ingress 错误路径
12. service public-endpoint 三 verb 覆盖

### P2 收尾（冲到 90%+）

13. 剩余边界分支、flag 互斥校验、ValueError 异常路径

---

## 4. 风险与依赖

| 风险 | 影响 | 缓解 |
|------|------|------|
| runtime_build.py 依赖真实 docker build | 测试无法隔离 | 用 ProviderProtocol stub 注入 |
| runtime_deploy.py 依赖 SSH 到 1Panel | 测试无法离线 | 走 fake provider，不直接 mock subprocess |
| web.py 启动 uvicorn | 测试会阻塞 | 用 TestClient + 提前 return mock |
| infra cleanup/live-gate 依赖远端状态 | 测试需要 fixture | 复用 tests/support/cli.py 的 run_agentplane_cli |
| delivery_handlers_deploy.py 仅 8% 覆盖 | 部署路径从未真实验证 | 先补 unit，再补 integration with fake provider |

### 前置条件

- **repo structure 测试失败**：`coverage_output.txt` 被 `tests/project/test_repo_structure_basics.py` 标记为非法顶层条目，必须先加入 `.gitignore` 或删除文件。
- **PROGRESS.md 未提交**：当前 git status 显示 PROGRESS.md 有未提交修改，需先处理。

---

## 5. 验收标准（M1 完成定义）

- [x] 7 域 × surface × verb 完整矩阵
- [x] 每条动词标注测试状态（✅ / 🟡 / ❌）
- [x] 标注主要测试文件
- [x] 按 P0/P1/P2 排序冲刺优先级
- [x] 给出覆盖率提升预估
- [ ] （M2 验收）P0 冲刺包落地，覆盖率 ≥ 84%
- [ ] （M3 验收）P1 冲刺包落地，覆盖率 ≥ 89%
- [ ] （M4 验收）pyproject 门禁提升到 85%，roadmap 声明 Beta 退出

---

## 6. 下一步行动

1. 用户对齐本矩阵（本次会话）
2. 修复 `coverage_output.txt` 被跟踪问题（建议加 `.gitignore`）
3. 登记 B127（M1 CLI 动词矩阵清单）到 PROGRESS.md
4. 启动 M2（P0 冲刺包），建议拆为 B128-B132 五个分支任务
