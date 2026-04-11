# Target Secrets: <target>

本目录对应 `targets/<target>/*` secret scope。

当前 bootstrap 会生成并校验这些 repo-local 文件，真实值由人类填写：

- `../../services/onepanel-login.<target>.env`

目标级 host truth 与运行态 secrets 继续由 Agent 在后续 domain/host 流程中接管：

- `../../hosts/<target>/...`
