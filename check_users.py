import sqlite3

conn = sqlite3.connect("hospital.db")
cursor = conn.cursor()

cursor.execute("SELECT id, name, email, role FROM users")

rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()