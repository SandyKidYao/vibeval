# vibeval Protocol — Overview

vibeval Data Protocol v0.2

vibeval 测试按**功能模块**组织，每个模块包含两类数据：

- **Dataset** — 测试的输入，包含合成数据和评判标准
- **Result** — 测试的产出，包含 trace（过程记录）和评估结果

## 统一模型

所有测试都是 N 轮（turn）的交互。单轮测试是 turns=1 的特例。
每轮固定结构：**input → steps[] → output**。

## 目录结构

```
tests/vibeval/
├── {feature_name}/                # 按功能模块组织
│   ├── analysis/                  # /vibeval-analyze 产物（可选）
│   │   └── ...
│   ├── design/                    # /vibeval-design 产物（可选）
│   │   └── ...
│   ├── datasets/                  # 合成测试数据 + 评判标准
│   │   └── {dataset_name}/
│   │       ├── manifest.yaml
│   │       └── *.json | *.yaml
│   ├── results/                   # 测试运行产出
│   │   └── {run_id}/
│   │       ├── summary.json
│   │       └── {test}__{item}.result.json
│   ├── comparisons/               # 横评结果
│   │   └── {run_a}_vs_{run_b}.json
│   └── tests/                     # 测试代码（VibeCoding 生成）
│       ├── conftest.py
│       └── test_*.py
```

每个 feature 目录是自包含的。

## 数据流

```
VibeCoding → datasets/ + tests/
           → 运行测试 → results/{run_id}/*.result.json
           → vibeval judge {feature} {run_id}  → 评估
           → vibeval compare {feature} run_a run_b → 横评
```
