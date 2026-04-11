# 1Panel OpenResty Container Naming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `prod0-main` 上 1Panel 官方 OpenResty 容器名规范化为 `1panel-openresty-prod`，并把仓库规范与 inventory 一并更新到生产 `-prod` / WSL `-dev` 口径。

**Architecture:** 这次变更不做一次性 `docker rename`，而是修改 1Panel OpenResty 应用源目录中的 `.env`，让 Compose 读取新的 `CONTAINER_NAME` 后重建容器。仓库侧同步更新 `AGENTS.md` 和 `inventory/servers/prod0-main/*`，确保运维记录与实际运行态一致。

**Tech Stack:** Docker Compose, 1Panel app runtime files, SSH, Markdown, JSON

---

### Task 1: Confirm source of truth and current runtime

**Files:**
- Read: `/data/1panel/apps/openresty/openresty/.env`
- Read: `/data/1panel/apps/openresty/openresty/docker-compose.yml`
- Read: `inventory/servers/prod0-main/README.md`
- Read: `inventory/servers/prod0-main/inventory.json`

- [ ] **Step 1: Check the current runtime name**

Run: `ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "docker ps --format '{{.Names}}'" | grep '1Panel-openresty-engw'`
Expected: prints `1Panel-openresty-engw`

- [ ] **Step 2: Confirm Compose reads `CONTAINER_NAME`**

Run: `ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "sed -n '1,40p' /data/1panel/apps/openresty/openresty/docker-compose.yml && echo && sed -n '1,20p' /data/1panel/apps/openresty/openresty/.env"`
Expected: `docker-compose.yml` contains `container_name: ${CONTAINER_NAME}` and `.env` contains `CONTAINER_NAME='1Panel-openresty-engw'`

- [ ] **Step 3: Inspect repository references**

Run: `cd /root/work/OP_Linux && rg -n '1Panel-openresty-engw' inventory/servers/prod0-main AGENTS.md README.md`
Expected: matches in `inventory/servers/prod0-main/README.md` and `inventory/servers/prod0-main/inventory.json`

### Task 2: Update the remote 1Panel OpenResty runtime name

**Files:**
- Modify: `/data/1panel/apps/openresty/openresty/.env`

- [ ] **Step 1: Back up the current `.env`**

Run: `ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "cp /data/1panel/apps/openresty/openresty/.env /data/1panel/apps/openresty/openresty/.env.bak-20260324-naming"`
Expected: backup file created with no output

- [ ] **Step 2: Change `CONTAINER_NAME` to the production standard**

Run: `ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "sed -i \"s/CONTAINER_NAME='1Panel-openresty-engw'/CONTAINER_NAME='1panel-openresty-prod'/\" /data/1panel/apps/openresty/openresty/.env && grep '^CONTAINER_NAME' /data/1panel/apps/openresty/openresty/.env"`
Expected: prints `CONTAINER_NAME='1panel-openresty-prod'`

- [ ] **Step 3: Recreate only the OpenResty app container**

Run: `ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "cd /data/1panel/apps/openresty/openresty && docker compose up -d --force-recreate openresty"`
Expected: Compose recreates the service and starts a container named `1panel-openresty-prod`

- [ ] **Step 4: Verify runtime state**

Run: `ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "docker inspect 1panel-openresty-prod --format 'Name={{.Name}} Image={{.Config.Image}} NetworkMode={{.HostConfig.NetworkMode}} Restart={{.HostConfig.RestartPolicy.Name}}'"`
Expected: output includes `/1panel-openresty-prod`, `1panel/openresty:1.27.1.2-5-1-focal`, `host`, and `always`

### Task 3: Verify service continuity after rename

**Files:**
- Read: remote runtime only

- [ ] **Step 1: Check loopback HTTPS on the host**

Run: `ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "curl -k -I --resolve token.zzzai.cloud:2053:127.0.0.1 https://token.zzzai.cloud:2053/ && echo && curl -k -I --resolve pay.zzzai.cloud:2053:127.0.0.1 https://pay.zzzai.cloud:2053/pay"`
Expected: both responses contain `HTTP/1.1 200 OK`

- [ ] **Step 2: Check public HTTPS from the repository host**

Run: `curl -k -I https://token.zzzai.cloud:2053/ && echo && curl -k -I https://pay.zzzai.cloud:2053/pay`
Expected: both responses contain `HTTP/1.1 200 OK`

- [ ] **Step 3: Confirm old runtime name is gone**

Run: `ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "docker ps --format '{{.Names}}'" | grep -E '1Panel-openresty-engw|1panel-openresty-prod'`
Expected: only `1panel-openresty-prod` is present

### Task 4: Update repository rules and inventory

**Files:**
- Modify: `AGENTS.md`
- Modify: `inventory/servers/prod0-main/README.md`
- Modify: `inventory/servers/prod0-main/inventory.json`

- [ ] **Step 1: Add explicit 1Panel OpenResty naming guidance**

Edit `AGENTS.md` so the 1Panel section states the canonical OpenResty container names are `1panel-openresty-dev` for WSL and `1panel-openresty-prod` for production hosts.

- [ ] **Step 2: Replace old production references**

Edit `inventory/servers/prod0-main/README.md` and `inventory/servers/prod0-main/inventory.json` to replace `1Panel-openresty-engw` with `1panel-openresty-prod`.

- [ ] **Step 3: Record the normalization event**

Add a short note in `inventory/servers/prod0-main/README.md` that `2026-03-24` normalized the 1Panel OpenResty container name to the production `-prod` convention.

### Task 5: Final verification and review

**Files:**
- Read: all modified files

- [ ] **Step 1: Verify repository matches the new naming**

Run: `cd /root/work/OP_Linux && rg -n '1Panel-openresty-engw|1panel-openresty-prod|1panel-openresty-dev' AGENTS.md inventory/servers/prod0-main/README.md inventory/servers/prod0-main/inventory.json`
Expected: old name only appears in historical context if intentionally preserved; new names appear in rules and current-state inventory

- [ ] **Step 2: Review the diff**

Run: `cd /root/work/OP_Linux && git diff -- AGENTS.md inventory/servers/prod0-main/README.md inventory/servers/prod0-main/inventory.json docs/superpowers/specs/2026-03-24-1panel-openresty-container-naming-design.md docs/superpowers/plans/2026-03-24-1panel-openresty-container-naming.md`
Expected: diff shows only naming normalization, design/plan docs, and inventory wording updates

- [ ] **Step 3: Commit**

Run:

```bash
cd /root/work/OP_Linux
git add AGENTS.md inventory/servers/prod0-main/README.md inventory/servers/prod0-main/inventory.json docs/superpowers/specs/2026-03-24-1panel-openresty-container-naming-design.md docs/superpowers/plans/2026-03-24-1panel-openresty-container-naming.md
git commit -m "chore: normalize 1panel openresty container naming"
```

Expected: one commit with the naming normalization and documentation updates
