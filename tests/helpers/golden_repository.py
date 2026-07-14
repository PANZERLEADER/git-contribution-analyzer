from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tests.helpers.git_repo_builder import GitRepoBuilder


@dataclass(frozen=True)
class GoldenRepository:
    path: Path
    alice_name: str = "Alice"
    alice_email: str = "alice@example.com"
    bob_name: str = "Bob"
    bob_email: str = "bob@example.com"


def build_dual_track_golden_repository(path: Path) -> GoldenRepository:
    fixture = GoldenRepository(path=path)
    builder = GitRepoBuilder.create(path)
    builder.commit_text("README.md", "# Golden repository\n", "chore: initialize fixture")

    builder.checkout("feature/alice-user", create=True)
    builder.commit_text(
        "api/user.py",
        "def create_user():\n    return {'created': True}\n",
        "feat(user): add user API PROJ-1",
        name=fixture.alice_name,
        email=fixture.alice_email,
    )
    builder.commit_text(
        "tests/test_user.py",
        "def test_create_user():\n    assert True\n",
        "test(user): cover user API PROJ-1",
        name=fixture.alice_name,
        email=fixture.alice_email,
    )
    builder.commit_text(
        "docs/user-api.md",
        "# User API\n\nCreates a user.\n",
        "docs(user): document user API PROJ-1",
        name=fixture.alice_name,
        email=fixture.alice_email,
    )
    builder.checkout("main")
    builder.merge("feature/alice-user", "merge: deliver user API PROJ-1")

    builder.commit_text(
        "service/bob.py",
        "def independent_work():\n    return True\n",
        "feat(bob): add independent workflow PROJ-2",
        name=fixture.bob_name,
        email=fixture.bob_email,
    )

    builder.checkout("feature/alice-pending", create=True)
    builder.commit_text(
        "api/pending.py",
        "PENDING = True\n",
        "feat(pending): draft endpoint PROJ-3",
        name=fixture.alice_name,
        email=fixture.alice_email,
    )
    builder.checkout("main")

    builder.checkout("feature/alice-duplicate", create=True)
    duplicate = builder.commit_text(
        "service/idempotency.py",
        "IDEMPOTENCY_KEY = 'request-id'\n",
        "fix(payment): add idempotency guard PROJ-4",
        name=fixture.alice_name,
        email=fixture.alice_email,
    )
    builder.checkout("main")
    builder.cherry_pick(duplicate)

    reverted = builder.commit_text(
        "service/payment_limit.py",
        "PAYMENT_LIMIT = 100\n",
        "fix(payment): adjust payment limit PROJ-5",
        name=fixture.alice_name,
        email=fixture.alice_email,
    )
    builder.revert(reverted)

    builder.commit_text(
        "db/migrations/V002__payment_transaction.sql",
        "BEGIN;\nALTER TABLE payment ADD COLUMN request_id VARCHAR(64);\nCOMMIT;\n",
        "feat(payment): add transaction migration PROJ-6",
        name=fixture.alice_name,
        email=fixture.alice_email,
    )
    builder.commit_text(
        "docs/operations.md",
        "# Operations\n" + "routine documentation line\n" * 500,
        "docs(ops): expand operating guide PROJ-7",
        name=fixture.alice_name,
        email=fixture.alice_email,
    )

    builder.commit_text(
        "generated/client.py",
        "# generated\nCLIENT = True\n",
        "build: refresh generated client",
    )
    builder.commit_text(
        "uv.lock",
        "version = 1\n",
        "build: update lockfile",
    )
    builder.commit_binary("assets/logo.bin", b"\x00\x01\x02\xff", "build: add binary asset")
    builder.tag("v1.0.0")
    return fixture
