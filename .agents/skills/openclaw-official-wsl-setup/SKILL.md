---
name: openclaw-official-wsl-setup
description: Install or repair OpenClaw on Ubuntu or WSL with the official non-Docker flow, prefer the official installer with git/source mode when pnpm or mainland mirrors are needed, wire a custom OpenAI-compatible endpoint through onboarding, fix dashboard token access, verify the systemd user service, and debug Feishu channel delivery issues after onboarding, especially on WSL behind a Windows-host proxy such as Clash or Mihomo. Use when the user asks for the official OpenClaw install path, wants to avoid Docker, needs OpenClaw to use CLIProxyAPI or another OpenAI-compatible base URL, or hits token, service, or Feishu message-delivery issues after onboarding.
---

# OpenClaw Official WSL Setup

Set up OpenClaw on Ubuntu or WSL using the upstream installer and onboarding flow, not the repository Docker deployment. Prefer this skill when the user wants the official path, a local loopback-only gateway, a custom OpenAI-compatible model endpoint such as CLIProxyAPI, or needs to repair Feishu bot delivery on the same installation.

## Workflow

1. Verify the effective Linux user, home directory, and shell context before doing anything else.
   Use `wsl -d Ubuntu -u <user> -- bash -ic '...'` for commands that depend on `nvm`, shell PATH, or the generated `openclaw` wrapper.
   If quoting is fragile, call the `nvm` Node binary explicitly, such as `/home/<user>/.nvm/versions/node/v24.14.0/bin/node`.
2. Check the target runtime first.
   Confirm Node is `>= 22.12`.
   Confirm the command runs as the intended Linux user, not `root`.
   Confirm `systemctl --user` is available if the user wants `--install-daemon`.
3. Choose the official install mode.
   Use the default installer first only when npm global install is acceptable:
   ```bash
   curl -fsSL https://openclaw.ai/install.sh | bash
   ```
   If the user wants `pnpm`, the network is China-mainland-sensitive, or `npm install -g openclaw` fails, stay on the official installer but switch to source mode:
   ```bash
   npm config set registry https://registry.npmmirror.com
   corepack pnpm config set registry https://registry.npmmirror.com
   curl -fsSL https://openclaw.ai/install.sh | bash -s -- --install-method git --git-dir /home/<user>/projects/openclaw --no-onboard
   ```
4. Prefer the OpenClaw source checkout on a Linux filesystem path such as `/home/<user>/projects/openclaw`, not `/mnt/c/...`.
5. For non-interactive onboarding, always include `--accept-risk`.
   For a custom OpenAI-compatible endpoint, use:
   ```bash
   export CUSTOM_API_KEY="..."
   openclaw onboard --non-interactive \
     --accept-risk \
     --mode local \
     --auth-choice custom-api-key \
     --custom-base-url "http://localhost:8318/v1" \
     --custom-model-id "gpt-5" \
     --custom-provider-id "cli-proxy-api" \
     --custom-compatibility openai \
     --secret-input-mode ref \
     --gateway-port 18789 \
     --gateway-bind loopback \
     --install-daemon \
     --daemon-runtime node \
     --skip-skills
   ```
6. When using `--secret-input-mode ref` for a custom provider, persist the referenced env var in `~/.openclaw/.env` as well.
   `CUSTOM_API_KEY` existing only in the onboarding process environment is not enough for the systemd user service.
   Example:
   ```bash
   mkdir -p ~/.openclaw
   printf 'CUSTOM_API_KEY=%s\n' "$CUSTOM_API_KEY" > ~/.openclaw/.env
   chmod 600 ~/.openclaw/.env
   ```
7. If onboarding installs a systemd user service on WSL, enable lingering so the service survives logout:
   ```bash
   sudo loginctl enable-linger <user>
   ```
8. If the dashboard says Control UI assets are missing after a source install, build them from the upstream checkout:
   ```bash
   export PATH="/home/<user>/.nvm/versions/node/v24.14.0/bin:$PATH"
   corepack pnpm -C /home/<user>/projects/openclaw ui:build
   systemctl --user restart openclaw-gateway
   ```
9. Set or re-set the default model explicitly after onboarding:
   ```bash
   openclaw models set cli-proxy-api/gpt-5
   ```
10. Re-open the dashboard with the official helper:
    ```bash
    openclaw dashboard
    ```
    Current versions emit a tokenized URL with `#token=...`, not `?token=...`.
    If the UI still prompts for auth, paste the gateway token into Control UI settings.

## Feishu Channel Repair

Use this section when OpenClaw is running but the Feishu bot does not receive messages.

1. Verify the actual runtime user first.
   Do not assume the human login user owns the active OpenClaw instance.
   Check both the expected user and `root`:
   ```bash
   wsl -d Ubuntu -u <user> -- bash -lc 'echo $HOME; command -v openclaw || true; systemctl --user status openclaw-gateway --no-pager || true'
   wsl -d Ubuntu -u root -- bash -lc 'echo $HOME; command -v openclaw || true; systemctl --user status openclaw-gateway --no-pager || true'
   ```
   The active instance is the one that has `~/.openclaw`, `~/.config/systemd/user/openclaw-gateway.service`, and a live `openclaw-gateway`.

2. Inspect the active Feishu config, service env, and recent logs.
   Read:
   - `~/.openclaw/openclaw.json`
   - `~/.config/systemd/user/openclaw-gateway.service`
   - `journalctl --user -u openclaw-gateway -n 200 --no-pager`
   Focus on:
   - `connectionMode`
   - `requireMention`
   - `dmPolicy`
   - `allowFrom`
   - `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`
   - `bot open_id resolved`
   - `ws connect failed`

3. Separate Feishu credential problems from WebSocket transport problems.
   If logs show `bot open_id resolved`, App ID and App Secret are already working.
   Do not treat the SDK message about enabling persistent connection as proof that the Feishu console is misconfigured; it may still appear even when long-connection mode is already enabled.
   When needed, verify the endpoint directly through the current proxy:
   ```bash
   curl -x http://<wsl-gateway-ip>:7890 https://open.feishu.cn/callback/ws/endpoint \
     -H 'Content-Type: application/json' \
     -d '{"app_id":"<appId>","app_secret":"<appSecret>"}'
   ```
   If the response returns `code: 0` and a `wss://msg-frontier.feishu.cn/...` URL, Feishu long-connection capability is fine and the problem is farther downstream.

4. On WSL, verify whether outbound traffic must traverse a Windows-host proxy.
   Check the current WSL gateway:
   ```bash
   wsl -d Ubuntu -u root -- bash -lc "ip route show default | awk '{print \$3; exit}'"
   ```
   If the Windows host runs Clash or Mihomo, prefer that gateway IP such as `172.x.x.1`, not `127.0.0.1`.
   Typical Clash Nyanpasu config path on this machine:
   - `C:\Users\Administrator\AppData\Roaming\Clash Nyanpasu\config\clash-config.yaml`
   - `C:\Users\Administrator\AppData\Roaming\Clash Nyanpasu\config\nyanpasu-config.yaml`
   Confirm:
   - `mixed-port: 7890`
   - `allow-lan: true`
   - `tun.enable: true`
   - `enable_system_proxy: true`

5. If HTTP calls succeed through the proxy but Feishu WebSocket still fails, patch the plugin WebSocket client to use a proxy agent.
   The failure pattern is:
   - REST calls such as tenant token or `/callback/ws/endpoint` succeed
   - `openclaw-gateway` still logs repeated `ws connect failed`
   Inspect the installed extension under the active runtime user, for example `~/.openclaw/extensions/openclaw-lark/src/core/lark-client.js`.
   If `new Lark.WSClient(...)` does not pass a proxy-capable `agent`, add one that derives from `HTTPS_PROXY`, `ALL_PROXY`, or `HTTP_PROXY`.
   A working pattern is:
   ```js
   import { HttpsProxyAgent } from 'https-proxy-agent';

   function resolveWSProxyAgent() {
     const proxyUrl =
       process.env.HTTPS_PROXY ||
       process.env.https_proxy ||
       process.env.ALL_PROXY ||
       process.env.all_proxy ||
       process.env.HTTP_PROXY ||
       process.env.http_proxy;
     return proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;
   }
   ```
   Then pass it into `Lark.WSClient`:
   ```js
   this._wsClient = new Lark.WSClient({
     appId,
     appSecret,
     domain: resolveBrand(this.account.brand),
     loggerLevel: Lark.LoggerLevel.info,
     agent: resolveWSProxyAgent(),
   });
   ```
   Install the dependency inside the extension directory if needed:
   ```bash
   cd ~/.openclaw/extensions/openclaw-lark
   npm install https-proxy-agent@7 --no-fund --no-audit
   ```

6. Re-check policy settings before declaring the channel fixed.
   In `~/.openclaw/openclaw.json`:
   - `requireMention=true`: group messages must `@机器人`
   - `dmPolicy=allowlist`: private chat works only for `allowFrom`
   - `dmPolicy=open`: any private chat user is allowed
   If the user wants broad private-chat access:
   ```bash
   openclaw config set channels.feishu.dmPolicy open
   openclaw config set channels.feishu.allowFrom '["*"]'
   openclaw config validate
   systemctl --user restart openclaw-gateway
   ```

## Verification

Run these checks at the end:

- `openclaw --version`
- `openclaw status`
- `openclaw models status`
- `openclaw gateway status`
- `curl http://127.0.0.1:18789/healthz`
- `openclaw agent --agent main --message "Reply with exactly OK."`

If `openclaw status` shows the service is running but the gateway is unreachable, inspect:

- `journalctl --user -u openclaw-gateway -n 120 --no-pager`
- `~/.openclaw/.env`
- `~/.openclaw/openclaw.json`

If the issue is Feishu delivery, also verify:

- `journalctl --user -u openclaw-gateway -n 200 --no-pager`
- wait 20-60 seconds after restart and ensure there is no fresh `ws connect failed`
- look for `event-dispatch is ready` and `ws client ready`
- `lsof -Pan -p <gateway-pid> -i` or `ss -tpn state established` to confirm the gateway holds an established connection to the proxy listener when a host proxy is required
- send one fresh Feishu test message after restart
- in group tests, `@机器人` if `requireMention=true`

## Durable Pitfalls

- The generated `~/.local/bin/openclaw` wrapper may fail with `node: not found` unless the command runs in an interactive shell that loads `nvm`, or you bypass the wrapper with an absolute Node path.
- The official dashboard helper currently emits a `#token=` fragment URL. If a user tries `?token=...` and still gets `unauthorized`, regenerate the link with `openclaw dashboard`.
- A successful non-interactive onboarding can still leave the gateway crash-looping if the referenced `CUSTOM_API_KEY` is missing or empty in `~/.openclaw/.env`.
- Source installs can finish with a working gateway but a broken dashboard until `pnpm ui:build` is run.
- On this machine, the source install may report a non-blocking warning that the systemd service uses an `nvm` Node path instead of a system Node.
- The active OpenClaw instance may be under `root` even when the human operator expects `zqf` or another normal user.
- A successful `bot open_id resolved` means Feishu credentials work; keep debugging transport instead of rotating secrets blindly.
- On this Windows+WSL setup, Feishu WebSocket traffic may need the Windows host proxy even when ordinary HTTP checks already succeed.
- The `openclaw-lark` patch lives inside the installed extension under `~/.openclaw/extensions`; extension upgrades may overwrite it.
- Group-message tests can produce false negatives when `requireMention=true`.

## Report Back

Keep the final report concrete:

- Linux user and home directory
- Install mode used: official npm or official git/source mode
- Source checkout path
- Registry mirror used, if any
- Dashboard URL and whether token auth is enabled
- Default model and custom provider base URL
- Service state and whether `loginctl enable-linger` was applied
- Active runtime user if different from the expected operator
- Feishu `connectionMode`, `dmPolicy`, and `requireMention` when the channel was part of the task
- Proxy target in the user service env when a host proxy was involved
- Whether Feishu `/callback/ws/endpoint` returned a valid WebSocket URL
- Whether the plugin needed a proxy-agent patch
