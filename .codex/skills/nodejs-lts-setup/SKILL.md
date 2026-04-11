---
name: nodejs-lts-setup
description: Install or upgrade Node.js to the latest official LTS in Ubuntu or WSL, usually with nvm, and switch npm to the Aliyun registry. Use when Codex is asked to set up a JavaScript runtime, replace an old Node.js version, fix user-level Node environments, or configure npm mirror settings such as https://npm.aliyun.com.
---

# Node.js LTS Setup

Verify the current official LTS release before changing anything, then install it in the target Linux user environment with `nvm`, set it as default, switch npm to the requested mirror, and verify that a fresh interactive shell resolves the expected versions.

## Workflow

1. Check the latest official LTS release on `nodejs.org` because the answer changes over time.
2. Detect the current user, `HOME`, and existing `node`, `npm`, and `nvm` state inside the target Ubuntu or WSL environment.
3. Install `nvm` for the target Linux user if it is missing.
4. Load `nvm`, install the verified LTS version, and set the default alias to that version.
5. Run `npm config set registry https://npm.aliyun.com` unless the user requested another registry.
6. Verify `node -v`, `npm -v`, and `npm config get registry` in a new interactive shell, not only in the current command.
7. Summarize what changed, including the old version if one existed.

## Command Pattern

Prefer running commands as the target Linux user explicitly. In WSL, use:

```bash
wsl -d Ubuntu -u <user> bash -lc '...'
```

Use explicit paths when shell quoting is fragile:

```bash
export NVM_DIR=/home/<user>/.nvm
. /home/<user>/.nvm/nvm.sh
```

Install `nvm` when needed:

```bash
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
```

Install and activate the verified LTS version:

```bash
export NVM_DIR=/home/<user>/.nvm
. /home/<user>/.nvm/nvm.sh
nvm install <lts-version>
nvm alias default <lts-version>
nvm use <lts-version>
```

Set the npm mirror:

```bash
npm config set registry https://npm.aliyun.com
```

Verify in a fresh interactive shell:

```bash
bash -ic 'node -v && npm -v && npm config get registry'
```

## Notes

- Install into the intended Linux user account, not `root`, unless the user explicitly asked for a system-wide root setup.
- Expect quoting issues when invoking `bash -lc` from PowerShell; prefer single quotes around the Bash payload and explicit absolute Linux paths.
- If the environment already has a legacy system Node.js on `PATH`, do not remove it unless the user asks. It is enough to ensure interactive shells resolve the `nvm` default version.
- Report the exact LTS version and registry value that were verified.
