import re
import pandas as pd

def clean_val(v):
    if pd.isna(v): return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(' ', '')
    if not s: return 0.0
    
    # Lógica robusta para formato europeo (6.678.165 o 1.234,56)
    if ',' in s and '.' in s:
        # Estilo 1.234,56 -> quitar puntos, cambiar coma por punto
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        # Estilo 1234,56 -> cambiar coma por punto
        s = s.replace(',', '.')
    elif s.count('.') > 1:
        # Estilo 6.678.165 -> quitar todos los puntos
        s = s.replace('.', '')
    
    s = re.sub(r'[^\d.\-]', '', s)
    try: return float(s) if s else 0.0
    except: return 0.0

test_cases = [
    ("6.678.165", 6678165.0),
    ("1.234,56", 1234.56),
    ("1,234.56", 1.23456),
    ("1000", 1000.0),
    ("1.000", 1.0),
    ("1,000", 1.0),
    (" 2.345,67 ", 2345.67),
    ("1.234.567,89", 1234567.89),
    ("338.115,48", 338115.48)
]

for tc, expected in test_cases:
    res = clean_val(tc)
    status = "OK" if res == expected else "FAIL"
    print(f"Input: '{tc}' -> Result: {res} (Expected: {expected}) {status}")
