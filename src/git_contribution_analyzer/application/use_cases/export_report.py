from __future__ import annotations

import os
import tempfile
from pathlib import Path

from git_contribution_analyzer.application.use_cases.generate_report import generate_report


def export_report(
    path: Path,
    run_id: str,
    report_format: str,
    target: Path,
    *,
    include_email: bool = False,
    overwrite: bool = False,
) -> Path:
    resolved = target.expanduser().resolve()
    if resolved.exists() and not overwrite:
        raise FileExistsError(f"Report already exists: {resolved}")
    rendered = generate_report(
        path,
        run_id,
        report_format,
        include_email=include_email,
    )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=resolved.parent,
            prefix=f".{resolved.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(rendered)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, resolved)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return resolved
