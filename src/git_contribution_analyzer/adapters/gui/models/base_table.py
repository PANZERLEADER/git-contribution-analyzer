from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QByteArray,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Slot,
)

_INVALID_INDEX = QModelIndex()


@dataclass(frozen=True, slots=True)
class Column:
    key: str
    title: str


class DictTableModel(QAbstractTableModel):
    def __init__(
        self,
        *,
        columns: tuple[Column, ...],
        rows: tuple[dict[str, Any], ...] = (),
    ) -> None:
        super().__init__()
        self._columns = columns
        self._source_rows = tuple(dict(row) for row in rows)
        self._rows = self._source_rows
        self._filter = ""
        self._roles = {
            int(Qt.ItemDataRole.UserRole) + index + 1: QByteArray(column.key.encode("utf-8"))
            for index, column in enumerate(columns)
        }

    def rowCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = _INVALID_INDEX,
    ) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = _INVALID_INDEX,
    ) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        if role == int(Qt.ItemDataRole.DisplayRole):
            if not 0 <= index.column() < len(self._columns):
                return None
            value = row.get(self._columns[index.column()].key)
            return "" if value is None else value
        role_name = self._roles.get(role)
        if role_name is not None:
            return row.get(bytes(role_name.data()).decode("utf-8"))
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> Any:
        if (
            role == int(Qt.ItemDataRole.DisplayRole)
            and orientation == Qt.Orientation.Horizontal
            and 0 <= section < len(self._columns)
        ):
            return self._columns[section].title
        return None

    def roleNames(self) -> dict[int, QByteArray]:
        return dict(self._roles)

    def set_rows(self, rows: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._source_rows = tuple(dict(row) for row in rows)
        self._rows = self._filtered_rows()
        self.endResetModel()

    @Slot(str)
    def set_filter(self, value: str) -> None:
        self.beginResetModel()
        self._filter = value.strip().casefold()
        self._rows = self._filtered_rows()
        self.endResetModel()

    def _filtered_rows(self) -> tuple[dict[str, Any], ...]:
        if not self._filter:
            return self._source_rows
        return tuple(
            row
            for row in self._source_rows
            if any(self._filter in str(value).casefold() for value in row.values())
        )
