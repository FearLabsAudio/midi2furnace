# build/midi2furnace.spec
# Local build:
#   pyinstaller --noconfirm --workpath .pyibld --distpath dist build/midi2furnace.spec
import os, sys
from PyInstaller.utils.hooks import collect_submodules

PROJECT_DIR = os.path.abspath(os.getcwd())
ENTRY_SCRIPT = os.path.join(PROJECT_DIR, "midi2fur.py")
APP_NAME = "midi2furnace"

# Hidden imports
hidden = []
hidden += collect_submodules("imgui")
hidden += ["imgui.integrations.pygame"]
hidden += collect_submodules("pygame")
hidden += collect_submodules("OpenGL")
hidden += collect_submodules("mido")
if sys.platform.startswith("win"):
    hidden += ["OpenGL.platform.win32"]

# Optional datas (real files only)
datas = []
def add_file(rel_path, dest="."):
    p = os.path.join(PROJECT_DIR, rel_path)
    if os.path.isfile(p):
        datas.append((p, dest))

# keep these or comment them out as you prefer
add_file("readme.md", ".")
add_file("requirements.txt", ".")

# Icons if present
icon_file = None
win_icon = os.path.join(PROJECT_DIR, "assets", "app.ico")
mac_icon = os.path.join(PROJECT_DIR, "assets", "app.icns")
if sys.platform == "win32" and os.path.isfile(win_icon):
    icon_file = win_icon
elif sys.platform == "darwin" and os.path.isfile(mac_icon):
    icon_file = mac_icon

block_cipher = None

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# IMPORTANT: empty list + exclude_binaries=True
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name=APP_NAME,
)
