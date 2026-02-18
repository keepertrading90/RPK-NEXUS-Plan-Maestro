import os, sys, subprocess
PYTHON_PATH = r"\\RPK4TGN\ofimatica\Supply Chain\PLAN PRODUCCION\PANEL\_SISTEMA\runtime_python\python.exe"
def main():
    if len(sys.argv) < 2:
        print("[WARN] USO: ops_sync.py 'mensaje'")
        sys.exit(1)
    print("[INFO] VALIDANDO Y SUBIENDO...")
    os.system(f'"{PYTHON_PATH}" scripts/qa_scanner.py')
    os.system("git add .")
    # Usar comillas dobles escapadas para el mensaje de commit en Windows
    msg = sys.argv[1].replace('"', '\"')
    os.system(f'git commit -m "{msg}"')
    os.system("git push origin main")
if __name__ == "__main__":
    main()