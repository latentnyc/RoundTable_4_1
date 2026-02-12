import sqlite3
import json

conn = sqlite3.connect('c:\\Users\\laten\\Vibes\\RoundTable_4_1\\backend\\game.db')
cursor = conn.cursor()
cursor.execute('SELECT name, sheet_data FROM characters LIMIT 1')
row = cursor.fetchone()
if row:
    print(f"Name: {row[0]}")
    try:
        data = json.loads(row[1])
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError:
        print("Invalid JSON")
else:
    print("No characters found")
conn.close()
