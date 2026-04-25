# Bootstrap Secrets

Linux / WSL 里直接用 `agentplane ...`。

Windows 宿主统一走：
`pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli ...`

不要在 Windows 控制面根目录直接执行 `uv run ...`，否则会踩 Linux `.venv` 与 Windows 本地环境混用问题。

日零启动只保留五个正式动作：

1. 检查当前宿主、backend 和工作区绑定：
   `agentplane bootstrap inspect-local --repo-root <repo-root>`
2. 生成 bootstrap truth 空壳：
   `agentplane bootstrap init-secrets --repo-root <repo-root>`
3. 由人类只填写 Agent takeover 所需 truths：
   - `secrets/ssh/config`
   - `secrets/ssh/keys/*.pem`
4. 校验 truths 是否已就绪：
   `agentplane bootstrap verify-secrets --repo-root <repo-root>`
5. 汇总当前仓库是否已具备 Agent 接管条件：
   `agentplane bootstrap doctor --repo-root <repo-root>`

## Generated Scaffold

`bootstrap init-secrets` 会创建以下空壳和说明文件，但不会写入真实敏感值：

- `secrets/local/control-plane/README.md`
- `secrets/targets/wsl/README.md`
- `secrets/targets/prod0-main/README.md`
- `secrets/targets/prod2-main/README.md`
- `secrets/ssh/config`
- `secrets/ssh/keys/`

## Notes

- 日常正式入口仍然是 `agentplane ...`。
- bootstrap 只负责 takeover truths、target scope README 和 readiness 判定；target 级 host truth、data-service admin secrets 和 domain 操作交给 Agent 在后续 flow 里处理。
- `secrets/env/prod-jump.env` 属于 projection-only 文件；只有明确的投影消费方需要时才单独补齐，不再作为 bootstrap blocker。
- `onepanel-login.<target>.env` 这类人工浏览器登录辅助材料不参与 bootstrap contract。
- `bootstrap verify-secrets` 只报告缺项、结构化 contract 问题和 readiness，不打印 secret 明文。
