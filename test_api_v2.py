import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_drilldown():
    centro = "782"
    mes = "2026-02"
    url = f"{BASE_URL}/centro/{centro}/articulos/mes/{mes}"
    print(f"Testing: {url}")
    try:
        res = requests.get(url)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")

def test_evolution():
    # Test for multiple centers
    centros = "782,750"
    url = f"{BASE_URL}/centro/{centros}?fecha_inicio=2026-02-01&fecha_fin=2026-02-19"
    print(f"\nTesting Evolution: {url}")
    try:
        res = requests.get(url)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_drilldown()
    test_evolution()
