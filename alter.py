import sqlite3

conn=sqlite3.connect("test.db")
cursor=conn.cursor()

cursor.execute("Alter table transactions add column stripe_intent_id VARCHAR(100) ")

print("Done successfully")

conn.commit()
conn.close()

