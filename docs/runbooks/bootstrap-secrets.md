# Bootstrap Secrets

日零启动只保留四个正式动作：

1. 检查当前宿主、backend 和工作区绑定：
   `uv run python -m agentplane.cli bootstrap inspect-local --repo-root <repo-root>`
2. 生成本地 secrets 空壳：
   `uv run python -m agentplane.cli bootstrap init-secrets --repo-root <repo-root>`
3. 由人类填写真实 secrets：
   - `secrets/env/prod-jump.env`
   - `secrets/ssh/config`
   - `secrets/ssh/keys/*.pem`
   - `secrets/services/onepanel-login.<target>.env`
4. 校验 secrets 是否已就绪：
   `uv run python -m agentplane.cli bootstrap verify-secrets --repo-root <repo-root>`
5. 汇总当前仓库是否已具备 Agent 接管条件：
   `uv run python -m agentplane.cli bootstrap doctor --repo-root <repo-root>`

## Generated Scaffold

`bootstrap init-secrets` 会创建以下空壳和说明文件，但不会写入真实敏感值：

- `secrets/local/control-plane/README.md`
- `secrets/targets/wsl/README.md`
- `secrets/targets/prod0-main/README.md`
- `secrets/targets/prod2-main/README.md`
- `secrets/env/prod-jump.env`
- `secrets/ssh/config`
- `secrets/services/onepanel-login.<target>.env`

## Notes

- 日常正式入口仍然是 `uv run python -m agentplane.cli ...`。
- bootstrap 只负责本地 scaffold 与 secret readiness；target 级 data-service admin secrets、host truth 和 domain 操作交给 Agent 在后续 flow 里处理。
- `bootstrap verify-secrets` 只报告缺项、占位值和 readiness，不打印 secret 明文。
