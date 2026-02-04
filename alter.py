import sqlite3



conn = sqlite3.connect("test.db")
cursor = conn.cursor()

cursor.execute("DELETE from orders where o_id == 21;")
conn.commit()
conn.close()

print("Row updated successfully")
