# Local Control Plane Secrets

本目录对应 `local/control-plane/*` secret scope。

当前 bootstrap 只会生成并校验这些 Agent takeover truths，真实值由人类填写：

- `../../ssh/config`
- `../../ssh/keys/*.pem`

Windows 宿主请统一通过 `invoke-agentplane-windows-uv.ps1` 进入 CLI，不要直接在控制面根目录执行 `uv run ...`。

完成填写后运行：

- `agentplane bootstrap verify-secrets --repo-root <repo-root>`
- `agentplane bootstrap doctor --repo-root <repo-root>`

`../../env/prod-jump.env` 这类 projection/compat 文件只在相关后续 flow 需要时再单独处理。
