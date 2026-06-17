# 模型 TPS 实测（2026-06-14）

## 目的

对当前项目已接入且本机已配置可用的 3 个模型做同题 live 吞吐测速：

- `longcat / LongCat-2.0-Preview`
- `deepseek_direct / deepseek-v4-flash`
- `deepseek_direct / deepseek-v4-pro`

## 测试口径

- 调用入口：`adapters/model-providers/src/yggdrasil_model_providers/gateway.py` 的真实 `invoke_model`
- 环境来源：工作区根目录 `.env`
- 提示词：固定使用一份长文 greenfield delivery plan 题面
- 工具调用：关闭
- `temperature=0.1`
- `max_tokens=1400`
- 每个模型连续跑 `3` 次
- 结果全部是 live 调用，无 fallback
- 3 个模型都打满了 `1400 output tokens`，`finishReason=length`

## 指标定义

- `firstTokenLatencyMs`：首 token 延迟
- `wallSeconds`：单次请求总耗时
- `endToEndTps`：`outputTokens / wallSeconds`
- `decodeTps`：`outputTokens / (wallSeconds - firstTokenLatencyMs)`

说明：这里的 `decodeTps` 更接近“首 token 出来之后的持续生成速度”，`endToEndTps` 则包含首 token 等待时间，更适合看真实用户体感。

## 结果汇总

| 模型 | 首 token 均值 | 总耗时均值 | 端到端 TPS 均值 | 首 token 后 TPS 均值 |
| --- | ---: | ---: | ---: | ---: |
| `LongCat-2.0-Preview` | `1235.48 ms` | `32.72 s` | `42.80` | `44.48` |
| `deepseek-v4-flash` | `766.29 ms` | `18.25 s` | `76.72` | `80.08` |
| `deepseek-v4-pro` | `971.09 ms` | `20.70 s` | `67.65` | `70.99` |

## 单次明细

### `LongCat-2.0-Preview`

| Trial | 首 token | 总耗时 | output tokens | 端到端 TPS | 首 token 后 TPS |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `1362.45 ms` | `32.727 s` | `1400` | `42.78` | `44.64` |
| 2 | `1090.03 ms` | `33.150 s` | `1400` | `42.23` | `43.67` |
| 3 | `1253.97 ms` | `32.271 s` | `1400` | `43.38` | `45.14` |

### `deepseek-v4-flash`

| Trial | 首 token | 总耗时 | output tokens | 端到端 TPS | 首 token 后 TPS |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `951.26 ms` | `18.349 s` | `1400` | `76.30` | `80.47` |
| 2 | `725.41 ms` | `18.093 s` | `1400` | `77.38` | `80.61` |
| 3 | `622.19 ms` | `18.307 s` | `1400` | `76.47` | `79.17` |

### `deepseek-v4-pro`

| Trial | 首 token | 总耗时 | output tokens | 端到端 TPS | 首 token 后 TPS |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `973.49 ms` | `21.097 s` | `1400` | `66.36` | `69.57` |
| 2 | `1010.09 ms` | `20.740 s` | `1400` | `67.50` | `70.96` |
| 3 | `929.69 ms` | `20.259 s` | `1400` | `69.10` | `72.43` |

## 结论

按本次固定口径，速度排序很清楚：

1. `deepseek-v4-flash`
2. `deepseek-v4-pro`
3. `LongCat-2.0-Preview`

如果只看本轮均值：

- `deepseek-v4-flash` 的端到端吞吐约是 `LongCat-2.0-Preview` 的 `1.79x`
- `deepseek-v4-pro` 的端到端吞吐约是 `LongCat-2.0-Preview` 的 `1.58x`
- `deepseek-v4-flash` 比 `deepseek-v4-pro` 端到端快约 `13.4%`

## 限制

- 本次是单机、串行、单题面、单输出上限实测，不代表所有任务形态下都保持相同比例
- 因为 3 个模型都撞到 `max_tokens=1400` 上限，所以这是“长输出连续生成”场景下的速度对比，不是开放式自然收口任务的完整画像
- DeepSeek 与 LongCat 的 token 统计口径来自各自 provider 响应，经项目统一归一化后再计算，适合做本项目内部横向比较

## 原始数据

- 原始 JSON：`tmp/benchmarks/model_tps_2026_06_14.json`
