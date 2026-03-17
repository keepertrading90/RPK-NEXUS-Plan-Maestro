import requests

url = "http://localhost:8000/api/reports/stock-objectives"
payload = {
    "fecha_inicio": "2026-01-01",
    "fecha_fin": "2026-03-12",
    "cliente": "ALL"
}

try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
