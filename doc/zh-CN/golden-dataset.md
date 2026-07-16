# 黄金数据集

[中文文档索引](README.md) | [English](../testing/golden-dataset.md)

## 目的

黄金仓库在测试运行时通过真实 Git 命令生成。它固定交付状态分类、重复抑制、难度反例、隐私和
run/report 重放的行为契约，同时避免复制任何私有仓库源码。

## 场景

`tests/helpers/golden_repository.py` 会创建：

1. Alice 已合并到 `main` 的功能、测试和文档。
2. Alice 只存在于作者分支的功能。
3. Bob 独立完成并落地的功能。
4. Merge commit。
5. Cherry-pick 产生的重复 patch。
6. 一个提交及其后续 revert。
7. 预期判定为高风险的小型数据库迁移。
8. 预期保持低难度的大型纯文档变更。
9. Generated 内容、二进制文件和 lockfile。
10. Release tag 和目标分支。

仓库路径包含空格和中文字符，用于验证 Windows 和跨平台路径处理。

## 生命周期

`tests/e2e/test_dual_track_golden_lifecycle.py` 执行：

```text
init -> identities map -> analyze --no-llm
     -> assess --person --no-llm -> assess --all --no-llm
     -> resume --person --no-llm
     -> resume with mock provider and verified outcomes
     -> runs list/show -> report markdown/json
```

断言关注稳定行为契约，不依赖随机 UUID 或时间戳。新的规则版本如有意改变黄金结果，必须在同一
变更中更新测试和本文档，并在 `CHANGELOG.md` 说明原因。

结构 baseline 测试还会锁定排他 cutoff、duplicate/merge/generated/binary 排除、context-cap gap、
低频 occurrence 保留、hub-aware coupling、增量 sync、status/show/prune Schema，以及发布前取消。
Calibration/holdout fixture 目前是刻意留空的模板，不能作为启用 difficulty 新规则的黄金证据。

## 私有参考仓库

大型私有仓库可以用于性能和规则校准，但仓库中只能提交匿名计数、耗时和文件大小。源码、邮箱、
凭据和原始报告必须保留在本项目之外。
