# Module: evaluation-and-tests

## Responsibility

评测与测试层用于保障阶段门禁、回归稳定性和跨场景行为一致性。

## Key Files

- `packages/python-sdk/src/yggdrasil_sdk/evaluation_cli.py`
- `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/`
- `evaluation/suites/`
- `evaluation/fixtures/`
- `tests/*.py`

## Entry Points

- `corepack pnpm eval:*`（官方评测套件）
- `uv run pytest -q`（回归测试）

## Data Flow

suite 配置 + fixture -> evaluation runtime 执行 -> 评分聚合 -> 结果输出与归档。

## Important Types / Classes / Functions

- `evaluation_cli.main()`
- `run_evaluation_suite`
- `list_evaluation_suite_definitions`
- 各 suite case 执行器（`suite_cases_g4.py`、`suite_cases_part_a.py`、`suite_cases_part_b.py`）

## Common Change Scenarios

- 新增 suite：在 `evaluation/suites/` 定义并接入 evaluation runtime。
- 调整评分：修改 scorer 或 case 汇总逻辑并回归历史基线。
- 调整测试样本：同步维护 fixture 与断言口径。

## Tests

- `tests/test_g2_regression.py`
- `tests/test_g4_multiscene.py`
- `tests/test_m8_runtime.py`
- `tests/test_m9_acceptance.py`

## Risks

- 指标定义漂移会造成“看似通过但不可比”。
- live 套件受 provider 与密钥条件限制，需区分离线与在线结果解释。

## Related Docs

- `docs/development/build-and-test.md`
- `docs/development/large-file-policy.md`
