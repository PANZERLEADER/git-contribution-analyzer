from PyInstaller.utils.hooks import collect_data_files, collect_submodules


datas = collect_data_files("git_contribution_analyzer", include_py_files=True)
hiddenimports = collect_submodules("git_contribution_analyzer") + collect_submodules(
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
    excludes=[],
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
