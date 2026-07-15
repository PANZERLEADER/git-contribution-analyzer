# ruff: noqa: F821
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
)

GUI_MODULE_PREFIXES = (
    "git_contribution_analyzer.adapters.gui",
    "git_contribution_analyzer.application.facades",
    "git_contribution_analyzer.gui",
)


def is_core_module(name):
    return not any(
        name == prefix or name.startswith(f"{prefix}.") for prefix in GUI_MODULE_PREFIXES
    )


def is_core_data(entry):
    source = entry[0].replace("\\", "/")
    return "/gui/" not in source


datas = [
    entry
    for entry in collect_data_files("git_contribution_analyzer", include_py_files=True)
    if is_core_data(entry)
]
hiddenimports = collect_submodules(
    "git_contribution_analyzer", filter=is_core_module
) + collect_submodules(
    "alembic", filter=lambda name: not name.startswith("alembic.testing")
)

a = Analysis(
    ["src/git_contribution_analyzer/cli/app.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "shiboken6", *GUI_MODULE_PREFIXES],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="gca",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
