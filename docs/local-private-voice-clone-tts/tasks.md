# 本地私有声音克隆 TTS Tasks

## T001：建立可复现评测夹具

- Goal：在 `/private/tmp/read-along-tts-evaluation` 准备固定输入、共享 manifest、指标脚本、假 runner 和匿名样本布局，不向主应用加入模型依赖。
- Depends on：无。
- Verification：参考 WAV 与逐字稿哈希和格式符合契约；十句语料覆盖项完整；假 runner 验证 RTF、CER、失败记录及匿名映射。
- Status：Done。

## T002：实测 CosyVoice3

- Goal：在 `/private/tmp/read-along-tts-evaluation/cosyvoice3` 的 Python 3.10 隔离环境运行 `Fun-CosyVoice3-0.5B-2512` 声音克隆，生成统一样本并记录兼容性、质量、性能和稳定性数据。
- Depends on：T001。
- Verification：完成全部评测语料、SenseVoice 回转录、性能测量和至少 20 句连续生成。
- Status：In Progress。
- Claimed by：`/root`。

## T003：实测 Qwen3-TTS

- Goal：在 `/private/tmp/read-along-tts-evaluation/qwen3_tts` 的 Python 3.12 隔离环境运行 `Qwen3-TTS-12Hz-0.6B` Base 声音克隆，生成统一样本并记录兼容性、质量、性能和稳定性数据。
- Depends on：T001。
- Verification：完成全部评测语料、SenseVoice 回转录、性能测量和至少 20 句连续生成。
- Status：Pending。

## T004：准备匿名 A/B 盲测

- Goal：汇总两个模型的自动结果，筛除不合格候选，并为两个有效候选生成匿名随机 A/B 材料，或为唯一有效候选生成匿名接受度听测材料。
- Depends on：T002、T003。
- Verification：自动结果字段完整；匿名样本无法从名称识别模型；存在两个有效候选时，随机映射可在评分后揭示。
- Status：Pending。

## T005：形成胜出决策

- Goal：结合运行门槛、可靠性、错读结果和用户盲测，确定胜出模型或确认两者均不合格，并把结论写入 Topic 关键决策。
- Depends on：T004。
- Verification：每项淘汰和胜出规则都有对应证据；用户确认盲测、接受度听测或无有效候选的评测结论。
- Status：Pending。

## T006：落实 sidecar 决策

- Goal：若存在胜者，为胜出模型实现 localhost sidecar、单一全局声音档案和运行说明；若无胜者，记录不实施结论并保持产品运行路径不变。
- Depends on：T005。
- Verification：有胜者时覆盖健康检查、WAV 合成、声音档案摘要校验和仅绑定 `127.0.0.1`；无胜者时确认没有引入模型运行依赖。
- Status：Pending。

## T007：接入 Read Along 朗读引擎

- Goal：若存在胜者，新增 `local_clone_tts` 配置与适配器，并实现完整缓存指纹、离线缓存复用、可恢复失败和禁止自动降级；若无胜者，确认无需应用改动。
- Depends on：T006。
- Verification：有胜者时单元和集成测试覆盖配置、请求映射、缓存及错误路径；无胜者时检查主应用与默认后端未改变。
- Status：Pending。

## T008：完成 Topic 验收

- Goal：补充最终决策和运行文档，完成目标机器验证与项目级自动检查。
- Depends on：T007。
- Verification：按评测结果完成 `plan.md` 中适用的 Topic 级验证，并运行 `make check`。
- Status：Pending。
