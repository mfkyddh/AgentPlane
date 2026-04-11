# 1Panel API Over SSH Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `prod0-main` 建立基于 SSH + 本机回环的 1Panel API 标准操作路径，写入本地与远端 env，验证 API 调用成功，并通过 API 将白名单收敛到 `127.0.0.1`。

**Architecture:** 使用仓库内单独的 `onepanel-api.env` 保存 1Panel API 所需参数，所有真实 API 请求都先 SSH 到 `prod0-main` 再访问 `http://127.0.0.1:2096`。利用现有 1Panel API 客户端或等效签名请求完成只读验证和 API 配置更新，再把这一流程沉淀进现有技能文档。

**Tech Stack:** SSH, shell, Node.js, existing 1Panel signed client, dotenv-style env files, Markdown

---

### Task 1: Create the shared env layout

**Files:**
- Create: `templates/services/onepanel-api.env.example`
- Create: `secrets/services/onepanel-api.env`

- [ ] **Step 1: Write the tracked example**

Create `templates/services/onepanel-api.env.example` with the required variables and safe placeholder values.

- [ ] **Step 2: Write the real local env**

Create `secrets/services/onepanel-api.env` with the production values:
- `ONEPANEL_BASE_URL=https://1panel.zzzai.cloud:8443`
- `ONEPANEL_CONNECT_BASE_URL=http://127.0.0.1:2096`
- `ONEPANEL_API_KEY=<provided>`
- `ONEPANEL_SECURITY_ENTRANCE=0f0e8602e3`
- `ONEPANEL_TIMEOUT_MS=30000`
- `ONEPANEL_SKIP_TLS_VERIFY=false`

### Task 2: Sync the env to the production repository

**Files:**
- Modify/create remote `/opt/env_ubuntu/secrets/services/onepanel-api.env`

- [ ] **Step 1: Confirm the remote repository path**

Run: `ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main 'test -d /opt/env_ubuntu/secrets/services'`
Expected: exit 0

- [ ] **Step 2: Upload the env**

Copy `secrets/services/onepanel-api.env` to `/opt/env_ubuntu/secrets/services/onepanel-api.env` on `prod0-main` and tighten permissions to `600`.

- [ ] **Step 3: Verify parity**

Run a non-secret diff check on variable keys or checksum to confirm local and remote env files match.

### Task 3: Verify the API call path from the production host

**Files:**
- Read: `.codex/skills/openclaw-1panel/dist/scripts/cli.js`

- [ ] **Step 1: Load the env on `prod0-main`**

Run the remote command through SSH and `source /opt/env_ubuntu/secrets/services/onepanel-api.env`.

- [ ] **Step 2: Execute one read-only API request**

Use the existing signed CLI or an equivalent minimal request to call a safe endpoint such as a settings read or dashboard read. If `BindDomain` is enabled, preserve the public origin in `ONEPANEL_BASE_URL` and dial the loopback listener through `ONEPANEL_CONNECT_BASE_URL`.

- [ ] **Step 3: Confirm success**

Expected: JSON success response from the 1Panel API, proving the host-local loopback + API key + security entrance combination works.

### Task 4: Update the API whitelist through the API

**Files:**
- Read/write through API only

- [ ] **Step 1: Discover the current API config schema**

Use read endpoints first to learn the payload shape needed by `/api/v2/core/settings/api/config/update`.

- [ ] **Step 2: Submit the whitelist update**

Send the minimal API config update that keeps the current API enabled and changes the whitelist to only `127.0.0.1`.

- [ ] **Step 3: Re-read the API config**

Verify the returned config now reflects only `127.0.0.1` in the whitelist.

- [ ] **Step 4: Record the boundary**

Document that `IpWhiteList=127.0.0.1` protects the direct 1Panel listener, but another local reverse proxy on the same host can still forward requests that appear local to 1Panel.

### Task 5: Update skill documentation and repository guidance

**Files:**
- Modify: `.codex/skills/openclaw-1panel/SKILL.md`
- Modify: `.codex/skills/openclaw-1panel/README.zh-CN.md`
- Modify: `.codex/skills/openclaw-1panel/references/module-groups.md`
- Modify: `README.md` if needed

- [ ] **Step 1: Document the repository-preferred API path**

State that for this repository, 1Panel API operations should SSH to the target host and call `http://127.0.0.1:2096`.

- [ ] **Step 2: Document the env location**

State that the local canonical env file is `secrets/services/onepanel-api.env`, mirrored to `/opt/env_ubuntu/secrets/services/onepanel-api.env` on `prod0-main`.

- [ ] **Step 3: Document whitelist behavior**

State that after API validation, the recommended steady state is to keep the API whitelist limited to `127.0.0.1`.

### Task 6: Final verification and commit

**Files:**
- Read: all modified files

- [ ] **Step 1: Verify the env files exist**

Check both local and remote `onepanel-api.env` files exist with correct permissions.

- [ ] **Step 2: Verify API access still works after whitelist narrowing**

Run the same read-only API request through SSH again and confirm it still succeeds.

- [ ] **Step 3: Review the diff and commit**

Commit the env template, documentation, and skill updates in one commit after verification.
