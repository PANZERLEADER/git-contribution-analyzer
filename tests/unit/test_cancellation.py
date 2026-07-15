from __future__ import annotations

import pytest

from git_contribution_analyzer.application.ports.cancellation import (
    CancellationSource,
    NeverCancelledToken,
    OperationCancelled,
)


def test_default_token_should_never_cancel() -> None:
    token = NeverCancelledToken()

    assert token.cancellation_requested is False
    token.raise_if_cancelled()


def test_source_should_raise_after_cancel_request() -> None:
    source = CancellationSource()

    source.cancel()

    assert source.token.cancellation_requested is True
    with pytest.raises(OperationCancelled):
        source.token.raise_if_cancelled()


def test_cancel_should_be_idempotent() -> None:
    source = CancellationSource()

    source.cancel()
    source.cancel()

    assert source.token.cancellation_requested is True
