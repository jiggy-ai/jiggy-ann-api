import jiggy
import numpy as np
from concurrent.futures import ThreadPoolExecutor


DIM=128
NUMVECTOR=1024

collection = jiggy.create_collection(f'random-{NUMVECTOR}-{DIM}')
print(collection)


vectors = np.random.random((NUMVECTOR, DIM))

print(f"Uploading collection of {NUMVECTOR} vectors of dimension {DIM}")
# parallelize upload with threads to dramatically increase upload throughput

with ThreadPoolExecutor(max_workers=20) as pool:
    for vector_id in range(NUMVECTOR):
        pool.submit(collection.add, vectors[vector_id], vector_id)
    print("awaiting upload")
    pool.shutdown()
