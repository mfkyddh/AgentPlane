# Local Control Plane Secrets

本目录对应 `local/control-plane/*` secret scope。

当前 bootstrap 会生成并校验这些 repo-local 文件，真实值由人类填写：

- `../../env/prod-jump.env`
- `../../ssh/config`
- `../../ssh/keys/*.pem`

完成填写后运行：

- `uv run python -m agentplane.cli bootstrap verify-secrets --repo-root <repo-root>`
- `uv run python -m agentplane.cli bootstrap doctor --repo-root <repo-root>`
