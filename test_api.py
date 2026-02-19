import requests
import json

base_url = "http://localhost:8000/api"

def check_endpoint(endpoint, params=None):
    print(f"\n--- Testing {endpoint} ---")
    try:
        r = requests.get(f"{base_url}{endpoint}", params=params)
        print(f"Status: {r.status_code}")
        data = r.json()
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            # Print a summary of the data
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, (list, dict)):
                        print(f" - {k}: {len(v)} items")
                    else:
                        print(f" - {k}: {v}")
                if "kpis" in data:
                    print(f"   KPIs: {data['kpis']}")
            else:
                print(f" - Length: {len(data)}")
    except Exception as e:
        print(f"Request failed: {e}")

check_endpoint("/fechas")
check_endpoint("/summary", params={"fecha_inicio": "2026-02-19", "fecha_fin": "2026-02-19"})
check_endpoint("/status")
