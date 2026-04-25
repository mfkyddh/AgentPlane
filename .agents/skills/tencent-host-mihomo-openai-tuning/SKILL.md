---
name: tencent-host-mihomo-openai-tuning
description: Diagnose and optimize slow OpenAI or ChatGPT egress on this repository's Tencent Cloud Ubuntu hosts when Mihomo is already deployed. Use when `prod0-main` or another active Tencent host reaches `api.openai.com`, `auth.openai.com`, `sentinel.openai.com`, or `chatgpt.com` too slowly, when the `GPT` proxy group may be pinned to a poor node, or when you need to benchmark candidate nodes through the Mihomo controller, hot-switch the selector, and verify that both API and web flows improved.
---

# Tencent Host Mihomo OpenAI Tuning

Use this skill on the remote host side, not the Windows host side.

Prefer this workflow when Mihomo is already healthy enough to forward traffic, but OpenAI-related traffic is still slow because the `GPT` selector is pinned to a bad or unstable node.

If you need the exact command sequence, read [references/runbook.md](references/runbook.md) first.

## Read First

- Start from WSL and use the project SSH aliases in `secrets/ssh/config`.
- On this repository's Tencent hosts, the SSH path may depend on a Windows-host proxy such as `nc -X connect -x 172.25.240.1:7890 %h %p`.
- When the effective remote user is non-root, prefer running privileged Mihomo inspection through `sudo`.
- Do not trust `curl --noproxy '*'` as a true direct-path test when Mihomo TUN is enabled. If `Meta` TUN owns the route, traffic can still be intercepted.
- Read controller settings from `/etc/mihomo/config.yaml` instead of assuming stale values.

## Workflow

1. Confirm that Mihomo is the actual path.
   Check:
   - `systemctl status mihomo`
   - `ss -lntup` for `mixed-port` and controller listeners
   - `resolvectl status`
   - `getent ahosts api.openai.com`
   If OpenAI domains resolve to `198.18.x.x`, fake-ip is active and Mihomo is in path.

2. Read the live controller endpoint and secret from `/etc/mihomo/config.yaml`.
   At minimum capture:
   - `mixed-port`
   - `external-controller`
   - `secret`
   - `profile.store-selected`

3. Inspect the `GPT` selector before changing anything.
   Query `/proxies/GPT` through the Mihomo controller.
   Capture:
   - current `now`
   - selector `type`
   - full candidate list in `all`

4. Benchmark candidate nodes with controller delay checks, but do not stop there.
   Use Mihomo's per-proxy delay API against an OpenAI URL such as `https://api.openai.com`.
   Prefer shortlists from the best delay results, then validate them with real endpoint requests.

5. Validate real traffic, not just synthetic delay.
   Test at least:
   - `https://api.openai.com/v1/models`
   - `https://auth.openai.com`
   - `https://chatgpt.com`
   Expected healthy shapes:
   - `api.openai.com/v1/models` often returns `401` without a key
   - `auth.openai.com` often returns `403`
   - `chatgpt.com` often returns `403`
   A correct HTTP status with lower total or TLS time is better evidence than a low one-off delay sample.

6. Hot-switch the `GPT` selector through the controller.
   Prefer controller `PUT /proxies/GPT` over editing YAML when the only change is the selected node.
   Re-read `/proxies/GPT` after switching to verify `now` changed.

7. Favor stability over the absolute fastest single sample.
   Re-run the same validation at least twice on the finalists.
   Reject nodes that show intermittent TLS spikes or endpoint-specific failures, even if their first delay sample looked best.

## Interpreting Common Patterns

- Delay API says a node is fast, but `api.openai.com/v1/models` fails or spikes.
  The node is not a safe final choice for OpenAI API traffic.

- `auth.openai.com` and `chatgpt.com` improve, but API traffic still fails.
  Keep searching. Some nodes are good enough for the web path but unstable for API TLS.

- Explicit proxy and default requests look equally slow.
  The bottleneck is probably the selected upstream node, not the host's local TUN forwarding.

- `curl -x http://127.0.0.1:7890` fails, but Mihomo is running.
  The proxy may be bound to another address such as `172.19.0.1:7890`; check the live listener instead of assuming loopback.

- Logs show frequent requests from `172.17.x.x`.
  A Docker container is likely generating repeated OpenAI web traffic. Improving the node helps, but connection reuse inside the caller may still matter.

## Verified Lessons From This Repository

- Mihomo TUN can capture OpenAI domains via fake-ip even when a test tries to bypass environment proxy variables.
- The live controller endpoint and mixed proxy listener must be read from the host instead of copied from stale incident notes.
- Delay API results are only a shortlist; repeated real endpoint checks decide the final selector.
- Prefer the most stable repeated endpoint results over the fastest single sample.

## Verification Checklist

- `systemctl is-active mihomo` is `active`
- `getent ahosts api.openai.com` reflects the expected fake-ip or DNS mode
- `/proxies/GPT` shows the intended final `now`
- Repeated real-endpoint tests improve versus the previous node
- `profile.store-selected: true` is confirmed if the selection must survive restart
