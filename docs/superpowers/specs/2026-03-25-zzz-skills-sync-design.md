# zzz-skills 同步与 WSL 计划任务纳管设计

## 1. 目标

在 `/root/work` 下维护一个正式 Git 仓库 `/root/work/zzz-skills`，将 Windows 全局 Codex 技能目录 `C:\Users\Administrator\.codex\skills\` 中所有名称以 `zzz-` 开头的技能，定期镜像同步到该仓库，并在有变化时自动推送到 `origin/main`。

这套同步能力必须纳入 `OP_Linux` 的正式控制面，而不是把核心逻辑散落在 1Panel 页面配置中。WSL 本机 `1Panel` 只负责按周期调度，业务逻辑、日志口径、文档、登记和运维规范统一收口到 `OP_Linux`。

## 2. 范围

本设计只覆盖以下范围：

- 同步源：`/mnt/c/Users/Administrator/.codex/skills/zzz-*`
- 同步目标：`/root/work/zzz-skills`
- 调度位置：WSL 本机 `1Panel` 计划任务
- 控制面仓库：`/root/work/OP_Linux`
- 执行周期：每 2 小时一次

本设计不覆盖以下范围：

- `C:\Users\Administrator\.codex\superpowers\skills\`
- `C:\Users\Administrator\.agents\...` 中的技能
- 远端主机 `prod0-main` 上的 1Panel 计划任务
- 自动处理 Git 冲突、自动 rebase 或自动 merge

## 3. 现状与问题

当前环境中：

- `/root/work/zzz-skills` 仓库已经存在，远端为 `https://github.com/mfkyddh/zzz-skills.git`
- 目标仓库里当前仅同步了 `zzz-oplinux-app-delivery`
- `OP_Linux` 仓库里几乎没有这项自动同步任务的 inventory、runbook 和治理登记
- WSL 本机 `1Panel` 计划任务尚未在仓库中形成正式受管资产

这意味着“仓库已存在、部分内容已同步”，但控制面和运维口径还没有闭环。

## 4. 核心设计选择

### 4.1 控制面归属

采用“`OP_Linux` 持有同步逻辑，1Panel 只做调度”的方案。

原因：

- 符合仓库既有的“Python + `uv` 为主栈，Bash 为薄包装”的决策
- 可以把同步逻辑、变更判定、失败策略、手动执行入口统一到仓库中
- 避免以后在 1Panel 页面里堆积不可审计的 Shell 逻辑

### 4.2 同步策略

采用“以源为准的镜像收敛”策略。

规则如下：

- 只同步源目录下一级名称匹配 `zzz-*` 的技能目录
- 目标仓库中对应技能目录按源目录内容完整覆盖
- 源目录中已删除或改名的 `zzz-*` 技能，在目标仓库中也要删除
- 无变化时不提交、不推送
- 有变化时才执行 `git add/commit/push`

### 4.3 调度入口

`1Panel` 计划任务只调用 `OP_Linux` 的统一入口，例如：

```bash
cd /root/work/OP_Linux && uv run python -m ops.cli ...
```

不把扫描、复制、Git 提交、推送等业务逻辑直接写在 1Panel 页面中。

## 5. 组件设计

建议拆成四个组件：

### 5.1 核心同步器

新增一个 Python 模块，例如：

- `ops/scripts/automation/sync_zzz_skills.py`

职责：

- 扫描 `/mnt/c/Users/Administrator/.codex/skills/zzz-*`
- 校验目标仓库 `/root/work/zzz-skills`
- 执行目录镜像收敛
- 统计新增、更新、删除结果
- 判断 Git 是否存在实际变化
- 有变化时执行提交与推送
- 输出结构化结果

### 5.2 CLI 统一入口

在 `ops.cli` 下补一个正式子命令，供手动和计划任务共用，例如：

- `uv run python -m ops.cli automation sync-zzz-skills`

职责：

- 暴露稳定入口
- 处理参数、退出码和打印结果
- 让 1Panel、人工排障、后续脚本都调用同一条命令

### 5.3 Inventory 登记

在 `inventory/servers/wsl/inventory.json` 中新增一类受管自动化资产，例如顶层 `automations` 或 `scheduled_tasks`，登记：

- 任务名
- 控制器类型：`1panel-cronjob`
- 周期：每 2 小时
- `cwd`
- 统一执行命令
- 源路径
- 目标仓库路径
- 目标分支
- 文档入口
- 验证命令

### 5.4 Runbook 与治理文档

新增专门 runbook，并在 WSL 治理文档中补充“1Panel 只做调度、业务逻辑必须收口到 OP_Linux”的规则。

## 6. 执行流

标准执行流如下：

1. `1Panel` 每 2 小时触发一次任务
2. 任务进入 `/root/work/OP_Linux`
3. 调用 `uv run python -m ops.cli automation sync-zzz-skills`
4. CLI 执行预检
5. 预检通过后扫描源目录中的所有 `zzz-*`
6. 对 `/root/work/zzz-skills` 执行镜像收敛
7. 若 Git 无差异，返回“无变化跳过”
8. 若 Git 有差异，则提交并推送到 `origin/main`
9. 输出结果，供 `1Panel` 执行记录查看

## 7. 预检规则

任务开始前必须先做预检，以下任一失败都直接退出：

- 源目录不存在
- 目标仓库不存在
- 目标仓库不是 Git 仓库
- 当前分支不是 `main`
- 目标仓库工作树不干净
- 本地分支落后于 `origin/main`

设计上不允许定时任务自动 stash、reset、pull --rebase 或 merge。

## 8. Git 策略

### 8.1 运行分支

- 本次完善开发分支：`codex/zzz-skills-sync`
- 定时任务实际操作的目标仓库分支：`/root/work/zzz-skills` 的 `main`

### 8.2 提交策略

有变化时固定执行：

```bash
git add -A
git commit -m "chore: sync zzz skills"
git push origin main
```

无变化时跳过 commit 和 push。

### 8.3 脏工作树保护

若 `/root/work/zzz-skills` 存在未提交改动，任务必须失败退出，并输出脏文件列表。

原因：

- 防止定时任务覆盖人工现场
- 防止把未知仓库状态继续放大

## 9. 幂等性与文件规则

### 9.1 幂等性目标

同一份源目录内容重复执行多次，结果必须一致：

- 不额外生成新提交
- 不反复改动时间戳导致假变化
- 不保留已经从源删除的陈旧技能目录

### 9.2 文件过滤

仅同步 `zzz-*` 技能目录及其必要文件，默认过滤常见临时垃圾，例如：

- `.DS_Store`
- `Thumbs.db`
- `__pycache__`

### 9.3 目标仓库收敛边界

目标仓库中：

- `.git/` 永远保留
- 明确保留的仓库级文件可以继续保留，例如 `README.md`、`.gitignore`
- `zzz-*` 目录必须与源目录保持一致
- 若出现未列入 allowlist 的非 `zzz-*` 仓库级文件，优先报错而不是静默删除

这样可以避免后续误删目标仓库里人工维护的正式仓库文件。

## 10. 状态与退出码口径

建议把结果状态固定成以下集合：

- `ok_no_changes`
- `ok_pushed`
- `failed_precheck`
- `failed_runtime`

其中：

- `ok_no_changes`：扫描和校验成功，但没有文件变化
- `ok_pushed`：有变化，且已成功提交并推送
- `failed_precheck`：源目录、目标仓库、Git 状态等前置条件失败
- `failed_runtime`：复制、删除、提交或推送过程失败

这样可以让 CLI 输出、1Panel 日志和 runbook 统一使用同一套术语。

## 11. 文档与纳管资产

至少补齐以下资产：

### 11.1 Inventory

更新：

- `inventory/servers/wsl/inventory.json`

新增本机受管计划任务登记。

### 11.2 Inventory 摘要

补充或创建：

- `inventory/servers/wsl/README.md`

简要说明 WSL 本机由 1Panel 托管 `zzz-skills-sync` 定时任务。

### 11.3 Runbook

新增：

- `docs/runbooks/wsl-zzz-skills-sync.md`

内容至少包括：

- 目的与边界
- 源/目标路径
- 手动执行方式
- 如何查看 1Panel 执行记录
- 无变化时的预期结果
- push 失败、工作树脏、源目录缺失时的排障办法

### 11.4 治理文档

更新以下文档之一或两者：

- `docs/architecture/linux-governance.md`
- `docs/runbooks/wsl-host-governance.md`

明确写入：

- WSL 本机 `1Panel` 计划任务只负责调度
- 计划任务业务逻辑必须通过 `OP_Linux` 仓库统一入口承载
- 新增本机自动化任务时，必须同步 inventory 与 runbook

## 12. 1Panel 计划任务口径

计划任务建议固定命名为：

- `wsl-zzz-skills-sync`

推荐调度周期：

- 每 2 小时一次

推荐工作目录：

- `/root/work/OP_Linux`

推荐执行命令：

```bash
uv run python -m ops.cli automation sync-zzz-skills
```

如果当前 CLI 子命令命名需要兼容现有结构，可保留一个薄包装脚本，但最终对 1Panel 暴露的仍应是单一稳定入口。

## 13. 验收标准

本设计完成后的验收标准如下：

1. `OP_Linux` 中存在正式 CLI 入口，可以手动执行 `zzz-skills` 同步
2. 源目录只有 `zzz-oplinux-app-delivery` 时，首次运行不会误删仓库允许保留文件
3. 源目录新增一个 `zzz-*` 技能后，执行任务会把该目录同步到 `/root/work/zzz-skills` 并自动推送
4. 源目录删除某个 `zzz-*` 技能后，执行任务会从目标仓库删除并自动推送
5. 源目录无变化时，执行任务返回 `ok_no_changes`
6. `/root/work/zzz-skills` 工作树脏时，任务直接失败，不覆盖现场
7. `inventory`、`runbook`、治理文档能够说明该任务的定位、入口和排障方法
8. WSL 本机 `1Panel` 计划任务可以稳定按每 2 小时运行一次

## 14. 实施边界

本设计允许在当前回合继续补齐：

- `OP_Linux` 中的同步器与 CLI
- `inventory` / `README` / `runbook` / 治理文档
- WSL 本机 `1Panel` 计划任务所需的正式命令口径

本设计不要求在当前回合实现：

- 对远端 `prod0-main` 的同步任务复制
- 对多个技能源目录的统一同步
- 自动处理目标仓库远端冲突
- 泛化为所有 Codex 全局技能的镜像仓库框架
