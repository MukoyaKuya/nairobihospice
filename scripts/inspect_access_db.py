
import pyodbc

db_path = r"C:\Users\Little Human\Desktop\NairobiHospice Access\Hospice V6.0_be.accdb"
conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_path};"

print(f"Connecting to: {db_path}")
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Get list of tables
tables = []
for row in cursor.tables(tableType='TABLE'):
    table_name = row.table_name
    if not table_name.startswith("MSys"):
        tables.append(table_name)

print("\n=== Access Database Table Summary ===")
for t in sorted(tables):
    try:
        cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
        count = cursor.fetchone()[0]
        print(f" - {t:<30} : {count:>6} rows")
    except Exception as e:
        print(f" - {t:<30} : Error counting ({e})")
print("======================================\n")
for t in sorted(tables):
    print("\n==========================================")
    print(f"TABLE: {t}")
    print("==========================================")
    columns = [column[3] for column in cursor.columns(table=t)]
    print(f"Columns ({len(columns)}): {', '.join(columns)}")

    try:
        cursor.execute(f"SELECT TOP 3 * FROM [{t}]")
        rows = cursor.fetchall()
        for idx, r in enumerate(rows, 1):
            row_dict = {}
            for col_idx, col_name in enumerate(columns):
                val = r[col_idx]
                row_dict[col_name] = str(val) if val is not None else None
            print(f" Sample Row {idx}: {row_dict}")
    except Exception as e:
        print(f" Error fetching rows: {e}")

cursor.close()
conn.close()
