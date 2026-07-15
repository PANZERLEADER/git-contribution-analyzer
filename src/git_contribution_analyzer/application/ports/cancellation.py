from __future__ import annotations

from threading import Event
from typing import Protocol


class OperationCancelled(Exception):
    """Raised at a safe boundary after cooperative cancellation was requested."""


class CancellationToken(Protocol):
    @property
    def cancellation_requested(self) -> bool: ...

    def raise_if_cancelled(self) -> None: ...


class NeverCancelledToken:
    @property
    def cancellation_requested(self) -> bool:
        return False

    def raise_if_cancelled(self) -> None:
        return


class _EventCancellationToken:
    def __init__(self, event: Event) -> None:
        self._event = event

    @property
    def cancellation_requested(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancellation_requested:
            raise OperationCancelled("Operation cancelled")


class CancellationSource:
    def __init__(self) -> None:
        self._event = Event()
        self._token = _EventCancellationToken(self._event)

    @property
    def token(self) -> CancellationToken:
        return self._token

    def cancel(self) -> None:
        self._event.set()
