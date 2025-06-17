import sqlite3

# SQLite setup (database connection)
conn = sqlite3.connect('reddit_data.db')
cursor = conn.cursor()

# SQL command to delete the entire table
cursor.execute('DROP TABLE IF EXISTS posts')

# Commit the transaction and close the connection
conn.commit()
conn.close()

print("Table 'posts' has been deleted.")