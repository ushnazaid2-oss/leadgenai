import sqlite3
conn = sqlite3.connect('leadgenai.db')
conn.execute("UPDATE email_accounts SET name='Zaid AI Solutions'")
conn.commit()
conn.close()
print("Updated successfully")
