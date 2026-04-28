---
name: onepanel-openresty-site-migration
description: Use when migrating an existing single-domain site on this repository's Ubuntu or Example Cloud hosts to a 1Panel-managed OpenResty website, especially when the old public entry must stay online and a new HTTPS port needs parallel validation.
---

# 1Panel OpenResty Site Migration

## Overview

Use this skill for the "single site first" migration pattern: keep the current edge entry online, then move one domain's runtime to the official 1Panel OpenResty website stack and validate it on a new HTTPS port before any wider cutover.

Core rule: prefer the official 1Panel OpenResty app and website objects. Do not replace them with a self-built OpenResty container unless the user explicitly asks for that deviation.

## When to Use

- A domain currently works behind `nginx-ui`, another reverse proxy, or a legacy Nginx deployment, but the user wants the site itself moved into 1Panel.
- The old public entry such as `:8443` must remain live while a new entry such as `:2053` is brought up in parallel.
- The site should become a 1Panel website with 1Panel-managed certificate material instead of reusing cert files from another stack.
- The target service is a reverse-proxy style website, not a full stack that needs a new application container.

Do not use this skill for:

- Full edge cutovers where 1Panel/OpenResty must immediately replace every existing public listener.
- Cases where the user explicitly wants a custom OpenResty container instead of the official 1Panel app.
- Pure certificate issuance work with no website migration.

## Baseline Failures This Skill Prevents

- Missing `Referer` and `Origin` when 1Panel security entrance is enabled, which causes `/api/v2/...` calls to fail even with a valid token.
- Falling back to a self-built OpenResty container because the agent only knows read APIs or treats every mutation as reserved.
- Falling back to legacy direct flows instead of the canonical `CLI-first` skills that own app and website mutation flow.
- Assuming the default 1Panel website generator will correctly expose a non-standard HTTPS port without any post-generation patching.
- Trusting 1Panel UI or app status text over real listeners, active config files, and live HTTP responses.

## Verified Workflow

1. Confirm the 1Panel API interface is enabled and collect:
   - `ONEPANEL_BASE_URL`
   - `ONEPANEL_API_KEY`
   - optional `ONEPANEL_SECURITY_ENTRANCE`
   - any API IP whitelist requirement
2. Route the official OpenResty app install and parameter flow through the canonical `CLI-first` app skill:
   - use `onepanel-app-ops`
   - keep `plan`, `apply --execute`, and `verify` split in the routed canonical skill
3. Route website creation and HTTPS binding through the canonical website skill:
   - use `onepanel-website-ops`
4. Route certificate import through the canonical website skill instead of a direct HTTP write path:
   - keep certificate material in the 1Panel website SSL store managed by `onepanel-website-ops`
5. Route HTTPS binding through the canonical website skill:
   - keep website HTTPS enable / verify flow inside `onepanel-website-ops`
6. If the default generated config does not express the required non-standard HTTPS port, apply the smallest possible patch to the 1Panel-managed site files rather than replacing the whole runtime.
7. Keep the old edge entry online and validate the new port independently before any cutover.

## Minimal Patch Rule

Only patch the files 1Panel already generated for that website. On this repository's current production layout, the typical targets are:

- `/data/1panel/www/conf.d/<site>.conf`
- `/data/1panel/www/sites/<site>/proxy/root.conf`
- `/data/1panel/www/sites/<site>/proxy/<restricted-path>.conf`

Patch only what 1Panel could not express, such as:

- `listen <new-port> ssl`
- `listen [::]:<new-port> ssl`
- preserving an existing restricted-path ACL like `/setup`

Do not use this patch step as an excuse to fork the full OpenResty config away from 1Panel management.

## Validation Checklist

- Source host loopback request to the new port returns the expected homepage status.
- External request to the new port homepage returns `200`.
- External request to each restricted path such as `/setup` returns the expected deny status, typically `403`.
- Listener check confirms both IPv4 and IPv6 binds for the new port.
- The certificate served on the new port comes from the 1Panel website SSL store, not from `nginx-ui` or another unrelated runtime path.
- The legacy public entry remains healthy during the parallel run window.

## Common Mistakes

- Reintroducing a custom OpenResty container because it feels faster than using the official 1Panel app.
- Checking only homepage `200` and missing that restricted paths were accidentally opened.
- Assuming a panel status of `Running` means the generated port mapping and config are correct.
- Treating a detected `listen 0.0.0.0` as sufficient without also checking `[::]` and an actual external IPv6-capable client.

## Real Example Pattern

`token.example.net` was migrated with this pattern:

- the old `:8443` edge stayed on `nginx-ui`
- the new `:2053` entry was served by the official 1Panel OpenResty website
- the certificate was moved into the 1Panel website SSL store
- `/setup` was validated separately from the homepage because homepage `200` alone was not enough

Treat that as one proven example of the pattern, not as the only supported domain or port combination.
