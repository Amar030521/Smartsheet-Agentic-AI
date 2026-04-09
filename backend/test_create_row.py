"""
Run this directly to test row creation:
  python test_create_row.py
"""
import sys, os
sys.path.insert(0, '.')
sys.path.insert(0, 'mcp')

from dotenv import load_dotenv
load_dotenv()

import smartsheet

token = os.getenv('SMARTSHEET_API_TOKEN')
client = smartsheet.Smartsheet(token)
client.errors_as_exceptions(True)

SHEET_ID = 5098143252172676

print("Step 1: Fetching sheet...")
sheet = client.Sheets.get_sheet(SHEET_ID)
print(f"  Sheet: {sheet.name}, Columns: {len(sheet.columns)}, Rows: {len(sheet.rows or [])}")

# Build column map
col_map = {col.title: col for col in sheet.columns}
print("\nStep 2: Column map:")
for title, col in col_map.items():
    print(f"  {title}: id={col.id_}, type={col.type_}, formula={bool(col.formula)}, system={col.system_column_type}")

# Build minimal test row - only TEXT_NUMBER columns, no formulas
print("\nStep 3: Building test row...")
cells = []
test_data = {
    "Project Name": "TEST ROW - DELETE ME",
    "Project Description": "Test from API",
}

for col_name, value in test_data.items():
    col = col_map.get(col_name)
    if col:
        cell = smartsheet.models.Cell()
        cell.column_id = col.id_
        cell.value = value
        cell.strict = False
        cells.append(cell)
        print(f"  Adding: {col_name} = {value} (col_id={col.id_})")
    else:
        print(f"  SKIP: {col_name} not found")

print(f"\nStep 4: Creating row with {len(cells)} cells...")
new_row = smartsheet.models.Row()
new_row.to_bottom = True
new_row.cells = cells

try:
    result = client.Sheets.add_rows(SHEET_ID, [new_row])
    print(f"  Result type: {type(result).__name__}")
    print(f"  Result code: {getattr(result, 'result_code', 'N/A')}")
    print(f"  Data: {result.data}")
    if result.data:
        created = result.data[0]
        print(f"\n✅ SUCCESS! Row created at position {created.row_number} with ID {created.id}")
    else:
        print(f"\n❌ Empty data returned. Message: {getattr(result, 'message', 'None')}")
except Exception as e:
    print(f"\n❌ EXCEPTION: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
