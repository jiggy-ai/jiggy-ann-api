import jiggy
import numpy as np
from time import time
from concurrent.futures import ThreadPoolExecutor

#jiggy.init("http://127.0.0.1:8000")

collection = jiggy.create_collection(f'test-{int(time())}')
print(collection)

DIM=128
NUMVECTOR=1024

vectors = np.random.random((NUMVECTOR, DIM))

print(f"Uploading collection of {NUMVECTOR} vectors of dimension {DIM}")
# parallelize upload with threads to dramatically increase upload throughput
with ThreadPoolExecutor(max_workers=20) as pool:
    for vector_id in range(NUMVECTOR):
        pool.submit(collection.add, vectors[vector_id], vector_id)
    print("awaiting upload")
    pool.shutdown()

print(collection.count)
assert(collection.count == NUMVECTOR)

print("verifying vectors")

with ThreadPoolExecutor(max_workers=20) as pool:
    def verify(vector_id):
        jv = collection.get(vector_id)
        mse = np.square(np.subtract(vectors[vector_id], jv)).mean()
        if mse > 1e-12:
            print("error", mse)
    for vector_id in range(NUMVECTOR):
        pool.submit(verify, vector_id)
    pool.shutdown()


print("Deleting vectors")

with ThreadPoolExecutor(max_workers=20) as pool:
    for vector_id in range(NUMVECTOR):
        pool.submit(collection.delete, vector_id)
    pool.shutdown()

print(collection.count)
assert(collection.count == 0)

collection.delete_collection()
