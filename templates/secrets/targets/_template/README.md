# Target Secrets: <target>

本目录对应 `targets/<target>/*` secret scope。

目标级 host truth 与运行态 secrets 继续由 Agent 在后续 domain/host 流程中接管：

- `../../hosts/<target>/...`

projection/compat 文件与人工登录辅助材料不属于 bootstrap takeover contract：

- `../../env/prod-jump.env`
- `../../services/onepanel-api*.env`
- `../../services/onepanel-login.<target>.env`
