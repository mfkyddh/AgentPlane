---
status: active
owner: AgentPlane maintainers
last_verified: 2026-06-18
audience: both
---

# 故障排除

> 结论：常见问题和解决方案，帮助快速定位和解决问题。

---

## SSH 连接问题

### 连接超时

**症状**：
```
ssh: connect to host xxx.xxx.xxx.xxx port 22: Connection timed out
```

**可能原因**：
1. 服务器防火墙阻止 SSH 连接
2. SSH 服务未启动
3. 网络不可达

**解决方案**：
```bash
# 1. 检查服务器是否可达
ping xxx.xxx.xxx.xxx

# 2. 检查 SSH 端口是否开放
telnet xxx.xxx.xxx.xxx 22

# 3. 检查服务器防火墙规则
# 如果使用 1Panel，在面板中检查防火墙设置

# 4. 检查 SSH 服务状态
# 登录服务器后执行
systemctl status sshd
```

### 认证失败

**症状**：
```
Permission denied (publickey,password).
```

**可能原因**：
1. SSH 密钥未配置
2. 密钥权限不正确
3. 用户名错误

**解决方案**：
```bash
# 1. 检查 SSH 密钥是否存在
ls -la ~/.ssh/

# 2. 检查密钥权限
chmod 600 ~/.ssh/id_rsa
chmod 700 ~/.ssh

# 3. 测试 SSH 连接
ssh -v user@xxx.xxx.xxx.xxx

# 4. 检查服务器端 SSH 配置
# /etc/ssh/sshd_config 中的 PubkeyAuthentication 和 PasswordAuthentication
```

### 密钥问题

**症状**：
```
Load key "/path/to/key": invalid format
```

**可能原因**：
1. 密钥格式不正确
2. 密钥文件损坏

**解决方案**：
```bash
# 1. 重新生成 SSH 密钥
ssh-keygen -t ed25519 -C "your_email@example.com"

# 2. 复制公钥到服务器
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@xxx.xxx.xxx.xxx

# 3. 使用 AgentPlane 管理密钥
agentplane infra secrets sync-layout --target <target> --repo-root .
```

---

## 1Panel API 问题

### API 不可达

**症状**：
```
Connection refused: http://xxx.xxx.xxx.xxx:8888/api/v1/...
```

**可能原因**：
1. 1Panel 服务未启动
2. 端口被防火墙阻止
3. API 地址配置错误

**解决方案**：
```bash
# 1. 检查 1Panel 服务状态
systemctl status 1panel

# 2. 检查端口是否开放
netstat -tlnp | grep 8888

# 3. 检查 1Panel 配置
cat /opt/1panel/conf/1panel.conf

# 4. 重启 1Panel 服务
systemctl restart 1panel
```

### 认证失败

**症状**：
```
401 Unauthorized: invalid token
```

**可能原因**：
1. API Token 过期
2. Token 配置错误

**解决方案**：
```bash
# 1. 重新生成 API Token
# 登录 1Panel 面板 -> 设置 -> API Token

# 2. 更新 AgentPlane 配置
agentplane infra secrets sync-layout --target <target> --repo-root .

# 3. 验证配置
agentplane infra health --target <target> --repo-root .
```

### 版本不兼容

**症状**：
```
API endpoint not found: /api/v2/...
```

**可能原因**：
1. 1Panel 版本过低
2. API 版本不匹配

**解决方案**：
```bash
# 1. 检查 1Panel 版本
curl http://xxx.xxx.xxx.xxx:8888/api/v1/dashboard/baseInfo

# 2. 升级 1Panel
# 参考 1Panel 官方文档

# 3. 检查 AgentPlane 支持的 1Panel 版本
# 参考 docs/conventions.md
```

---

## Docker 问题

### 容器启动失败

**症状**：
```
Error response from daemon: driver failed programming external connectivity on endpoint xxx
```

**可能原因**：
1. 端口已被占用
2. 镜像不存在
3. 权限不足

**解决方案**：
```bash
# 1. 检查端口占用
netstat -tlnp | grep <端口号>

# 2. 检查镜像是否存在
docker images | grep <镜像名>

# 3. 查看容器日志
docker logs <容器名>

# 4. 检查 Docker 权限
sudo usermod -aG docker $USER
```

### 端口冲突

**症状**：
```
Bind for 0.0.0.0:80 failed: port is already allocated
```

**解决方案**：
```bash
# 1. 查找占用端口的进程
lsof -i :80

# 2. 停止冲突的容器
docker ps | grep :80
docker stop <容器ID>

# 3. 修改端口映射
# 编辑 docker-compose.yaml，修改 ports 配置
```

### 镜像拉取失败

**症状**：
```
Error response from daemon: pull access denied for xxx
```

**可能原因**：
1. 镜像不存在
2. 私有仓库认证失败
3. 网络问题

**解决方案**：
```bash
# 1. 检查镜像名称是否正确
docker search <镜像名>

# 2. 登录私有仓库
docker login <仓库地址>

# 3. 检查网络连接
ping registry-1.docker.io

# 4. 使用镜像代理
# 配置 Docker daemon.json
```

---

## Windows/WSL 问题

### 路径问题

**症状**：
```
The system cannot find the path specified
```

**可能原因**：
1. 路径分隔符不正确
2. WSL 路径映射问题

**解决方案**：
```bash
# 1. 使用正确的路径分隔符
# Windows: C:\Users\...
# WSL: /mnt/c/Users/...

# 2. 在 WSL 中访问 Windows 文件
cd /mnt/c/Users/...

# 3. 使用 AgentPlane 的路径策略
# 参考 docs/core/architecture.md#跨平台执行模型
```

### 编码问题

**症状**：
```
UnicodeDecodeError: 'gbk' codec can't decode byte...
```

**解决方案**：
```bash
# 1. 设置环境变量
export PYTHONIOENCODING=utf-8

# 2. 在 PowerShell 中设置
$env:PYTHONIOENCODING="utf-8"

# 3. 检查文件编码
file -i <文件名>
```

### 环境变量问题

**症状**：
```
'agentplane' is not recognized as an internal or external command
```

**解决方案**：
```bash
# 1. 检查 PATH 环境变量
echo $PATH

# 2. 使用 uv run 运行
uv run agentplane --help

# 3. 使用 python -m 运行
python -m agentplane --help

# 4. 重新安装
uv tool install -e .
```

---

## 测试失败

### 测试超时

**症状**：
```
FAILED: Timeout > 300.0s
```

**解决方案**：
```bash
# 1. 增加超时时间
uv run pytest --timeout=600

# 2. 只运行快速测试
uv run agentplane test fast --tb=short

# 3. 检查网络连接
# 某些测试可能需要网络访问
```

### 测试依赖缺失

**症状**：
```
ModuleNotFoundError: No module named 'xxx'
```

**解决方案**：
```bash
# 1. 同步依赖
uv sync

# 2. 检查 pyproject.toml
# 确保依赖已声明

# 3. 重新安装
uv pip install -e .
```

### 测试环境问题

**症状**：
```
FAILED: FileNotFoundError: [Errno 2] No such file or directory
```

**解决方案**：
```bash
# 1. 检查测试数据是否存在
ls tests/fixtures/

# 2. 重新生成测试数据
uv run pytest --collect-only

# 3. 检查工作目录
pwd
```

---

## 获取帮助

如果以上方案都无法解决问题：

1. **查看日志**：
   ```bash
   # AgentPlane 日志
   uv run agentplane project health-check --repo-root .

   # Docker 日志
   docker logs <容器名>

   # 系统日志
   journalctl -u <服务名>
   ```

2. **搜索文档**：
   - [命令参考](command-reference.md)
   - [架构](core/architecture.md)
   - [编码与协作规范](conventions.md)

3. **提交 Issue**：
   - 使用 GitHub Issues 报告问题
   - 包含错误信息、环境信息、复现步骤

---

## 关联文档

- [入门指南](getting-started.md) — 快速上手
- [命令参考](command-reference.md) — 所有 CLI 命令
- [架构](core/architecture.md) — 架构设计
- [编码与协作规范](conventions.md) — 技术栈、编码规则
