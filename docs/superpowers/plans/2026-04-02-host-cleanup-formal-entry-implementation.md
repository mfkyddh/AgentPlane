# Host Cleanup Formal Entry Implementation Plan

**Goal:** 删除顶层 `cleanup`，把主机级清理流程并入 `host cleanup`，继续压缩顶层 CLI 控制面。

## Task 1: 冻结新合同

- [x] 把 `tests/test_cli_entrypoints.py` 改成顶层 help 不再暴露 `cleanup`
- [x] 把 `tests/test_host_cli.py` 改成要求 `host cleanup plan/apply`
- [x] 把 `tests/test_docs_no_legacy_terms.py` 改成要求 active 文档与 skill 使用 `host cleanup`
- [x] 跑定向测试确认失败点集中在 parser / 文档未同步

## Task 2: 落 CLI 实现

- [x] 在 `ops/cli/host.py` 新增 `cleanup` 子命令族
- [x] 让 `host cleanup` 统一返回 `{command, action, target, payload}`
- [x] 从 `ops/cli/app.py` 删除顶层 `cleanup` parser 与 dispatch
- [x] 在 `ops/cli/cleanup.py` 显式声明实际支持的 target 集合

## Task 3: 同步 active 合同

- [x] 更新 `README.md`
- [x] 更新 `AGENTS.md`
- [x] 更新 `docs/architecture/control-plane.md`
- [x] 更新 `docs/runbooks/wsl-host-governance.md`
- [x] 更新 `.codex/skills/host-ops/SKILL.md`

## Task 4: 验证

- [x] 运行 `tests/test_cli_entrypoints.py`
- [x] 运行 `tests/test_host_cli.py`
- [x] 运行 `tests/test_cleanup.py`
- [x] 运行 `tests/test_docs_no_legacy_terms.py`
- [x] 手工检查 `ops.cli --help` 与 `ops.cli host cleanup --help`
