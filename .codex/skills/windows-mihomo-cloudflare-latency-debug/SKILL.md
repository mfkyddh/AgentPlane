---
name: windows-mihomo-cloudflare-latency-debug
description: Diagnose why a domain is slow from the Windows host when Clash Nyanpasu or Mihomo is involved, especially for mixed Cloudflare orange-cloud and gray-cloud routes, TUN mode, fake-ip or redir-host DNS, and IPv4 versus IPv6 path selection. Use when a user asks to compare latency for one or more Cloudflare-fronted domains from Windows, identify whether the delay is in DNS, TUN, Cloudflare edge, AAAA handling, or origin access, and apply reversible Windows-side mitigations such as DNS changes or a hosts override.
---

# Windows Mihomo Cloudflare Latency Debug

Use this skill from the Windows host side. The goal is to separate five different slow points that are easy to confuse:

- Cloudflare orange-cloud edge latency
- gray-cloud origin latency
- Mihomo TUN interception
- fake-ip or redir-host DNS behavior
- Windows system DNS, especially slow AAAA handling

Keep the workflow layered. Do not jump to a fix before the path is identified.

If the task is a live incident and speed matters more than background explanation, read [references/runbook.md](references/runbook.md) first and use it as the execution checklist.

## Read First

- Prefer PowerShell on Windows for host-side checks.
- Current verified Clash Nyanpasu config path on this machine:
  `C:\Users\Administrator\AppData\Roaming\Clash Nyanpasu\config\clash-config.yaml`
- Current verified controller endpoint shape on this machine:
  `http://127.0.0.1:17650`
- Without explicit user permission, do not edit Windows host files such as `hosts` or the Clash config.
- For repeated sampling, prefer the bundled script:
  [`scripts/measure-domain-latency.ps1`](scripts/measure-domain-latency.ps1)
- When running the script from a `\\wsl.localhost\...` path, prefer:
  ```powershell
  pwsh.exe -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\zqf\projects\env_ubuntu\.codex\skills\windows-mihomo-cloudflare-latency-debug\scripts\measure-domain-latency.ps1 -Domain <domain> -Port 8443 -OriginIp <origin-ip>
  ```
  This avoids Windows execution-policy failures on unsigned UNC scripts.

## Workflow

1. Confirm the actual Mihomo runtime state instead of trusting the UI.
   Read the controller secret from the config file, then query `/configs` and relevant proxy groups.
   Check:
   - `mode`
   - `ipv6`
   - `tun.enable`
   - active selector for the main fallback group

2. Confirm what Windows is resolving right now.
   Use:
   - `Resolve-DnsName <domain>`
   - `Resolve-DnsName <domain> -NoHostsFile -DnsOnly`
   - `Get-DnsClientCache | Where-Object { $_.Entry -eq '<domain>' }`
   Signals:
   - `198.18.x.x` means fake-ip
   - `2606:4700::/32` means Cloudflare IPv6 edge
   - host file answers show TTL `0`

3. Split timing into DNS, TCP, TLS, TTFB, and total.
   Use repeated `curl.exe` with `-w`:
   ```powershell
   curl.exe -k -o NUL -sS -w "remote=%{remote_ip} code=%{http_code} dns=%{time_namelookup} tcp=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} total=%{time_total}`n" https://example:8443/
   ```
   Run all of:
   - default
   - `-4`
   - `-6`
   The default path tells you what Windows actually prefers.
   For live work, you can run:
   ```powershell
   pwsh.exe -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\zqf\projects\env_ubuntu\.codex\skills\windows-mihomo-cloudflare-latency-debug\scripts\measure-domain-latency.ps1 -Domain <domain> -Port 8443 -OriginIp <origin-ip>
   ```

4. Confirm whether the response is Cloudflare or origin.
   Use `curl.exe -vkI`.
   Signals:
   - `Server: cloudflare` and `CF-RAY` mean orange-cloud edge or AAAA path reaching Cloudflare
   - `Server: nginx/...` means origin or local reverse proxy

5. If needed, confirm DNS record truth from Cloudflare API, not only local resolution.
   On this repository, the reusable token lives in `secrets/env/prod-jump.env`.
   Check:
   - exact `A` and `AAAA` for the hostname
   - whether `proxied` is `true` or `false`
   - whether a wildcard record is shadowing expectations

6. If the domain is still slow after TUN or proxy changes, measure Windows system DNS directly.
   Compare:
   - system resolver
   - `223.5.5.5`
   - `1.1.1.1`
   - `8.8.8.8`
   Time both `A` and `AAAA`.
   If system `AAAA` is consistently much slower than public resolvers, the bottleneck is the Windows DNS chain, not the origin.

7. Only then choose a mitigation.

## Interpreting Common Patterns

- Default slow, `-4` fast, default remote is `2606:4700:...`
  The host is preferring IPv6 and reaching Cloudflare edge.

- `Resolve-DnsName` returns `198.18.x.x`
  fake-ip is active. Measure whether fake-ip itself is acceptable before blaming the origin.

- `mode: direct` but access still behaves like it is intercepted
  Direct mode does not mean TUN is out of the path. Check `tun.enable` and route/interface output.

- Default domain access is slow, but `--resolve host:port:ip` or direct IP plus `Host` is fast
  The bottleneck is the domain-resolution path, not the server path.

- Cloudflare API shows gray-cloud `A`, but Windows still reaches Cloudflare on default access
  Look for `AAAA`, wildcard records, cached answers, or local resolver synthesis.

- After disabling TUN, the domain is still slow but direct-IP tests are fast
  The remaining bottleneck is usually Windows system DNS, often `AAAA`.

## Remediation Ladder

Use the least invasive fix that matches the verified bottleneck.

1. Runtime-only checks
   - compare default, `-4`, `-6`
   - flush DNS cache
   - verify active Clash runtime state

2. Resolver-side fixes
   - set better Windows DNS servers on the active interface
   - retest system `A` and `AAAA`

3. Mihomo-side DNS fixes
   - toggle `fake-ip` versus `redir-host`
   - disable IPv6 if the domain repeatedly falls onto a slow AAAA path
   - note that domain-specific DNS policy may not behave as expected; verify after every change

4. Deterministic local override
   - with explicit user approval, add a `hosts` entry for the exact gray-cloud domain
   - this is the fastest way to bypass a broken or slow system resolver path

## Verified Lessons From This Repository

- A gray-cloud origin can still look slow on Windows if AAAA answers or Cloudflare IPv6 edge paths are preferred locally.
- On this machine, Windows system DNS can add several seconds when `AAAA` queries are slow, even after TUN is disabled.
- Switching Windows DNS servers can reduce the delay materially, but a `hosts` entry for the exact gray-cloud hostname is the deterministic last-resort fix when the user approves it.

## Verification Checklist

- Default `curl.exe -vkI https://<domain>:8443/` shows the expected remote IP family
- Default repeated `curl.exe` timings match the intended path
- `Resolve-DnsName <domain>` and `Get-DnsClientCache` agree with the intended override
- Response headers prove whether the path is Cloudflare or origin
- Any Windows-side override is backed up before editing and is reversible
