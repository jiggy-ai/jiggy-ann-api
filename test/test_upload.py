import jiggy
import numpy as np
from time import time
from concurrent.futures import ThreadPoolExecutor

from random import random

#jiggy.init(host='http://localhost:8000')

collection = jiggy.create_collection(f'test-{int(time())}')
print(collection)

DIM=128
NUMVECTOR=1024

vectors = np.random.random((NUMVECTOR, DIM))

t0 = time()
# parallelize upload with threads to dramatically increase upload throughput
with ThreadPoolExecutor(max_workers=20) as pool:
    for vector_id in range(NUMVECTOR):
        pool.submit(collection.add, vectors[vector_id], vector_id)
    print("waiting shutdown")
    pool.shutdown()
dt = time()-t0
xput = NUMVECTOR/dt
print(f"uploaded {NUMVECTOR} in {dt:.1f} seconds ({xput:.1f}/s)")

collection.delete_collection()
