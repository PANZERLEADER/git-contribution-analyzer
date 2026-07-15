import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


datas = collect_data_files("git_contribution_analyzer", include_py_files=True)
hiddenimports = (
    collect_submodules("git_contribution_analyzer")
    + collect_submodules("alembic", filter=lambda name: not name.startswith("alembic.testing"))
    + [
        "PySide6.QtCharts",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickControls2",
    ]
)

a = Analysis(
    ["src/git_contribution_analyzer/adapters/gui/app.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebEngineWidgets",
    ],
    noarchive=False,
)


def without_webengine(entries):
    return [entry for entry in entries if "webengine" not in entry[0].casefold()]


a.binaries = without_webengine(a.binaries)
a.datas = without_webengine(a.datas)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="gca-gui",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        name="gca-gui",
    )
    app = BUNDLE(
        coll,
        name="gca-gui.app",
        icon=None,
        bundle_identifier="io.github.panzerleader.gca",
        version="0.4.0",
        info_plist={"NSHighResolutionCapable": True},
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="gca-gui",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
    )
