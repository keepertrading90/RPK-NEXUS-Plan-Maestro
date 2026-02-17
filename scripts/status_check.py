import os, sys
REQUIRED = ["backend/core", "backend/db", "frontend/ui", "scripts", ".agent"]
def check():
    print("🏥 RPK SYSTEM DIAGNOSTIC...")
    missing = [d for d in REQUIRED if not os.path.exists(d)]
    if missing:
        print(f"❌ ERROR CRÍTICO: Faltan carpetas {missing}")
        return False
    print("🟢 Integridad Estructural: OK")
    return True
if __name__ == "__main__":
    if not check(): sys.exit(1)