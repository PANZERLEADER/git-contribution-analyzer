from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]

REQUIRED_CHINESE_DOCUMENTS = {
    "README.zh-CN.md": "# Git 贡献分析器",
    "doc/zh-CN/README.md": "# GCA 中文文档",
    "doc/zh-CN/architecture.md": "# GCA 架构",
    "doc/zh-CN/data-model.md": "# GCA 数据模型",
    "doc/zh-CN/cli-reference.md": "# GCA CLI 参考",
    "doc/zh-CN/installation.md": "# 安装、升级与卸载",
    "doc/zh-CN/methodology.md": "# 工作评估与简历生成方法论",
    "doc/zh-CN/privacy.md": "# 隐私与数据边界",
    "doc/zh-CN/provider-guide.md": "# LLM Provider 指南",
    "doc/zh-CN/golden-dataset.md": "# 黄金数据集",
    "doc/zh-CN/release-0.1.0.md": "# GCA 0.1.0 发布说明",
}

BILINGUAL_DOCUMENT_PAIRS = {
    "doc/architecture/architecture.md": "../zh-CN/architecture.md",
    "doc/architecture/data-model.md": "../zh-CN/data-model.md",
    "doc/cli/cli-reference.md": "../zh-CN/cli-reference.md",
    "doc/guides/installation.md": "../zh-CN/installation.md",
    "doc/guides/methodology.md": "../zh-CN/methodology.md",
    "doc/guides/privacy.md": "../zh-CN/privacy.md",
    "doc/guides/provider-guide.md": "../zh-CN/provider-guide.md",
    "doc/testing/golden-dataset.md": "../zh-CN/golden-dataset.md",
    "doc/releases/0.1.0.md": "../zh-CN/release-0.1.0.md",
}


def test_should_ship_required_chinese_documentation() -> None:
    missing = [path for path in REQUIRED_CHINESE_DOCUMENTS if not (ROOT / path).is_file()]

    assert missing == []

    for path, heading in REQUIRED_CHINESE_DOCUMENTS.items():
        content = (ROOT / path).read_text(encoding="utf-8")
        assert heading in content
        assert re.search(r"[\u4e00-\u9fff]", content)


def test_should_link_english_and_chinese_documentation() -> None:
    english_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    chinese_index = (ROOT / "doc/zh-CN/README.md").read_text(encoding="utf-8")

    assert "[简体中文](README.zh-CN.md)" in english_readme
    assert "[English](README.md)" in chinese_readme
    for path in REQUIRED_CHINESE_DOCUMENTS:
        if path.startswith("doc/zh-CN/") and path != "doc/zh-CN/README.md":
            assert Path(path).name in chinese_index

    for english_path, chinese_link in BILINGUAL_DOCUMENT_PAIRS.items():
        english_content = (ROOT / english_path).read_text(encoding="utf-8")
        assert f"[简体中文]({chinese_link})" in english_content
