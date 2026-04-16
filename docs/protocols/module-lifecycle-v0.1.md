# 模块生命周期协议 v0.1

- 文档状态：Draft
- 版本：v0.1
- 日期：2026-04-16

## 1. 目标

定义模块从被发现到被移除的完整生命周期，确保模块可治理、可观测、可隔离、可恢复。

## 2. 参与方

- Kernel：负责模块注册表、兼容性校验、审计与状态持久化。
- Module Host：负责加载、健康检查、错误隔离与生命周期执行。
- Operator：负责安装、启用、停用、升级、回滚等人工操作。
- Module：提供 manifest、hook、事件与健康检查实现。

## 3. 生命周期状态

- discovered：已发现 manifest，尚未校验。
- validated：manifest 校验通过。
- incompatible：兼容性校验失败。
- installed：依赖与迁移已完成，可被启用。
- disabled：已安装但未启用。
- enabling：正在启动。
- active：已启用且健康。
- degraded：已启用但部分检查失败，仍可服务。
- draining：正在优雅停机，不再接收新请求。
- quarantined：因重复失败被隔离。
- uninstalling：正在卸载。
- removed：已从系统移除。
- failed：一次生命周期操作失败。

## 4. 状态转换

- discovered -> validated
- discovered -> incompatible
- validated -> installed
- installed -> disabled
- disabled -> enabling
- enabling -> active
- enabling -> failed
- active -> degraded
- degraded -> active
- active -> draining
- degraded -> draining
- draining -> disabled
- failed -> quarantined
- disabled -> uninstalling
- uninstalling -> removed

## 5. 生命周期操作

### 5.1 Discover

- 扫描模块根目录或远程模块注册来源。
- 读取 yggdrasil.module.yaml。
- 写入 discovered 记录。

### 5.2 Validate

- 校验 manifest 结构。
- 校验版本兼容性。
- 校验依赖、hook、事件与迁移声明。
- 校验配置 schema 可解析。

### 5.3 Install

- 解析依赖。
- 执行迁移计划。
- 记录模块安装版本与配置快照。
- 进入 installed。

### 5.4 Enable

- 分配模块运行上下文。
- 执行 pre-enable hook。
- 加载代码或建立远程连接。
- 注册 hook、命令、前端贡献点与订阅关系。
- 执行健康检查。
- 成功则进入 active。

### 5.5 Disable

- 进入 draining。
- 拒绝新请求。
- 等待在途任务完成或超时终止。
- 注销 hook、路由、订阅与前端贡献点。
- 保存必要状态。
- 进入 disabled。

### 5.6 Upgrade

- 先执行 Validate。
- 比较旧新 manifest 与兼容范围。
- 执行迁移计划与回滚计划预检。
- 滚动替换或停机替换。
- 升级失败则回滚到上一个 active 版本。

### 5.7 Uninstall

- 只能从 disabled 状态进入。
- 注销安装记录。
- 可选执行降级迁移或保留数据。
- 进入 removed。

## 6. 生命周期 Hook

平台保留以下生命周期 hook 名称：

- module.install.validate
- module.install.plan-migrations
- module.enable.preflight
- module.enable.post-activate
- module.disable.pre-drain
- module.disable.post-stop
- module.upgrade.preflight
- module.health.report

详细输入输出见 [Hook 点协议 v0.1](hook-contracts-v0.1.md)。

## 7. 错误隔离

- 同一模块连续启动失败达到阈值后，进入 quarantined。
- quarantined 模块不得自动重启，除非人工解除隔离。
- 远程模块故障不得阻塞 Kernel 主流程。
- 进程内模块异常必须被 Module Host 捕获并记录，不允许直接崩溃整个主进程。

## 8. 健康检查

- active 模块必须周期性上报健康状态。
- 健康检查失败但不影响核心流程时进入 degraded。
- 健康检查失败且存在数据一致性风险时应自动进入 draining 或 quarantined。

## 9. 审计要求

以下操作必须写审计日志：

- install
- enable
- disable
- upgrade
- quarantine
- unquarantine
- uninstall

## 10. 第一版约束

- 第一版只支持安装级插拔、配置级启停、部署级隔离。
- 第一版不支持运行中热更新代码。
- 第一版不支持未签名第三方模块自动加载。