---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: both
layer: technical
---

# 🔐 Bootstrap Secrets

结论：`agentplane bootstrap ...` 负责 takeover truths、target scope README 和 readiness 判定，人类只填 secrets 和少量 identity。

Linux / WSL 里直接用 `agentplane ...`。

Windows 宿主统一走：
`uv run python -m agentplane.cli ...`

不要在 Windows 控制面根目录直接执行 `uv run ...`，否则会踩 Linux `.venv` 与 Windows 本地环境混用问题。

`bootstrap inspect-local` 会报告 `cli_entrypoint`：如果 `agentplane` 已在 PATH 中可用，会显示实际 executable；否则会给出 `uv run python -m agentplane.cli` fallback 和 `uv tool install -e <repo-root>` 安装建议。

日零启动只保留五个正式动作：

1. 检查当前宿主、backend 和工作区绑定：
   `agentplane bootstrap inspect-local --repo-root <repo-root>`

   **预期输出**：
   ```text
   [INFO] Control root: <repo-root>
   [INFO] Backend: WSL2
   [INFO] Workspace binding: OK
   ```

2. 生成 bootstrap truth 空壳：
   `agentplane bootstrap init-secrets --repo-root <repo-root>`

   **预期输出**：
   ```text
   [INFO] Created secrets/local/control-plane/README.md
   [INFO] Created secrets/targets/wsl/README.md
   [INFO] Created secrets/ssh/config
   [INFO] Created secrets/ssh/keys/
   ```

3. 由人类只填写 Agent takeover 所需 truths：
   - `secrets/ssh/config`
   - `secrets/ssh/keys/*.pem`

4. 校验 truths 是否已就绪：
   `agentplane bootstrap verify-secrets --repo-root <repo-root>`

   **预期输出**：
   ```text
   [PASS] SSH config exists
   [PASS] SSH keys found: 2
   [PASS] Target secrets scaffold: wsl, prod0-main
   ```

5. 汇总当前仓库是否已具备 Agent 接管条件：
   `agentplane bootstrap doctor --repo-root <repo-root>`

   **预期输出**：
   ```text
   [PASS] Repository structure
   [PASS] Secrets readiness
   [PASS] Backend connectivity
   [INFO] AgentPlane is ready for operations
   ```

## Generated Scaffold

`bootstrap init-secrets` 会创建以下空壳和说明文件，但不会写入真实敏感值：

- `secrets/local/control-plane/README.md`
- `secrets/targets/wsl/README.md`
- `secrets/targets/prod0-main/README.md`
- `secrets/ssh/config`
- `secrets/ssh/keys/`

## Notes

- 日常正式入口仍然是 `agentplane ...`。
- bootstrap 只负责 takeover truths、target scope README 和 readiness 判定；target 级 host truth、data-service admin secrets 和 domain 操作交给 Agent 在后续 flow 里处理。
- `secrets/env/prod-jump.env` 属于 projection-only 文件；只有明确的投影消费方需要时才单独补齐，不再作为 bootstrap blocker。
- `onepanel-login.<target>.env` 这类人工浏览器登录辅助材料不参与 bootstrap contract。
- `bootstrap verify-secrets` 只报告缺项、结构化 contract 问题和 readiness，不打印 secret 明文。
