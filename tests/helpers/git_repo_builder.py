from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path


class GitRepoBuilder:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._next_date = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    @classmethod
    def create(cls, root: Path) -> GitRepoBuilder:
        root.mkdir(parents=True)
        subprocess.run(
            ["git", "init", "-b", "main", str(root)],
            check=True,
            capture_output=True,
            text=True,
        )
        builder = cls(root)
        builder.run("config", "user.name", "Test User")
        builder.run("config", "user.email", "test@example.com")
        return builder

    def run(self, *arguments: str, env: dict[str, str] | None = None) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        return result.stdout.strip()

    def commit_text(
        self,
        path: str,
        content: str,
        message: str,
        *,
        name: str = "Test User",
        email: str = "test@example.com",
    ) -> str:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.run("add", path)
        return self._commit(message, name=name, email=email)

    def commit_binary(self, path: str, content: bytes, message: str) -> str:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        self.run("add", path)
        return self._commit(message)

    def rename(self, old_path: str, new_path: str, message: str) -> str:
        (self.root / new_path).parent.mkdir(parents=True, exist_ok=True)
        self.run("mv", old_path, new_path)
        return self._commit(message)

    def _commit(
        self,
        message: str,
        *,
        name: str = "Test User",
        email: str = "test@example.com",
    ) -> str:
        date = self._next_date.isoformat()
        self._next_date += timedelta(minutes=1)
        env = os.environ.copy()
        env.update(
            {
                "GIT_AUTHOR_NAME": name,
                "GIT_AUTHOR_EMAIL": email,
                "GIT_AUTHOR_DATE": date,
                "GIT_COMMITTER_NAME": name,
                "GIT_COMMITTER_EMAIL": email,
                "GIT_COMMITTER_DATE": date,
            }
        )
        self.run("commit", "-m", message, env=env)
        return self.run("rev-parse", "HEAD")

    def checkout(self, branch: str, *, create: bool = False) -> None:
        arguments = ("checkout", "-b", branch) if create else ("checkout", branch)
        self.run(*arguments)

    def tag(self, name: str) -> None:
        self.run("tag", name)

    def cherry_pick(self, commit_hash: str) -> str:
        self.run("cherry-pick", commit_hash)
        return self.run("rev-parse", "HEAD")

    def merge(self, branch: str, message: str) -> str:
        self.run("merge", "--no-ff", branch, "-m", message)
        return self.run("rev-parse", "HEAD")

    def revert(self, commit_hash: str) -> str:
        self.run("revert", "--no-edit", commit_hash)
        return self.run("rev-parse", "HEAD")

    def reset_hard(self, commit_hash: str) -> None:
        self.run("reset", "--hard", commit_hash)
