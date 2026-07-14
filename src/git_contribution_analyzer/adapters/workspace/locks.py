from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import portalocker

from git_contribution_analyzer.domain.errors import WorkspaceError


@contextmanager
def workspace_lock(lock_path: Path, timeout: float = 5.0) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with portalocker.Lock(str(lock_path), mode="a+", timeout=timeout):
            yield
    except portalocker.exceptions.LockException as exc:
        raise WorkspaceError(f"Workspace is locked: {lock_path}") from exc


def can_acquire_lock(lock_path: Path) -> bool:
    try:
        with workspace_lock(lock_path, timeout=0.05):
            return True
    except WorkspaceError:
        return False
