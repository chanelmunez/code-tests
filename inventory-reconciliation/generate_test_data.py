
import csv
import os
import random

DATA_DIR = "data"

def create_csv(filename, rows, header=None):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(header)
        writer.writerows(rows)
    return path

# 1. Empty File (Header only)
create_csv("testing-empty.csv", [], header=["sku", "name", "quantity", "location", "date"])

# 1b. Truly Empty File (0 bytes)
with open(os.path.join(DATA_DIR, "testing-0bytes.csv"), "w") as f:
    pass

# 2. Garbage Data
with open(os.path.join(DATA_DIR, "testing-garbage.csv"), "wb") as f:
    f.write(b"\x00\xff\xfe\x12\x34garbage_data_random_bytes")

# 3. Large File (1000 rows for speed, but representative)
header = ["product_name", "qty", "warehouse", "updated_at", "sku"]
rows = []
for i in range(1000):
    rows.append([f"Item {i}", random.randint(1, 100), "A", "2024-01-01", f"SKU-{i:03d}"])
create_csv("testing-huge.csv", rows, header=header)

# 4. Duplicates Only
header = ["sku", "name", "quantity", "location", "date"]
rows = [
    ["SKU-001", "Item 1", 10, "A", "2024-01-01"],
    ["SKU-001", "Item 1", 10, "A", "2024-01-01"],
    ["SKU-002", "Item 2", 5, "B", "2024-01-01"],
    ["SKU-002", "Item 2", 5, "B", "2024-01-01"],
]
create_csv("testing-duplicates.csv", rows, header=header)

# 5. Missing Columns
create_csv("testing-missing-cols.csv", [["SKU-001", 10]], header=["sku", "quantity"])

# 6. Collisions (Normalization triggers duplicate)
# SKU-001 and SKU001 -> both normalize to SKU-001
header = ["sku", "name", "quantity", "location", "date"]
rows = [
    ["SKU-001", "Item 1", 10, "A", "2024-01-01"],
    ["SKU001", "Item 1 (Alt)", 20, "A", "2024-01-01"], 
]
create_csv("testing-collisions.csv", rows, header=header)

# 7. Extreme Values
header = ["sku", "name", "quantity", "location", "date"]
rows = [
    ["SKU-MAX", "Max Int", 999999999999, "A", "2024-01-01"],
    ["SKU-MIN", "Min Int", -999999999999, "A", "2024-01-01"],
    ["SKU-LONG", "A" * 1000, 1, "B" * 1000, "2024-01-01"],
]
create_csv("testing-extreme.csv", rows, header=header)

print("Test data generated.")
