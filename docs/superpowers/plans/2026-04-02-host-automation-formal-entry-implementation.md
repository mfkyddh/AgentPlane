# Host Automation Formal Entry Implementation Plan

**Goal:** 删除顶层 `automation`，把 WSL 本机 automation task 收口到 `host automation`，同时保持 1Panel 面板计划任务可见、可调度、可核验。

## Task 1: 冻结新合同

- [ ] 把 `tests/test_cli_entrypoints.py` 改成顶层 help 不再暴露 `automation`
- [ ] 把 `tests/test_cli_entrypoints.py` 和 `tests/test_host_cli.py` 改成要求 `host automation search/get/verify/plan/apply`
- [ ] 新增 `tests/test_host_automation.py`，冻结 task truth、cronjob reconcile、run/trigger 的最小行为
- [ ] 跑定向测试确认失败点集中在 parser / dispatch / 文档未同步

## Task 2: 落 CLI 与 task surface

- [ ] 新增 `ops/cli/host_automation.py`
- [ ] 在 `ops/cli/host.py` 挂入 `automation` 子命令族
- [ ] 在 `ops/cli/app.py` 删除顶层 `automation` parser 与 dispatch
- [ ] 把 `inventory/servers/wsl/inventory.json` 的 automation command 切到 `host automation apply ... --operation run --execute`

## Task 3: 同步 active 合同

- [ ] 更新 `README.md`
- [ ] 更新 `AGENTS.md`
- [ ] 更新 `docs/architecture/control-plane.md`
- [ ] 更新 `docs/runbooks/wsl-host-governance.md`
- [ ] 更新 `docs/runbooks/wsl-secrets-backup.md`
- [ ] 更新 `docs/runbooks/wsl-zzz-skills-sync.md`
- [ ] 更新 `.codex/skills/host-ops/SKILL.md`

## Task 4: 验证

- [ ] 运行 `tests/test_cli_entrypoints.py`
- [ ] 运行 `tests/test_host_cli.py`
- [ ] 运行 `tests/test_host_automation.py`
- [ ] 运行 `tests/test_docs_no_legacy_terms.py`
- [ ] 手工检查 `ops.cli --help`、`ops.cli host --help`、`ops.cli host automation --help`
