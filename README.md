# vibeval — Vibe Coding Eval

AI 应用的快速评测框架。只需安装 Claude Code，即可完成从代码分析、测试生成到评估的全闭环。

## 解决什么问题

传统软件测试框架无法评估 AI 输出的质量；传统 AI 评测平台依赖数据集构建，跟不上功能迭代速度。vibeval 在两者之间取得平衡：

- 通过 VibeCoding 分析你的代码，快速生成合成数据和测试用例
- 确定性规则 + LLM 语义评判，双重评估
- 跨版本横评，追踪质量变化
- 语言无关：生成的测试代码适配你的项目框架，不依赖 vibeval 包

## 前置要求

- [Claude Code](https://claude.ai/code)
- Python 3.10+

## 安装

```bash
# 安装 vibeval CLI
pip install vibeval

# 安装 Claude Code 插件（在 Claude Code 中执行）
/install-plugin /path/to/vibeval/plugin
```

## 使用方式

在 Claude Code 中执行，全程不需要离开对话：

```
/vibeval-analyze  →  /vibeval-design  →  /vibeval-generate  →  /vibeval-run
                                                      ↑
                          代码变更 → /vibeval-update ──────┘
```

### 分析代码

```
/vibeval-analyze meeting_summary src/services/
```

分析源码，识别 AI 调用点、数据流、Mock 点，给出可评估性改进建议。

### 设计测试

```
/vibeval-design meeting_summary
```

设计合成数据规格、评判标准、测试结构。每一步产出可编辑的中间文件，可以 review 和修改。

### 生成代码和数据

```
/vibeval-generate meeting_summary
```

生成完整的测试套件（合成数据 + 测试代码），使用你项目的测试框架（pytest/vitest/jest/...）。

### 运行 + 评估

```
/vibeval-run meeting_summary
```

一步完成：执行测试 → 评估 → 诊断分析 → 生成报告。

### 代码变更后更新

```
/vibeval-update meeting_summary
```

检测代码变更，增量更新测试套件和数据。

### 跨版本对比

```bash
# 统计对比
vibeval diff meeting_summary run_a run_b

# LLM 深度横评
vibeval compare meeting_summary run_a run_b
```

### 可视化报告

```bash
vibeval report meeting_summary latest --open
```

生成自包含的 HTML 报告，涵盖测试设计、数据、过程 trace 和评判结果。

### 更多命令

```bash
vibeval --help
```

## License

MIT
