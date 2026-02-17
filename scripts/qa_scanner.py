import os, re, sys, ast
SCAN_DIRS = ["backend", "frontend"]
FORBIDDEN_PATTERNS = {
    r"supabase": "⛔ SEGURIDAD: Referencia a nube prohibida.",
    r"print\(": "⚠️ DEPURACIÓN: Eliminar 'print'.",
    r"TODO": "🔵 INCOMPLETO: Tarea pendiente.",
    r"sk-[a-zA-Z0-9]{20,}": "🔴 SEGURIDAD: API Key expuesta."
}
def check_syntax(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        return True
    except SyntaxError as e:
        print(f"💥 ERROR DE SINTAXIS en {file_path}: Linea {e.lineno}")
        return False
    except: return True

def run_audit():
    print("🕵️  INICIANDO QA...")
    errors = 0
    for d in SCAN_DIRS:
        if not os.path.exists(d): continue
        for root, _, files in os.walk(d):
            for file in files:
                path = os.path.join(root, file)
                if file.endswith(".py") and not check_syntax(path):
                    errors += 1
    if errors > 0: sys.exit(1)
    print("✅ Código Validado.")
    sys.exit(0)
if __name__ == "__main__":
    run_audit()