# 领域文档

本文件说明工程技能在探索代码库时应如何使用本仓库的领域文档。

## 探索前阅读

- 阅读仓库根目录的 `CONTEXT.md`。
- 如果根目录存在 `CONTEXT-MAP.md`，则按照其中的映射读取与当前任务相关的各个 `CONTEXT.md`。
- 阅读 `docs/adr/` 中与当前工作区域相关的 ADR。对于 multi-context 仓库，还应检查 `src/<context>/docs/adr/` 中各上下文自己的决策记录。

如果上述文件或目录不存在，继续执行任务即可，不要报告缺失，也不要提前建议创建。生产者技能 `/grill-with-docs` 会在领域术语或架构决策实际明确后按需创建它们。

## 文件布局

本仓库采用 single-context 布局：

```text
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

如果未来改为 multi-context 布局，应在根目录创建 `CONTEXT-MAP.md`，并由它指向各上下文的 `CONTEXT.md`：

```text
/
├── CONTEXT-MAP.md
├── docs/adr/
└── src/
    ├── <context-a>/
    │   ├── CONTEXT.md
    │   └── docs/adr/
    └── <context-b>/
        ├── CONTEXT.md
        └── docs/adr/
```

## 使用 glossary 中的词汇

当输出内容需要命名领域概念时，例如 Issue 标题、重构提案、诊断假设或测试名称，应使用 `CONTEXT.md` 中定义的术语，不要改用 glossary 明确避免的同义词。

如果所需概念尚未出现在 glossary 中，应先判断是否正在引入项目未使用的语言；如果确实存在领域知识缺口，则记录下来，交由 `/grill-with-docs` 处理。

## 标明与 ADR 的冲突

如果输出内容与现有 ADR 冲突，应明确指出冲突，不要静默覆盖已有决策。
