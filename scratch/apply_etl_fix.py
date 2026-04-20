
content = open(r'scripts\etl_historical_master.py', 'r', encoding='utf-8').read()

# Find the problematic line
target_old = "    # Give a unique name based on the date of the data and a timestamp"
if target_old in content:
    # Replace just the comment and the filename line
    old_block = (
        "    # Give a unique name based on the date of the data and a timestamp\n"
        "    final_file = partition_path / f\"{target_path.stem}_{first_date.replace('-','')}_{datetime.now().strftime('%H%M%S')}.parquet\""
    )
    new_block = (
        "    # FIX: Nombre basado SOLO en la fecha (YYYYMMDD), sin timestamp de hora.\n"
        "    # Re-ejecutar el ETL para el mismo dia SOBRESCRIBE el fichero existente,\n"
        "    # en lugar de crear uno nuevo duplicado (causa del error sistematico de duplicacion).\n"
        "    final_file = partition_path / f\"{target_path.stem}_{first_date.replace('-','')}.parquet\""
    )
    if old_block in content:
        content = content.replace(old_block, new_block, 1)
        open(r'scripts\etl_historical_master.py', 'w', encoding='utf-8').write(content)
        print("OK - Fix aplicado correctamente")
    else:
        print("ERROR - Bloque exacto no encontrado")
        # Print the relevant section for inspection
        idx = content.find(target_old)
        print(repr(content[idx:idx+200]))
else:
    print("ERROR - Comentario no encontrado en el fichero")
