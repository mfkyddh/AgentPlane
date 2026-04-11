# CLI-First Repo Refactor And Host Phase Handoff

## 1. 目标完成情况

### 原定目标是否完成

结论：原工作区的主目标已经完成。

已完成的范围分两层：

1. `CLI-first repository refactor` 原计划的 `Phase 0-7` 已完成。
2. 下一阶段的第一步 `host` 对象域第一版也已完成。

### 已完成的结果

- 正式控制面仍收口在 `uv run python -m ops.cli ...`
- `README / architecture / runbooks / history / archive` 的导航边界已收紧
- `.codex/skills/` 已成为正文真源，`.agents / plugins` 只保留派生层
- `templates / inventory / ledger` 的非应用层边界已收紧为单一真源 + projection
- 第一版 `host` 对象入口已经落地：
  - `uv run python -m ops.cli host inventory ...`
  - `uv run python -m ops.cli host audit ...`
  - `uv run python -m ops.cli host remote bash ...`
  - `uv run python -m ops.cli host secrets-layout ...`

### 明确保留未做的范围

这些不是遗漏，而是原计划明确延后：

- 不进入应用层运行面
- 不处理 `newapi / sub2api / sub2apipay / chatgpt-register-v2*` 的应用对象化
- 不把 `network / onepanel panel / onepanel firewall` 并入第一版 `host`

## 2. 问题回顾与处理

### (a) 执行过程中碰到的问题

1. `Phase 7` 计划里要求的 `docs/history/index.md` 与 `docs/archive/README.md` 当时并不存在，导致“历史/归档索引已收口”的说法还停留在文案层。
2. `host` 第一版设计落地后，文档、skill、CLI、仓库规则之间出现了一处口径不一致：
   - 新文档默认入口已改成 `ops.cli host ...`
   - 但 `AGENTS.md` 和对应测试仍写 `ops.cli remote bash ...` 是正式远端入口。
3. 宿主机能力原本分散在 `inventory / audit / remote / secrets / network / onepanel`，如果不先定义第一版边界，很容易在实现时把范围扩散。

### (b) 这些问题是否已解决或已记录

结论：都已处理，并且关键问题都已经通过测试或文档固化，后续不容易重复发生。

- 问题 1 已解决：
  - 新增了 `docs/history/index.md`
  - 新增了 `docs/archive/README.md`
  - 并补了文档合同测试，防止以后再次只写说明、不建真实索引

- 问题 2 已解决：
  - `AGENTS.md` 已同步到 `host remote bash` 正式口径
  - `tests/test_docs_no_legacy_terms.py` 已同步收紧

- 问题 3 已解决并已记录：
  - 通过 `docs/superpowers/specs/2026-04-01-host-object-cli-first-design.md`
  - 以及 `docs/superpowers/plans/2026-04-01-host-object-cli-first-implementation.md`
  - 明确第一版 `host` 只覆盖 `inventory / audit / remote bash / secrets-layout`
  - `network / panel / firewall` 明确记录为下一阶段桥接对象

## 3. 后续规划

### (a) 下一步计划

下一步建议继续沿着 `host` 对象域做第二轮扩展，但仍不要进入应用层。

优先顺序建议：

1. 评估 `network` 是否应该作为 `host network ...` 桥接子域进入 `host`
2. 评估 `onepanel firewall` 是否应进入 `host firewall ...`
3. 评估 `onepanel panel` 是否应进入 `host panel ...`
4. 只有宿主机对象面继续稳定后，再考虑 `service / website / tenant`

推荐先从 `network` 开始，因为它和宿主机基线、bridge 漂移修复、inventory 声明的一致性最接近，且比 `panel/firewall` 更少绑定 1Panel 对象语义。

### (b) 目前还未完成的工作

当前还未完成的不是“本轮漏做”，而是“下一阶段尚未开始”的工作：

- `host` 第二版尚未开始：
  - `network`
  - `panel`
  - `firewall`

- 更宽对象域尚未开始：
  - `service`
  - `website`
  - `tenant`
  - `app`
  - `projection` 的进一步对象化

- 历史兼容入口虽然保留并可用，但还没有进入真正的“逐步降级/收缩”阶段，目前仍处于稳定兼容状态

## 4. 当前基线

- 当前分支：`codex/cli-first-repo-refactor-plan`
- 当前提交基线应包含：
  - `8b32ffd` `refactor: finalize cli-first repository convergence`
  - `ceb3686` `docs: add host object cli-first design`
  - `d5fc5a5` `docs: add host cli implementation plan`
  - `a12247d` `feat: add host cli object entrypoint`

- 最近一次全量最小回归：

```bash
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_host_cli.py tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py tests/test_secrets_host_layout.py tests/test_inventory_generation.py tests/test_onepanel_plugin_and_skills.py tests/test_onepanel_env_targets.py -q
```

结果：

- `46 passed, 276 subtests passed`

## 5. 新会话建议起手式

新会话建议直接说明：

- 继续 `/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`
- 当前分支是 `codex/cli-first-repo-refactor-plan`
- 当前 `HEAD` 以本 handoff 对应提交为准
- 上一阶段已经完成 `repo refactor phase 0-7` 和 `host v1`
- 下一步从 `host v2` 开始，优先评估 `network` 是否进入 `host`
