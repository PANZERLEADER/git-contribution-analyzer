from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from git_contribution_analyzer.adapters.git.pydriller_history import PyDrillerChangeReader
from git_contribution_analyzer.domain.errors import WorkspaceError
from git_contribution_analyzer.domain.models.git_history import (
    GitCommit,
    GitFileChange,
    GitIdentity,
    GitRef,
)

REVERT_PATTERN = re.compile(r"This reverts commit ([0-9a-fA-F]{7,64})\.")


class NativeGitHistory:
    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve()
        self._mailmap_cache: dict[tuple[str, str], tuple[str, str, str, bool]] = {}

    def _run(
        self,
        *arguments: str,
        input_bytes: bytes | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(
                ["git", "-C", str(self.repository_root), *arguments],
                input=input_bytes,
                check=check,
                capture_output=True,
                timeout=60,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise WorkspaceError(f"Git command failed: {' '.join(arguments)}") from exc

    def _text(self, *arguments: str) -> str:
        return self._run(*arguments).stdout.decode("utf-8", errors="replace").strip()

    def list_refs(self) -> tuple[GitRef, ...]:
        ref_format = (
            "%(refname)%00%(objecttype)%00%(objectname)%00"
            "%(*objecttype)%00%(*objectname)%1e"
        )
        raw = self._run(
            "for-each-ref",
            f"--format={ref_format}",
            "refs/heads",
            "refs/remotes/origin",
            "refs/tags",
        ).stdout
        refs: list[GitRef] = []
        for record in raw.split(b"\x1e"):
            decoded = record.strip(b"\r\n").decode("utf-8", errors="replace")
            if not decoded:
                continue
            fields = decoded.split("\x00")
            if len(fields) != 5:
                raise WorkspaceError("Unexpected batched ref format")
            name, object_type, object_hash, peeled_type, peeled_hash = fields
            if object_type == "tag":
                if peeled_type != "commit" or not peeled_hash:
                    raise WorkspaceError(f"Tag does not resolve to a commit: {name}")
                commit_hash = peeled_hash
            else:
                if object_type != "commit" or not object_hash:
                    raise WorkspaceError(f"Ref does not resolve to a commit: {name}")
                commit_hash = object_hash
            if name.startswith("refs/tags/"):
                ref_type = "TAG"
            elif name.startswith("refs/remotes/"):
                ref_type = "REMOTE"
            else:
                ref_type = "HEAD"
            refs.append(GitRef(name=name, commit_hash=commit_hash, ref_type=ref_type))
        return tuple(refs)

    def list_commit_hashes(self) -> tuple[str, ...]:
        result = self._run("rev-list", "--all", "--topo-order", "--reverse", check=False)
        if result.returncode not in (0, 128):
            raise WorkspaceError("Unable to enumerate Git commits")
        output = result.stdout.decode("ascii", errors="replace").strip()
        return tuple(output.splitlines()) if output else ()

    def reachable_commits(self, ref_name: str) -> frozenset[str]:
        return frozenset(self._rev_list(ref_name))

    def first_release_tags(self, commit_hashes: Iterable[str]) -> dict[str, str]:
        wanted = set(commit_hashes)
        if not wanted:
            return {}
        release_tags: dict[str, str] = {}
        release_times = self.release_times()
        tags = sorted(
            (git_ref.name for git_ref in self.list_refs() if git_ref.ref_type == "TAG"),
            key=lambda tag: (release_times.get(tag, datetime.max.replace(tzinfo=UTC)), tag),
        )
        for tag in tags:
            for commit_hash in self._rev_list(tag):
                if commit_hash in wanted:
                    release_tags.setdefault(commit_hash, tag)
            if len(release_tags) == len(wanted):
                break
        return release_tags

    def release_times(self) -> dict[str, datetime]:
        raw = self._run(
            "for-each-ref",
            "--format=%(refname)%00%(creatordate:iso-strict)%1e",
            "refs/tags",
        ).stdout
        result: dict[str, datetime] = {}
        for record in raw.split(b"\x1e"):
            decoded = record.strip(b"\r\n").decode("utf-8", errors="replace")
            if not decoded:
                continue
            ref_name, created_at = decoded.split("\x00", maxsplit=1)
            if created_at:
                result[ref_name] = datetime.fromisoformat(created_at)
        return result

    def integration_times(
        self, ref_name: str
    ) -> dict[str, tuple[datetime, datetime | None]]:
        graph = self._parent_graph("--all")
        mainline = self._parent_graph("--first-parent", "--reverse", ref_name)
        if not mainline:
            return {}
        metadata = self._read_metadata(tuple(mainline))
        assigned: set[str] = set()
        result: dict[str, tuple[datetime, datetime | None]] = {}
        for anchor, anchor_parents in mainline.items():
            committed_at = datetime.fromisoformat(metadata[anchor][7])
            merged_at = committed_at if len(anchor_parents) > 1 else None
            stack = [anchor]
            while stack:
                commit_hash = stack.pop()
                if commit_hash in assigned:
                    continue
                assigned.add(commit_hash)
                result[commit_hash] = (committed_at, merged_at)
                stack.extend(graph.get(commit_hash, ()))
        return result

    def _parent_graph(self, *arguments: str) -> dict[str, tuple[str, ...]]:
        raw = self._run("rev-list", "--parents", *arguments, check=False)
        if raw.returncode not in (0, 128):
            raise WorkspaceError("Unable to enumerate Git parent graph")
        graph: dict[str, tuple[str, ...]] = {}
        for line in raw.stdout.decode("ascii", errors="replace").splitlines():
            fields = line.split()
            if fields:
                graph[fields[0]] = tuple(fields[1:])
        return graph

    def _rev_list(self, ref_name: str) -> tuple[str, ...]:
        result = self._run("rev-list", ref_name, check=False)
        if result.returncode not in (0, 128):
            raise WorkspaceError(f"Unable to enumerate commits for {ref_name}")
        output = result.stdout.decode("ascii", errors="replace").strip()
        return tuple(output.splitlines()) if output else ()

    def read_commits(self, commit_hashes: Iterable[str]) -> tuple[GitCommit, ...]:
        hashes = tuple(commit_hashes)
        changes_by_commit = PyDrillerChangeReader(self.repository_root).read_changes(hashes)
        metadata = self._read_metadata(hashes)
        patch_ids = self._patch_ids(hashes)
        return tuple(
            self._build_commit(
                metadata[commit_hash],
                changes=changes_by_commit.get(commit_hash),
                patch_id=patch_ids.get(commit_hash),
            )
            for commit_hash in hashes
        )

    def read_commit(self, commit_hash: str) -> GitCommit:
        return self.read_commits((commit_hash,))[0]

    def _read_metadata(self, hashes: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
        metadata: dict[str, tuple[str, ...]] = {}
        commit_format = (
            "%H%x00%P%x00%an%x00%ae%x00%cn%x00%ce%x00%aI%x00%cI%x00"
            "%T%x00%s%x00%b%x1e"
        )
        for start in range(0, len(hashes), 200):
            batch = hashes[start : start + 200]
            raw = self._run("show", "-s", f"--format={commit_format}", *batch).stdout
            for record in raw.split(b"\x1e"):
                decoded = record.lstrip(b"\r\n").decode("utf-8", errors="replace")
                if not decoded.strip():
                    continue
                fields = tuple(decoded.split("\x00", maxsplit=10))
                if len(fields) != 11:
                    raise WorkspaceError("Unexpected batched commit metadata format")
                metadata[fields[0]] = fields
        missing = set(hashes).difference(metadata)
        if missing:
            raise WorkspaceError(f"Missing commit metadata for {len(missing)} commits")
        return metadata

    def _build_commit(
        self,
        fields: tuple[str, ...],
        *,
        changes: tuple[GitFileChange, ...] | None,
        patch_id: str | None,
    ) -> GitCommit:
        if len(fields) != 11:
            raise WorkspaceError("Unexpected commit metadata format")

        canonical_name, canonical_email, source, confirmed = self._resolve_mailmap(
            fields[2], fields[3]
        )
        body = fields[10].rstrip("\n")
        revert_match = REVERT_PATTERN.search(body)
        return GitCommit(
            hash=fields[0],
            parents=tuple(fields[1].split()) if fields[1] else (),
            author=GitIdentity(
                name=fields[2],
                email=fields[3],
                canonical_name=canonical_name,
                canonical_email=canonical_email,
                source=source,
                confirmed=confirmed,
            ),
            committer_name=fields[4],
            committer_email=fields[5],
            authored_at=datetime.fromisoformat(fields[6]),
            committed_at=datetime.fromisoformat(fields[7]),
            tree_hash=fields[8],
            subject=fields[9],
            body=body,
            patch_id=patch_id,
            changes=changes if changes is not None else self._file_changes(fields[0]),
            reverts_hash=revert_match.group(1) if revert_match else None,
        )

    def _resolve_mailmap(self, name: str, email: str) -> tuple[str, str, str, bool]:
        cache_key = (name, email.lower())
        cached = self._mailmap_cache.get(cache_key)
        if cached is not None:
            return cached
        result = self._run("check-mailmap", f"{name} <{email}>", check=False)
        if result.returncode != 0:
            resolved = (name, email.lower(), "EXACT_EMAIL", False)
            self._mailmap_cache[cache_key] = resolved
            return resolved
        mapped = result.stdout.decode("utf-8", errors="replace").strip()
        match = re.fullmatch(r"(.*) <([^>]+)>", mapped)
        if not match:
            resolved = (name, email.lower(), "EXACT_EMAIL", False)
            self._mailmap_cache[cache_key] = resolved
            return resolved
        canonical_name, canonical_email = match.group(1), match.group(2).lower()
        changed = canonical_name != name or canonical_email != email.lower()
        resolved = (
            canonical_name,
            canonical_email,
            "MAILMAP" if changed else "EXACT_EMAIL",
            changed,
        )
        self._mailmap_cache[cache_key] = resolved
        return resolved

    def _file_changes(self, commit_hash: str) -> tuple[GitFileChange, ...]:
        status_data = self._run(
            "diff-tree", "--root", "--no-commit-id", "-r", "-M", "--name-status", "-z", commit_hash
        ).stdout
        tokens = status_data.decode("utf-8", errors="replace").split("\x00")
        stats = self._numstat(commit_hash)
        changes: list[GitFileChange] = []
        index = 0
        while index < len(tokens) and tokens[index]:
            status = tokens[index]
            index += 1
            code = status[0]
            old_path: str | None
            new_path: str | None
            if code in {"R", "C"}:
                old_path, new_path = tokens[index], tokens[index + 1]
                index += 2
            else:
                path = tokens[index]
                index += 1
                old_path = None if code == "A" else path
                new_path = None if code == "D" else path
            stat_key = new_path or old_path or ""
            insertions, deletions, is_binary = stats.get(stat_key, (0, 0, False))
            changes.append(
                GitFileChange(
                    old_path=old_path,
                    new_path=new_path,
                    change_type={
                        "A": "ADD",
                        "M": "MODIFY",
                        "D": "DELETE",
                        "R": "RENAME",
                        "C": "COPY",
                    }.get(code, "MODIFY"),
                    is_binary=is_binary,
                    insertions=insertions,
                    deletions=deletions,
                )
            )
        return tuple(changes)

    def _numstat(self, commit_hash: str) -> dict[str, tuple[int, int, bool]]:
        output = self._text("diff-tree", "--root", "--no-commit-id", "-r", "--numstat", commit_hash)
        stats: dict[str, tuple[int, int, bool]] = {}
        for line in output.splitlines():
            parts = line.split("\t", maxsplit=2)
            if len(parts) != 3:
                continue
            added, deleted, path = parts
            is_binary = added == "-" or deleted == "-"
            stats[path] = (
                0 if is_binary else int(added),
                0 if is_binary else int(deleted),
                is_binary,
            )
        return stats

    def _patch_ids(self, hashes: tuple[str, ...]) -> dict[str, str]:
        patch_ids: dict[str, str] = {}
        for start in range(0, len(hashes), 100):
            batch = hashes[start : start + 100]
            diff = self._run("show", "--pretty=format:commit %H", "--binary", *batch).stdout
            result = self._run("patch-id", "--stable", input_bytes=diff, check=False)
            if result.returncode != 0:
                raise WorkspaceError("Unable to calculate stable patch IDs")
            for line in result.stdout.decode("ascii", errors="replace").splitlines():
                fields = line.split()
                if len(fields) == 2:
                    patch_ids[fields[1]] = fields[0]
        return patch_ids

    def is_ancestor(self, commit_hash: str, ref_name: str) -> bool:
        result = self._run("merge-base", "--is-ancestor", commit_hash, ref_name, check=False)
        if result.returncode not in (0, 1, 128):
            raise WorkspaceError(f"Unable to evaluate reachability for {commit_hash}")
        return result.returncode == 0

    def tags_containing(self, commit_hash: str) -> tuple[str, ...]:
        output = self._text("tag", "--contains", commit_hash)
        return tuple(f"refs/tags/{tag}" for tag in output.splitlines() if tag)
