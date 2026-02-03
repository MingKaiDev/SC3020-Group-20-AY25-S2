import time
import random

import psycopg # PostgreSQL database adapter for Python

# 1. Open a connection
conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="YF-DB2",
    user="taoyf",
    password="taoyf"
)

#2. Create a cursor and issue the query
with conn.cursor() as cur:
    cur.execute("SELECT * FROM customer;")

    # 3. Fetch results
    rows = cur.fetchall()
    for row in rows:
        print(row)

# 4. Close the connection
conn.close()
