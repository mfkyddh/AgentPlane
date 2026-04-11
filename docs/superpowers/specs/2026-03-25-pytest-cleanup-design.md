# Pytest Entry And Cleanup CLI Design

## Goal

让仓库的 Python 测试入口开箱即用，并把 WSL 本地临时产物清理流程从“只会列计划”补到“可执行且可验证”。

## Scope

- 让 `uv run pytest` 在仓库根直接可用，不再依赖手工设置 `PYTHONPATH`。
- 为 `ops.cli cleanup` 增加 `apply` 子命令。
- 定义第一批 WSL 白名单清理目标，仅覆盖仓库内已明确忽略的临时目录和缓存。

## Design

### Pytest Entry

当前 `uv run pytest` 失败的根因是项目未声明可安装的本地包。方案是让 `pyproject.toml` 明确 `build-system` 和 wheel 打包配置，把 `ops` 作为本地包安装到 `uv run` 创建的环境中。这样测试和 `python -m ops.cli` 的入口都来自同一套包边界，而不是依赖临时环境变量注入。

### Cleanup Plan And Apply

`cleanup plan` 继续负责枚举动作；`cleanup apply` 基于相同动作集执行删除，并输出：

- `removed`: 成功删除的路径
- `missing`: 计划中已不存在的路径
- `skipped`: 因越界或不支持而跳过的路径

执行器只允许删除：

- 仓库根内路径
- 匹配白名单模式的路径

第一版白名单包括：

- `.playwright-cli/`
- `tmp/`
- `.venv/`
- `.pytest_cache/`
- `tests/__pycache__/`
- `.worktrees/*/.venv`
- `.worktrees/*/.pytest_cache`
- `.worktrees/*/tmp`
- `.worktrees/*/tests/__pycache__`
- `.worktrees/*/tmp/*.tar`

### Verification

- `uv run pytest tests/test_pyproject_config.py tests/test_cleanup.py tests/test_cli_entrypoints.py -q`
- `uv run pytest -q`
- `uv run python -m ops.cli cleanup plan --env wsl --repo-root /root/work/OP_Linux`
- `uv run python -m ops.cli cleanup apply --env wsl --repo-root /root/work/OP_Linux`
