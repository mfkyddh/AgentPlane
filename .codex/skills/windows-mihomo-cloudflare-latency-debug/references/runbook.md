# Windows Mihomo Cloudflare Latency Runbook

Use this when a Windows-host domain access is slow and the host may be using Clash Nyanpasu or Mihomo.

If you want one-shot collection first, run:

```powershell
pwsh.exe -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\zqf\projects\env_ubuntu\.codex\skills\windows-mihomo-cloudflare-latency-debug\scripts\measure-domain-latency.ps1 -Domain <domain> -Port 8443 -OriginIp <origin-ip>
```

## Goal

Identify which layer is slow:

- Windows system DNS
- Mihomo DNS mode (`fake-ip` or `redir-host`)
- Mihomo TUN interception
- IPv6 preference
- Cloudflare orange-cloud edge
- gray-cloud origin

## Fast Triage

1. Check Mihomo runtime, not the UI.
   - Query controller `/configs`
   - Record `mode`, `ipv6`, `tun.enable`

2. Check current resolution.
   - `Resolve-DnsName <domain>`
   - `Resolve-DnsName <domain> -NoHostsFile -DnsOnly`
   - `Get-DnsClientCache`

3. Run timing splits with:
   - default `curl.exe`
   - `curl.exe -4`
   - `curl.exe -6`
   Use `-w` to print `dns`, `tcp`, `tls`, `ttfb`, `total`

4. Run `curl.exe -vkI`
   - `Server: cloudflare` means Cloudflare path
   - `Server: nginx/...` means origin path

## Decision Table

- Default slow, `-4` fast, default remote is `2606:4700:...`
  IPv6 is pulling traffic to Cloudflare edge.

- Default slow, direct IP with `Host` fast
  The issue is name resolution or local DNS handling, not the server.

- `198.18.x.x` appears
  fake-ip is active.

- `mode: direct` but path still looks intercepted
  Check `tun.enable`; direct mode does not remove TUN.

- Cloudflare API shows gray-cloud A, but default access still reaches Cloudflare
  Look for AAAA, wildcard records, or cached local answers.

- TUN is off, Cloudflare is out, but the domain is still slow
  Time system `A` and `AAAA` queries. Slow `AAAA` is a common Windows-side bottleneck.

## Windows DNS Check

1. Find active DNS servers.
   - `Get-DnsClientServerAddress`

2. Time `A` and `AAAA` against:
   - system resolver
   - `223.5.5.5`
   - `1.1.1.1`
   - `8.8.8.8`

3. If system `AAAA` is much slower than public resolvers, fix Windows DNS first.

## Mitigation Order

1. Flush DNS cache
2. Recheck `-4` versus default
3. Improve Windows DNS servers
4. Adjust Mihomo DNS mode if needed
5. Disable IPv6 if the domain repeatedly falls onto a bad AAAA path
6. With approval, add a `hosts` entry for the exact gray-cloud hostname

## Repository-Specific Proven Pattern

For a gray-cloud hostname on this machine:

- Gray-cloud origin itself can be fast
- Cloudflare IPv6 path can still be slow
- Windows system `AAAA` handling can add its own delay
- Best deterministic fix order is:
  - improve Windows DNS first
  - then add a `hosts` pin for the exact hostname only if the user approves it
