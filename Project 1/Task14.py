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
        #Task 14b
        #cur.execute("insert into t1 select (floor(random()*10000)+1)::int, (floor(random()*10000)+1)::int,(floor(random()*10000)+1)::int, (floor(random()*10000)+1)::int,(floor(random()*10000)+1)::int from generate_series(1, 1000000);")
        
        #14c
        for i in range(1000000):
            a = random.randint(1, 10000)
            b = random.randint(1, 10000)
            c = random.randint(1, 10000)
            d = random.randint(1, 10000)
            e = random.randint(1, 10000)
            
            cur.execute(
                "INSERT INTO t1 (a, b, c, d, e) VALUES (%s, %s, %s, %s, %s)",
                (a, b, c, d, e)
            )
        
        
        
        conn.commit()
    except Exception:
        conn.rollback()
    print("Running Time of Task 14c Insertion: %s seconds " % round((time.time() - start_time),5))


# 4. Close the connection
conn.close()
