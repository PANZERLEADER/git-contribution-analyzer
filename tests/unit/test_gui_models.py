from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt

from git_contribution_analyzer.adapters.gui.models.base_table import Column, DictTableModel


def test_table_model_should_expose_stable_roles() -> None:
    model = DictTableModel(
        columns=(Column("name", "Name"), Column("status", "Status")),
        rows=({"name": "Alice", "status": "COMPLETED"},),
    )

    assert model.rowCount() == 1
    assert model.columnCount() == 2
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == "Alice"
    assert model.roleNames()[Qt.ItemDataRole.UserRole + 1] == b"name"
    assert model.data(QModelIndex(), Qt.ItemDataRole.DisplayRole) is None


def test_table_model_should_filter_without_mutating_source() -> None:
    rows = (
        {"name": "Alice", "status": "COMPLETED"},
        {"name": "Bob", "status": "FAILED"},
    )
    model = DictTableModel(columns=(Column("name", "Name"),), rows=rows)

    model.set_filter("bob")

    assert model.rowCount() == 1
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == "Bob"
    assert len(rows) == 2
