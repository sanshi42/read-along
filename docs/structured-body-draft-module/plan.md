# 结构化正文 Draft Module Plan

## 实现方案

- 让 `ReadingMaterialDraftParagraph` 不再接收 `text` 字段，而是通过 `sentences` 派生只读 `text` 属性。
- 更新导入器和测试 helper，使 Draft 构造只传 `sentences` 和可选 `source_label`。
- 删除材料库保存前的段落正文同步校验，因为该不变量已经移入 Draft Interface。
- 保持保存结果不变：段落表仍写入派生出的 `paragraph.text`，句子表仍按原顺序写入。

## 关键决策

- 本次不把 Draft 拆成更多文件；先把不变量放回已有模型，避免引入没有第二个 Adapter 的新 seam。
- `content_hash` 仍只由句子序列决定，避免正文派生方式改变重复判断。
- `text` 保留为只读属性，继续支持材料库持久化和测试断言读取段落正文。

## Topic 级验证

- 运行 Draft 模型、导入器和材料库相关 pytest。
- 运行 `make check`。
