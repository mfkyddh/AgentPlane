# 1Panel Data Layout

## Fresh Install Standard

- Use the official 1Panel installer.
- At the install-directory prompt, enter `/data`.
- The repository standard runtime directory is `/data/1panel`.
- The service binaries still live under `/usr/local/bin` and the systemd units still live under `/etc/systemd/system`.

## Minimum Checks Before Install

- `ps -p 1 -o comm=` returns `systemd`
- `docker --version` works
- `systemctl is-active docker` returns `active`
- `ss -ltnp` confirms the target 1Panel port is free
- `command -v 1panel` confirms whether the host already has 1Panel

## WSL Checks

- Confirm Windows-side access with `http://127.0.0.1:<port>/<entrance>`.
- Confirm Linux-side access with `curl -I http://127.0.0.1:<port>/<entrance>`.
- If the installer pauses unexpectedly in a China-network environment, check whether it is waiting on the Docker mirror prompt before the port prompt.

## Remote Host Checks

- Use the repository SSH aliases and a sudo-capable account.
- Verify the final listener with `ss -ltnp | grep ":<port>"`.
- Verify the services with `systemctl status 1panel-core 1panel-agent --no-pager`.
- Verify the panel entry with `curl -I http://127.0.0.1:<port>/<entrance>` from the host itself before testing the public path.

## Existing `/opt/1panel` Installations

- Treat `/opt/1panel` as legacy in this repository context.
- Do not move an existing install to `/data/1panel` blindly.
- First inspect:
  - `/usr/local/bin/1pctl`
  - `/etc/systemd/system/1panel-core.service`
  - `/etc/systemd/system/1panel-agent.service`
  - the live data tree under `/opt/1panel`
- Normalize to `/data/1panel` only after the current base directory and restart path are fully understood.
