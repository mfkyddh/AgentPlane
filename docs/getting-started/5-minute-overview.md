---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: human
---

# 🧭 5 分钟了解 AgentPlane

结论：AgentPlane 是一套让 AI 安全接管基础设施的"遥控器"系统。你下指令，AI 执行，全程有计划、有验证、有记录。

---

## AgentPlane 解决什么问题？

**传统方式的问题**：

AI 直接执行原始命令操作服务器——相当于让一个没有安全护栏的机器人直接操作生产线：
- 没有前置检查：SSH 连不上？容器不存在？失败了才知道
- 没有错误处理：命令报错后怎么恢复？全靠人工解读
- 没有审计记录：谁执行了什么？什么时候？查不到
- 没有状态验证：操作做完了，服务真的正常了吗？不知道

**AgentPlane 的方式**：

所有操作通过 `agentplane ...` 标准化入口执行，每个入口自动完成：

```
检查依赖 → 执行操作 → 验证结果 → 留下记录
```

---

## 三个核心概念（类比理解）

### 1️⃣ 配置中心 vs 现场状态

- **配置中心**：Git 里的文件定义"我们希望系统是什么样"——这是权威定义
- **现场状态**：服务器上实际运行的容器和服务——这是验证基准
- AgentPlane 的工作就是**持续对比两者**，发现不一致时及时报告

> 💡 为什么不用现场状态当权威？因为现场状态今天对、明天可能就被手动改乱了。Git 里的配置可以回滚到任意历史版本。

### 2️⃣ 标准化入口

AI 不直接执行 `ssh ... docker restart`，而是走标准化命令：

```bash
agentplane service apply --target prod --name myapp --execute
```

这个命令内部会自动：检查主机在线、选择正确的执行后端、执行操作、验证健康状态、写入操作记录。

### 3️⃣ 执行闭环

任何影响正式状态的操作，必须走完 6 步：

```
Plan（预览）→ Apply（执行）→ Verify（验证）
→ 记录（机器证据）→ 刷新状态台账 → 同步文档摘要
```

> 💡 高风险操作（如部署到生产环境）必须先预览再执行，且执行后必须验证。

---

## 下一步

- **想深入理解概念？** → [核心概念详解](core-concepts.md)
- **想上手操作？** → [应用交付流程](../runbooks/app-project-delivery-workflow.md)
- **想了解 AI 怎么工作？** → [AI 执行流程](how-agent-works.md)
- **想知道当前状态？** → [状态与验证](../runbooks/current-state-and-validation.md)
