import time
import random
import os

import psycopg # PostgreSQL database adapter for Python
from dotenv import load_dotenv

load_dotenv()

# 1. Open a connection
conn = psycopg.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

start_time = time.time()
#2. Create a cursor and issue the query
with conn.cursor() as cur:
    
    try:
        #Task 15b
        cur.execute("insert into t2 select (floor(random()*10000)+1)::int, (floor(random()*10000)+1)::int,(floor(random()*10000)+1)::int, (floor(random()*10000)+1)::int,(floor(random()*10000)+1)::int from generate_series(1, 1000000);")
        
        conn.commit()
        print("Running Time of Task 15b Insertion: %s seconds " % round((time.time() - start_time),5))
    except Exception:
        conn.rollback()
    


# 4. Close the connection
conn.close()
