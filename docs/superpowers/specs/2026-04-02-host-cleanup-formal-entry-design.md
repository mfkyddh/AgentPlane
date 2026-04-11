# Host Cleanup Formal Entry Design

**Date:** 2026-04-02

## Goal

把顶层 `cleanup` 硬删除，并把主机级清理流程收口到唯一正式入口 `uv run python -m ops.cli host cleanup ...`。

## Why This Next

当前单正式入口收口后，顶层 CLI 只剩 `cleanup / automation / onepanel` 三块非对象化域。

其中：

- `cleanup` 已天然按主机目标 `wsl / prod0-main` 建模
- 底层实现独立、写集小
- 与现有 `host inventory / audit / network / remote / secrets` 同属主机治理面

因此它是下一轮最小且收益最高的继续收口范围。

## Scope

本轮只做：

1. 删除顶层 `cleanup` parser 与 dispatch。
2. 新增 `host cleanup plan <target>`。
3. 新增 `host cleanup apply <target>`。
4. 把 active 文档、skills、帮助输出与测试切到 `host cleanup`。
5. 顺手修正 `docs/architecture/control-plane.md` 中与当前 host 合同直接冲突的残留表述。

本轮不做：

1. 不改 `cleanup` 底层白名单逻辑。
2. 不把 `automation` 并入 `host`。
3. 不推进 `onepanel` 的进一步对象化拆分。
4. 不新增 cleanup 的新 target，只沿用当前实际支持的 `wsl / prod0-main`。

## Target State

完成后：

```bash
uv run python -m ops.cli host cleanup plan wsl --repo-root /root/work/OP_Linux
uv run python -m ops.cli host cleanup apply wsl --repo-root /root/work/OP_Linux
```

以下命令退场：

```bash
uv run python -m ops.cli cleanup plan --env wsl
uv run python -m ops.cli cleanup apply --env wsl
```

## Output Contract

`host cleanup` 统一采用现有 `host` envelope：

```json
{
  "command": "host",
  "action": "cleanup.plan",
  "target": "wsl",
  "payload": {}
}
```

`payload` 内继续复用现有 `cleanup` 底层结果，但对外不再暴露顶层 `cleanup plan` / `cleanup apply` 命令身份。

## Files

- Modify: `ops/cli/app.py`
- Modify: `ops/cli/host.py`
- Modify: `ops/cli/cleanup.py`
- Modify: `tests/test_cli_entrypoints.py`
- Modify: `tests/test_host_cli.py`
- Modify: `tests/test_docs_no_legacy_terms.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/architecture/control-plane.md`
- Modify: `docs/runbooks/wsl-host-governance.md`
- Modify: `.codex/skills/host-ops/SKILL.md`

## Verification

最小验证：

```bash
uv run python -m pytest \
  tests/test_cli_entrypoints.py \
  tests/test_host_cli.py \
  tests/test_cleanup.py \
  tests/test_docs_no_legacy_terms.py -q

uv run python -m ops.cli --help
uv run python -m ops.cli host --help
uv run python -m ops.cli host cleanup --help
```
