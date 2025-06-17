import sqlite3

# Connect to the database
conn = sqlite3.connect('reddit_data.db')
cursor = conn.cursor()

# Run a query to fetch all posts
cursor.execute("SELECT * FROM posts")

# Fetch all data and print it
rows = cursor.fetchall()
for row in rows:
    print(row)

# Close the connection
conn.close()
