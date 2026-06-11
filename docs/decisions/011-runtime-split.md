---
status: active
owner: AgentPlane maintainers
last_verified: 2026-06-11
date: 2026-06-11
---

# 011. 运行时拆分：核心逻辑与 Provider 解耦

## 背景

当前 AgentPlane 的核心逻辑（domain 层）与 Provider 实现（1Panel）存在耦合。虽然已通过 ProviderProtocol 定义了接口，但部分核心逻辑仍直接依赖 Provider 特定的实现细节。

## 决策

将运行时拆分为两层：

### 1. 核心逻辑层（domain/）

- 不依赖任何 Provider 特定实现
- 通过 ProviderProtocol 接口与 Provider 交互
- 所有业务逻辑在此层实现

### 2. Provider 实现层（providers/）

- 实现 ProviderProtocol 接口
- 封装特定 Provider 的 API 调用
- 可独立替换

### 3. 接口定义

```python
class ProviderProtocol(Protocol):
    # 核心接口（≤15 方法）
    def get_target(self, target: str) -> ProviderTarget: ...
    def refresh_ledgers(self, repo_root: Path, target: str, *, write: bool) -> dict: ...
    def search_websites(self, tgt: ProviderTarget, *, name: str) -> dict: ...
    def get_website(self, tgt: ProviderTarget, *, website_id: int) -> dict: ...
    def search_installed_apps(self, tgt: ProviderTarget, *, name: str) -> dict: ...
    def get_dashboard(self, tgt: ProviderTarget) -> dict: ...
    # ... 其他方法
```

## 理由

1. **可替换性**：核心逻辑不依赖特定 Provider，可随时切换
2. **可测试性**：核心逻辑可用 StubProvider 测试，不依赖真实 Provider
3. **可维护性**：Provider 实现变更不影响核心逻辑
4. **符合原则**：遵循"可替换 > 深耦合"技术方向

## 实施计划

### Phase 1: 接口定义（已完成）

- [x] 定义 ProviderProtocol（13 方法）
- [x] 实现 StubProvider
- [x] 实现 OnePanelAdapter
- [x] 契约测试覆盖

### Phase 2: 核心逻辑迁移（已完成）

- [x] 迁移 domain/app/ 到 ProviderProtocol
- [x] 迁移 domain/service/ 到 ProviderProtocol
- [x] 迁移 domain/ingress/ 到 ProviderProtocol
- [x] 迁移 domain/infra/ 到 ProviderProtocol

### Phase 3: Provider 隔离（已完成）

- [x] 移除 domain/ 对 default_provider_gateway 的直接依赖
- [x] 统一通过 get_provider() 获取 Provider 实例
- [x] 验证所有 domain/ 代码不 import provider 特定模块

### Phase 4: 第二 Provider 实现（待开始）

- [ ] 实现 DockerComposeProvider（不依赖 1Panel）
- [ ] 验证同一操作在两个 Provider 上结果一致
- [ ] 更新文档

## 已知限制（已解决）

以下模块已通过子协议模式迁移：

1. **domain/infra/health.py** — 现在使用 HealthProviderProtocol
2. **domain/ingress/handlers.py** — 现在使用 InfraOpsProviderProtocol

子协议设计允许 Provider 按需实现扩展能力，不强制所有 Provider 支持所有功能。

## 替代方案

| 方案 | 为什么放弃 |
|------|-----------|
| 保持现状 | 耦合度高，替换 Provider 需要修改核心代码 |
| 全面重写 | 成本高，风险大 |
| 引入 DI 框架 | 过度工程，单人团队无法维护 |

## 影响

- 所有 domain/ 代码需要审查和迁移
- 需要更新测试以使用 StubProvider
- 需要更新文档
- 第二 Provider 实现需要额外开发时间

## 关联文档

- [技术方向声明](010-technical-direction.md)
- [架构](../core/architecture.md)
- [ProviderProtocol 定义](../../agentplane/providers/protocol.py)
