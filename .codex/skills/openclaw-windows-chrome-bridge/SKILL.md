---
name: openclaw-windows-chrome-bridge
description: Configure, repair, or operate OpenClaw browser automation when OpenClaw runs in WSL and Chrome runs on the Windows host. Use when the user wants OpenClaw in WSL to control Windows Chrome through remote CDP, wants Browse actions to be driven by OpenClaw agent messages, needs a stable Windows localhost-to-WSL bridge, or needs to understand why current Chrome builds do not expose the daily-use default profile to remote debugging.
---

# OpenClaw Windows Chrome Bridge

Use this skill when OpenClaw runs inside Ubuntu/WSL but the browser to automate is Google Chrome on the Windows host.

The supported pattern on this machine is:

- OpenClaw Gateway in WSL
- Windows Chrome started with `--remote-debugging-port`
- WSL attaches through a `remote` browser profile with `cdpUrl`
- If Chrome only listens on `127.0.0.1`, add a Windows `portproxy` bridge and point WSL at that bridge
- For agent-driven browsing, send a precise `openclaw agent` message that explicitly requires `browser profile remote`

Do not prefer `user` or `existing-session` for WSL-to-Windows control. On this machine, `remote CDP` is the stable path.

## Workflow

1. Verify the active OpenClaw runtime user first.
   Check both the expected Linux user and `root`.
   The active instance is the one that has a live `openclaw-gateway` plus `~/.openclaw/openclaw.json`.
   Example:
   ```bash
   wsl.exe -d Ubuntu -u root --cd /root -- bash -lc 'openclaw --version; systemctl --user status openclaw-gateway --no-pager'
   ```

2. Read the current browser config before editing.
   Inspect `~/.openclaw/openclaw.json` and preserve unrelated provider, agent, and channel settings.
   The desired browser shape is:
   ```json
   {
     "browser": {
       "enabled": true,
       "headless": false,
       "defaultProfile": "remote",
       "profiles": {
         "remote": {
           "cdpUrl": "http://<windows-host-reachable-address>:<port>",
           "attachOnly": true,
           "color": "#2F855A"
         }
       }
     }
   }
   ```

3. Start Windows Chrome for automation.
   On current Windows Chrome builds here, do not assume the daily-use default profile can be exposed with `--remote-debugging-port`.
   Prefer a dedicated user data dir under `C:\Users\Administrator\.codex\`.
   If local helper scripts are present under `agentplane/scripts/browser/`, prefer the launcher helper:
   ```powershell
   powershell -ExecutionPolicy Bypass -File agentplane/scripts/browser/start-chrome-bridge.ps1
   ```
   Equivalent manual example:
   ```powershell
   Start-Process -FilePath 'C:\Program Files\Google\Chrome\Application\chrome.exe' `
     -ArgumentList '--remote-debugging-port=9222','--user-data-dir=C:\Users\Administrator\.codex\openclaw-chrome-profile'
   ```

4. Verify Windows CDP locally first.
   Confirm:
   ```powershell
   Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:9222/json/version'
   Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -eq 9222 }
   ```

5. If WSL cannot reach `127.0.0.1:9222`, add a Windows bridge.
   On this machine, the stable pattern is a Windows `portproxy` listener such as `9223 -> 127.0.0.1:9222`.
   Example:
   ```powershell
   netsh interface portproxy add v4tov4 listenport=9223 listenaddress=0.0.0.0 connectport=9222 connectaddress=127.0.0.1
   netsh advfirewall firewall add rule name="OpenClaw Chrome CDP 9223" dir=in action=allow protocol=TCP localport=9223
   ```
   Then confirm from WSL:
   ```bash
   wsl.exe -d Ubuntu -u root --cd /root -- curl -fsS http://<wsl-default-gateway-ip>:9223/json/version
   ```

6. Discover the Windows host address visible from WSL.
   Prefer the WSL default route gateway:
   ```bash
   ip route show default
   ```
   Typical result on this machine is `172.x.x.1`.
   Use that gateway IP in `browser.profiles.remote.cdpUrl` when the bridge listens on a Windows host port.
   If the local helper exists, prefer:
   ```bash
   bash agentplane/scripts/browser/print-wsl-cdp-url.sh
   ```

7. Restart OpenClaw and validate the remote profile.
   ```bash
   systemctl --user restart openclaw-gateway
   openclaw config validate
   openclaw browser profiles --json
   openclaw browser status --browser-profile remote --json
   ```
   If the local repair helper exists, prefer it when the bridge, config, or gateway state may be stale:
   ```bash
   bash agentplane/scripts/browser/repair-browser-stack.sh
   ```

8. Prove real browser control, not just connectivity.
   Run:
   ```bash
   openclaw browser open https://example.com --browser-profile remote --json
   openclaw browser snapshot --browser-profile remote --json --limit 40
   openclaw browser click e6 --browser-profile remote --json
   openclaw browser screenshot --browser-profile remote --json
   ```

9. Drive Browse through OpenClaw agent messages when the user wants the agent itself to operate Chrome.
   If the local helper exists, use:
   ```bash
   bash agentplane/scripts/browser/browse-via-agent.sh https://chatgpt.com/team-sign-up
   ```
   The helper uses a dedicated session id by default so it does not fight with an existing `main` TUI or agent session lock.
   Equivalent direct command:
   ```bash
   openclaw agent --agent main --session-id browse-remote-001 --message "使用 Browse 工具和 browser profile remote 打开 https://example.com 。先检查 browser status，再打开页面，然后告诉我页面标题、当前 URL，以及是否遇到登录页、验证码或权限限制。不要切换到别的 profile；如果失败，原样返回错误。" --thinking medium --timeout 180 --json
   ```
   If the agent reports browser timeout or HTTP 404 while `openclaw browser status` says the remote profile is healthy, restart the gateway once, then retry the agent turn once.

## Bridge Stability

- `netsh interface portproxy` rules are stored by Windows and survive reboot.
- The specific bridge `0.0.0.0:9223 -> 127.0.0.1:9222` is stable because the connect target is Windows loopback, not the changing WSL guest IP.
- The bridge depends on:
  - Chrome actually listening on `127.0.0.1:9222`
  - Windows `iphlpsvc` running
  - the firewall rule still allowing the listener port
- The WSL-facing address may change across reboots because the WSL default gateway can change. Usually only `cdpUrl` host needs re-checking; the Windows bridge itself does not need to be recreated unless removed.

## Recovery Commands

List bridge rules:
```powershell
netsh interface portproxy show v4tov4
```

Replace the bridge:
```powershell
netsh interface portproxy delete v4tov4 listenport=9223 listenaddress=0.0.0.0
netsh interface portproxy add v4tov4 listenport=9223 listenaddress=0.0.0.0 connectport=9222 connectaddress=127.0.0.1
```

Check the listener:
```powershell
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -eq 9223 }
```

Check from WSL:
```bash
curl -fsS http://<gateway-ip>:9223/json/version
```

Print the current WSL-visible CDP URL:
```bash
bash agentplane/scripts/browser/print-wsl-cdp-url.sh
```

Repair the bridge, update `cdpUrl`, and restart the gateway:
```bash
bash agentplane/scripts/browser/repair-browser-stack.sh
```

Send an agent message that uses Browse on the remote profile:
```bash
bash agentplane/scripts/browser/browse-via-agent.sh https://example.com
```

## Durable Pitfalls

- Chrome 136+ on this machine may reject or ignore attempts to expose the default daily-use profile through remote debugging. Use a dedicated `--user-data-dir`.
- `openclaw browser` remote profiles require a `color` field in config on this version.
- If `openclaw browser status` reports gateway closure right after a restart, verify `openclaw config validate` and inspect `journalctl --user -u openclaw-gateway -n 120 --no-pager`.
- If `9222` works on Windows but not from WSL, it usually means Chrome only bound loopback and still needs the Windows-side bridge.
- If an `openclaw agent` Browse run fails with browser timeout or HTTP 404, do not keep retrying blindly; repair the bridge/gateway first, then resend the agent instruction once.

## Report Back

Include:

- active OpenClaw runtime user
- Chrome launch mode and user data dir
- Windows local CDP port
- Windows bridge port, if used
- WSL-visible host/IP used in `cdpUrl`
- final `remote` profile status
- one successful real browser action such as `open`, `snapshot`, or `screenshot`
- when agent-driven browsing was part of the task, one successful `openclaw agent` Browse result with the opened page title and final URL
