import os, sys, subprocess
PYTHON_PATH = r"Y:\Supply Chain\PLAN PRODUCCION\PANEL\_SISTEMA\runtime_python\python.exe"
def main():
    if len(sys.argv) < 2:
        print("⚠️ USO: ops_sync.py 'mensaje'")
        sys.exit(1)
    print("🔐 VALIDANDO Y SUBIENDO...")
    os.system(f'"{PYTHON_PATH}" scripts/qa_scanner.py')
    os.system("git add .")
    os.system(f'git commit -m "{sys.argv[1]}"')
    os.system("git push origin main")
if __name__ == "__main__":
    main()