import sqlite3

conn=sqlite3.connect("test.db")
cursor=conn.cursor()

cursor.execute("Alter table products add column stock_quantity INTEGER DEFAULT 100")

print("Done successfully")

conn.commit()
conn.close()

