import urllib.request
import json

# Test 1: Status
try:
    with urllib.request.urlopen("http://localhost:8000/api/status", timeout=10) as r:
        print("STATUS OK:", json.loads(r.read()).get("status"))
except Exception as e:
    print("STATUS ERROR:", e)

# Test 2: Clear cache
try:
    with urllib.request.urlopen("http://localhost:8000/api/admin/clear-cache", timeout=10) as r:
        print("CLEAR CACHE:", json.loads(r.read()))
except Exception as e:
    print("CLEAR CACHE ERROR:", e)

# Test 3: Simulate base - mostrar el body del error
try:
    with urllib.request.urlopen("http://localhost:8000/api/simulate/base", timeout=30) as r:
        data = json.loads(r.read())
        detail = data.get("detail", [])
        print(f"\nOK - {len(detail)} registros")
        if detail:
            print("Campos:", list(detail[0].keys()))
            print("UATC[0]:", detail[0].get("UATC"))
            print("Fase[0]:", detail[0].get("Fase"))
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code} ERROR:\n{body[:2000]}")
except Exception as e:
    print("ERROR:", e)
