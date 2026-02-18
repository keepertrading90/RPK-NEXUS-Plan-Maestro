from pathlib import Path
import os

file_path = Path(r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\server_nexus.py")
base_dir = file_path.resolve().parent.parent
static_dir = base_dir / "frontend"
ui_path = static_dir / "ui" / "index.html"

print(f"BASE_DIR: {base_dir}")
print(f"STATIC_DIR: {static_dir}")
print(f"UI_PATH: {ui_path}")
print(f"UI_EXISTS: {ui_path.exists()}")

if ui_path.exists():
    with open(ui_path, "r", encoding="utf-8") as f:
        print(f"UI_TITLE: {f.readline()}")
        print(f"UI_TITLE_2: {f.readline()}")
        print(f"UI_TITLE_3: {f.readline()}")
        print(f"UI_TITLE_4: {f.readline()}")
        print(f"UI_TITLE_5: {f.readline()}")
        print(f"UI_TITLE_6: {f.readline()}")
        print(f"UI_TITLE_7: {f.readline()}")
