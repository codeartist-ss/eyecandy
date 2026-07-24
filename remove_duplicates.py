"""
One-off maintenance script: removes duplicate clothing_item rows (same title),
keeping the lowest item_id and deleting the rest (plus their images).

Usage:
    DATABASE_URL=postgresql://... python remove_duplicates.py
"""
import os
import sys
import psycopg2

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    sys.exit('Set the DATABASE_URL environment variable first.')

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
    SELECT title, STRING_AGG(item_id::text, ',' ORDER BY item_id) AS ids, COUNT(*) AS cnt
    FROM clothing_item
    GROUP BY title
    HAVING COUNT(*) > 1
    ORDER BY title
""")
duplicates = cur.fetchall()

if duplicates:
    print("Found duplicates:")
    for title, ids, cnt in duplicates:
        id_list = [int(x) for x in ids.split(',')]
        to_delete = id_list[1:]  # keep the first (lowest id), delete the rest
        print(f"  {title}: {cnt} copies (IDs: {ids}) -> deleting {to_delete}")
        for item_id in to_delete:
            cur.execute("DELETE FROM item_image WHERE item_id = %s", (item_id,))
            cur.execute("DELETE FROM clothing_item WHERE item_id = %s", (item_id,))
    conn.commit()
    print("\n✅ Duplicates removed!")
else:
    print("No duplicates found!")

cur.execute("SELECT item_id, title FROM clothing_item ORDER BY item_id")
remaining = cur.fetchall()
print(f"\n📦 Remaining items ({len(remaining)} total):")
for item_id, title in remaining:
    print(f"  {item_id}. {title}")

cur.close()
conn.close()
