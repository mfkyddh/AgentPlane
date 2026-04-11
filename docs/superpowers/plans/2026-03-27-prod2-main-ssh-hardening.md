# Prod2 Main SSH Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `38.12.32.94` 以 `prod2-main` 名义纳入 OP_Linux 控制面，改造成仅允许仓库受管私钥登录的 root SSH 入口，并补齐封禁暴力破解策略与台账。

**Architecture:** 在控制面本地生成并保存 `secrets/ssh/keys/prod2-main.pem`，通过一次密码首连把公钥写入远端 `authorized_keys`，随后收紧 `sshd` 与 `fail2ban`/`ufw` 配置。最终把 SSH 配置、结构化 inventory、README 摘要和原始探测输出一起落库，确保后续远端操作可以统一通过 `uv run python -m ops.cli remote bash prod2-main` 执行。

**Tech Stack:** OpenSSH, fail2ban, UFW, Ubuntu shell, `uv`, OP_Linux inventory docs

---

### Task 1: 本地生成并纳管 `prod2-main` SSH 凭据

**Files:**
- Create: `secrets/ssh/keys/prod2-main.pem`
- Modify: `secrets/ssh/config`

- [ ] **Step 1: 生成仓库受管私钥**

Run: `ssh-keygen -t ed25519 -f /root/work/OP_Linux/secrets/ssh/keys/prod2-main.pem -N '' -C 'prod2-main-root@op_linux'`
Expected: 生成 `.pem` 私钥与 `.pub` 公钥。

- [ ] **Step 2: 收紧本地密钥权限**

Run: `chmod 600 /root/work/OP_Linux/secrets/ssh/keys/prod2-main.pem /root/work/OP_Linux/secrets/ssh/config`
Expected: 私钥与 SSH 配置均为仅所有者可读写。

- [ ] **Step 3: 注册仓库 SSH 别名**

在 `secrets/ssh/config` 追加：

```sshconfig
Host prod2-main 38.12.32.94
  HostName 38.12.32.94
  User root
  IdentityFile /root/work/OP_Linux/secrets/ssh/keys/prod2-main.pem
  ProxyCommand nc -X connect -x 172.25.240.1:7890 %h %p
  IdentitiesOnly yes
  ControlMaster auto
  ControlPersist 10m
  ControlPath /tmp/oplinux-ssh-%C
  StreamLocalBindUnlink yes
  StrictHostKeyChecking yes
  BatchMode yes
  ConnectTimeout 10
```

- [ ] **Step 4: 先行记录首次接管的连接方式**

Run: `ssh -F /root/work/OP_Linux/secrets/ssh/config -o BatchMode=no -o StrictHostKeyChecking=accept-new root@38.12.32.94 true`
Expected: 当前仍需密码首连，后续切到 alias + key。

### Task 2: 远端写入公钥并完成 SSH 加固

**Files:**
- Remote modify: `/root/.ssh/authorized_keys`
- Remote modify: `/etc/ssh/sshd_config`
- Remote create or modify: `/etc/fail2ban/jail.d/sshd.local`

- [ ] **Step 1: 通过密码首连创建 `.ssh` 目录并安装公钥**

Run: `sshpass -p '<password>' ssh -o StrictHostKeyChecking=accept-new root@38.12.32.94 'install -d -m 700 /root/.ssh && cat >> /root/.ssh/authorized_keys' < /root/work/OP_Linux/secrets/ssh/keys/prod2-main.pem.pub`
Expected: 远端 `authorized_keys` 包含控制面公钥。

- [ ] **Step 2: 验证密钥已可登录**

Run: `ssh -F /root/work/OP_Linux/secrets/ssh/config prod2-main 'whoami && hostname'`
Expected: 输出 `root` 与远端主机名。

- [ ] **Step 3: 收紧 `sshd`**

在远端确保以下键存在且生效：

```text
Port 22
PermitRootLogin prohibit-password
PasswordAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
MaxAuthTries 1
UsePAM yes
```

Run: `sshd -T | grep -E '^(port|permitrootlogin|passwordauthentication|pubkeyauthentication|authenticationmethods|maxauthtries) '`
Expected: 返回上面的最终值。

- [ ] **Step 4: 启用失败封禁**

远端安装并配置 `fail2ban` 的 `sshd` jail：

```ini
[sshd]
enabled = true
port = 22
mode = aggressive
maxretry = 1
findtime = 10m
bantime = 24h
```

Run: `fail2ban-client status sshd`
Expected: `Jail list` 中包含 `sshd`。

- [ ] **Step 5: 校验防火墙**

Run: `ufw status numbered`
Expected: 仅保留业务要求端口，至少包含 `22/tcp`。

### Task 3: 补齐控制面台账

**Files:**
- Create: `inventory/servers/prod2-main/inventory.json`
- Create: `inventory/servers/prod2-main/README.md`
- Create: `inventory/servers/prod2-main/probe-output.txt`

- [ ] **Step 1: 采集远端基线**

Run: `uv run python -m ops.cli remote bash prod2-main --script-file /root/work/OP_Linux/ops/scripts/remote/example.sh`
Expected: 能通过 alias 正常执行远端脚本。

- [ ] **Step 2: 记录结构化 inventory**

至少登记：
- `label`: `2号生产机（主力）`
- `public_ip`: `38.12.32.94`
- `ssh.auth`: `ssh-key`
- `ssh.password_authentication`: `false`
- `ssh.permit_root_login`: `true`
- `ssh.permit_root_login_exception`: `prohibit-password`
- `ssh.authentication_methods`: `publickey`
- `security.fail2ban.maxretry`: `1`

- [ ] **Step 3: 记录 README 摘要**

README 需说明：
- 当前登录方式已改为 `SSH 密钥`
- 密码认证已禁用
- `MaxAuthTries 1`
- `fail2ban sshd` 失败 `1` 次封禁 `24h`
- 仓库 SSH 别名与密钥文件名

- [ ] **Step 4: 保存探测原始输出**

把 `hostname`、`uname -a`、`lsb_release -ds`、`sshd -T` 关键项、`fail2ban-client status sshd`、`ufw status` 等输出写入 `probe-output.txt`。

### Task 4: 最终验证

**Files:**
- Verify: `secrets/ssh/config`
- Verify: `inventory/servers/prod2-main/inventory.json`
- Verify: `inventory/servers/prod2-main/README.md`

- [ ] **Step 1: 验证仓库 alias 远端 Bash 入口**

Run: `printf '%s\n' 'set -euo pipefail' 'whoami' 'hostname' | uv run python -m ops.cli remote bash prod2-main`
Expected: 成功输出 `root` 和主机名。

- [ ] **Step 2: 验证密码认证已关闭**

Run: `sshpass -p '<password>' ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no -o NumberOfPasswordPrompts=1 root@38.12.32.94 true`
Expected: 失败，且远端不接受密码认证。

- [ ] **Step 3: 验证远端安全状态**

Run: `ssh -F /root/work/OP_Linux/secrets/ssh/config prod2-main 'sshd -T | grep -E \"^(permitrootlogin|passwordauthentication|authenticationmethods|maxauthtries) \" && fail2ban-client status sshd'`
Expected: `permitrootlogin prohibit-password`、`passwordauthentication no`、`authenticationmethods publickey`、`maxauthtries 1`，且 `sshd` jail 启用。
