# Project Memory

Instructions here apply to this project and are shared with team members.

## Context

本项目所有设计都是服务于 LLM 的，设计和实现要以 LLM 为核心。

Always update  docs\DIRECTORY_REFERENCE.md file.

必须尽可能地完成任务。除非任务受到硬性阻塞，不然直接继续做下一步，不要停下来。

及时删除已经不需要的代码与设计，这些多余东西曾经给这个项目带来了不小的灾难。

不要为了兼容旧的设计而把新设计当作旧代码上的补丁，不应该做平滑的升级，应该直接切换。过渡性的代码给这个项目带来过不小的灾难。

废旧测试应该删除，否则会带跑项目路线。

本机安装了 docker desktop 有时需要手动启动，否则一些测试会挂。docker 路径："C:\Program Files\Docker\Docker\Docker Desktop.exe"

如果你对我的表述方式/文档有不理解的，应该询问，不能略过或简单总结。多问用户，你说的是不是xxx，为什么xxx。

报告你的担忧，报告不确定的地方以及潜在的问题。