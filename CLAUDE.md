# vibeval 项目开发指南

## 项目概述

vibeval (Vibe Coding Eval) 是一个 AI 应用评测框架，由两部分组成：
- **vibeval CLI** (`src/vibeval/`) — 评测工具（judge、compare、simulate、report 等）
- **Claude Code Plugin** (`plugin/`) — VibeCoding 工作流（analyze、design、generate、run、update）

## 核心原则

### 1. 协议为本

`plugin/skills/protocol/references/` 下的协议文档是整个项目的核心设定（Source of Truth）。所有 plugin 命令、CLI 代码、文档都必须围绕和遵循协议。当任何地方的内容与协议矛盾时，以协议为准。编写文档或命令时，避免重复协议中已有的定义，改为引用协议文件。

协议文件：
- `00-philosophy.md` — 评测哲学（信息不对称 + 全局视野）
- `01-overview.md` — 目录结构、统一 turn 模型
- `02-dataset.md` — 数据集格式
- `03-judge-spec.md` — 评判规格（rule/llm、target、所有字段定义）
- `04-result.md` — 结果格式（trace turns/steps）
- `05-comparison.md` — 横评格式

### 2. 语言无关

所有设计必须避免语言耦合。vibeval CLI 提供通用的、可通过命令行直接执行的功能，不需要在代码层面做依赖。用户的测试代码不 import vibeval 包，而是通过 subprocess 调用 CLI（如 `vibeval simulate`），或直接按协议格式生成文件。CLI 既服务开发者，也服务 VibeCoding Agent。

### 3. CLI Help 是命令文档的唯一来源

CLI 的每个命令必须保持完整、最新的 `--help` 描述（包括用途、参数说明、使用示例）。Plugin 的命令文档和 SKILL.md 中不重复 CLI 的参数细节，而是提示通过 `vibeval --help` / `vibeval <command> --help` 查看。这样 CLI 和文档永远不会不同步。

### 4. 测试目录的区分

`tests/` 目录下是 vibeval CLI 工具和代码自身的单元测试、集成测试。`examples/` 下的项目（如 `meeting_app/`）是独立的示例应用，它们有自己的测试（在 `examples/meeting_app/tests/vibeval/` 下），演示的是用户使用 vibeval 的完整流程。两者不要混淆。

## 开发约定

### 运行测试

```bash
# vibeval 自身的测试
python -m pytest tests/ -v

# 示例应用的测试（独立运行）
cd examples/meeting_app/tests/vibeval/meeting_summary/tests
python -m pytest test_summarizer.py -v

# 示例应用的 judge
cd examples/meeting_app
vibeval judge meeting_summary latest
```

### 修改协议

修改协议文件后，检查以下是否需要同步更新：
- `src/vibeval/` 中的代码实现（rules.py、llm.py、judge.py、compare.py、result.py）
- `plugin/commands/` 中的命令文档（应引用协议而非重复内容）
- `plugin/skills/protocol/SKILL.md`（Quick Reference 摘要）
- CLI 的 `--help` 描述

### 修改 CLI

新增或修改 CLI 命令时：
- 在 `cli.py` 中提供完整的 `help` 和 `description` 文本
- 不需要同步更新 plugin 文档中的命令细节——plugin 文档应引导查看 `vibeval --help`
- 添加对应的测试到 `tests/`

### 版本管理

项目版本在三处维护，必须保持一致：
- `pyproject.toml` — `version` 字段
- `plugin/.claude-plugin/plugin.json` — `version` 字段
- `src/vibeval/__init__.py` — `__version__` 变量

发版或变更版本号时，三处同时更新。

### 修改 Plugin

修改 plugin 命令或 skill 时：
- 基础概念定义（数据格式、字段、规则名等）一律引用 `references/` 中的协议文件，不内联重复
- 操作指导（如何设计、如何生成）可以在命令文档中展开，但引用协议作为定义来源
- CLI 命令的参数和用法，引导使用 `vibeval --help` 查看

### 项目结构

```
vibeval/
├── src/vibeval/            # CLI 工具实现
├── plugin/                # Claude Code 插件
│   ├── commands/           # /vibeval-analyze, /vibeval-design, /vibeval-generate, /vibeval-run, /vibeval-update
│   └── skills/protocol/    # 数据协议（Source of Truth）
├── examples/              # 独立的示例应用
├── tests/                 # vibeval 自身的测试
├── CLAUDE.md
├── README.md
└── pyproject.toml
```
