# Module: adapters-and-providers

## Responsibility

`adapters/*` 负责对外部模型与媒体提供方进行统一接入，屏蔽不同供应商接口差异。

## Key Files

- `adapters/model-providers/src/yggdrasil_model_providers/gateway.py`
- `adapters/media-providers/src/yggdrasil_media_providers/` 下对应 provider 实现
- `adapters/*/pyproject.toml`

## Entry Points

- provider gateway（模型候选、优先级、上下文窗口、成本参数）
- runtime 对 adapter 的调用封装（通过 SDK）

## Data Flow

runtime 请求 -> adapter 选择 provider/model -> 组装请求 -> 调用外部 API -> 归一化响应 -> 回传 runtime。

## Important Types / Classes / Functions

- `ProviderConfig`
- `PROVIDER_PROFILES`（provider 能力与成本配置）
- `_canonical_model_name`（模型别名标准化）
- `_provider_model_profile`、`_provider_catalog_entries`（候选解析与目录生成）

## Common Change Scenarios

- 新增 provider：补 profile、鉴权环境变量、请求映射。
- 调整模型策略：修改默认模型、优先级、质量/成本参数。
- 支持新参数：扩展 request payload 映射与响应解析。

## Tests

- `tests/test_deepseek_gateway.py`
- `tests/test_text_memory_and_adapters.py`

## Risks

- provider 配置错误会在 live 评测才暴露。
- 别名映射变更可能造成历史 suite 行为偏移。

## Related Docs

- `docs/development/build-and-test.md`
- `docs/development/large-file-inventory.md`
