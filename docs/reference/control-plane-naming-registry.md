---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-02
superseded_by: null
---

# 控制面命名注册表

本文定义“一件东西在不同层应该叫什么”，避免 `newapi`、`new-api`、`service key`、容器名、compose 目录名半同步漂移。

本表中的“可强制”仅适用于正式 app contract 对象；基础设施服务、第三方官方镜像、历史快照目录不在 Phase 1 强制范围内。

## Phase 1 可强制合同

| 字段 | Phase 1 硬规则 | 说明 |
| --- | --- | --- |
| `app_id` | 必须匹配 `^[a-z0-9]+(?:-[a-z0-9]+)*$` | 在 `inventory/apps/catalog.json` 当前对应 `apps[].app` 字段；仅允许小写字母、数字、单个短横线；禁止前后短横线、连续短横线、下划线、大写。 |
| `inventory.service_key` | 必须与 `app_id` 完全相等 | Phase 1 不接受别名，不接受运行态再命名。 |
| `image_family` | 正式 app 交付镜像 family 固定为 `<app_id>-prod` | 指镜像名去掉 tag / digest 后的 family，例如 `sub2api-prod:latest` 与 `sub2api-prod@sha256:...` 的 family 都是 `sub2api-prod`。 |
| `prod_container` | 必须等于 `<app_id>-prod` | 不是“包含 `-prod`”，是完整等值。 |
| `dev_container` | 必须等于 `<app_id>-dev` | 不是“包含 `-dev`”，是完整等值。 |

## 当前受 Phase 1 强制的正式应用

| app_id | compose_dir | image_family | prod_container | dev_container | inventory.service_key |
| --- | --- | --- | --- | --- | --- |
| `sub2api` | `infra/compose/sub2api` | `sub2api-prod` | `sub2api-prod` | `sub2api-dev` | `sub2api` |

## 使用要求

- 新正式 app object 进入控制面前，必须先在本表新增一行，再允许进入合同校验。
- 未列入本表的对象，本阶段不得按正式 app naming contract 做失败判定。
