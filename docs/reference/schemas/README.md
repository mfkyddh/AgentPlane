---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: both
layer: engineering
---

# Schema 索引

结论：本目录保存 AgentPlane 公开合同的机器可读 schema。长期说明仍放在 reference 文档，schema 用于工具、应用仓库和 CI 做结构校验。

## 当前 Schema

| Schema | 用途 | 上游说明 |
| --- | --- | --- |
| [app-delivery-contract-v2.schema.json](app-delivery-contract-v2.schema.json) | 应用仓库 `deploy/agentplane/contract.yaml` 的 `schema_version: 2` 合同 | [应用仓库协作规范](../../architecture/agentplane-app-collaboration.md) |

## 维护规则

- 新 schema 必须带稳定 `$id`。
- 破坏性字段变更必须新增 schema 版本，不覆盖旧版本文件。
- CLI 校验逻辑仍是正式执行门禁，schema 是外部工具和应用仓库的早期反馈层。

