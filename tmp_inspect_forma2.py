import pandas as pd
from pathlib import Path

ONEDRIVE = Path(r"C:\Users\ismael.rodriguez\OneDrive - RPK S COOP")
file_path = ONEDRIVE / "MESA UATC Tarragona - UATC RETENES-COMPRESION" / "CARGA FORMA 2.xlsm"

import shutil
import tempfile

tmp_path = Path(tempfile.gettempdir()) / f"nexus_fase10_{file_path.stem}.xlsm"
shutil.copy2(file_path, tmp_path)
df = pd.read_excel(tmp_path, header=None, engine='calamine')

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

print(df.head(45).to_string())
