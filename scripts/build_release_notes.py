from __future__ import annotations

import argparse
from pathlib import Path


def build_release_notes(root: Path, version: str, output: Path) -> None:
    sources = (
        root / "doc" / "releases" / f"{version}.md",
        root / "doc" / "zh-CN" / f"release-{version}.md",
    )
    sections: list[str] = []
    for source in sources:
        content = source.read_text(encoding="utf-8")
        if "\ufffd" in content:
            raise ValueError(f"Release notes contain invalid Unicode replacement text: {source}")
        sections.append(content.rstrip())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n\n---\n\n".join(sections) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build UTF-8 bilingual GitHub Release notes.")
    parser.add_argument("version")
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    build_release_notes(Path(__file__).parents[1], arguments.version, arguments.output)


if __name__ == "__main__":
    main()
