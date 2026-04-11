## 背景

WSL Redis 容器 `redis7-dev` 当前启用了密码认证，但运行密码为弱口令 `ruoyi123`。运行中的依赖容器 `newapi-dev` 通过 `secrets/services/newapi.wsl.env` 中的 `REDIS_CONN_STRING` 与 `REDIS_URL` 连接该 Redis。

## 目标

- 保留现有 Redis 数据
- 将 WSL Redis 运行密码轮换为强随机值
- 同步更新 WSL 中依赖 `redis7-dev` 的运行配置
- 重启 Redis 与依赖容器并验证恢复健康

## 方案

1. 生成不含 URL 特殊字符的 32 位十六进制随机密码
2. 更新 `secrets/services/redis.conf` 中的 `requirepass`
3. 更新 `secrets/services/newapi.wsl.env` 中的 `REDIS_CONN_STRING` 与 `REDIS_URL`
4. 重建 `redis7-dev`
5. 重建 `newapi-dev`
6. 验证未认证访问被拒绝、带新密码认证成功、`newapi-dev` 恢复健康

## 风险

- 仍使用旧密码的客户端会立即失效
- 这次只同步当前确认运行中的 WSL 依赖 `newapi-dev`
