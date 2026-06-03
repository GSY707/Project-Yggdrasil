# Project Memory

Instructions here apply to this project and are shared with team members.

## Context

Always update  docs\DIRECTORY_REFERENCE.md file.

必须尽可能地完成任务。除非任务受到硬性阻塞，不然直接继续做下一步，不要停下来。

及时删除已经不需要的代码与设计，这些多余东西曾经给这个项目带来了不小的灾难。

不要为了兼容旧的设计而把新设计当作旧代码上的补丁，不应该做平滑的升级，应该直接切换。过渡性的代码给这个项目带来过不小的灾难。

废旧测试应该删除，否则会带跑项目路线。

积极使用 subagent。

runSubagent 功能只有 “Auto (copilot)” 型号模型可用，其他用不了。search_subagent，execution_subagent 等 subagent 工具坏了，请用  runSubagent 代替。

本机安装了 docker desktop 有时需要手动启动，否则一些测试会挂。docker 路径："C:\Program Files\Docker\Docker\Docker Desktop.exe"

子代理如果额度受限，直接换 Auto (copilot) 模型即可使用，这个模型永远不限制。

子代理如果额度受限，直接换 Auto (copilot) 模型即可使用，这个模型永远不限制。

子代理如果额度受限，直接换 Auto (copilot) 模型即可使用，这个模型永远不限制。