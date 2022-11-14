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

print("requesting index")
ix = collection.create_index(M=10, ef=50, metric=jiggy.DistanceMetric.l2)
print(ix)

print("downloading index")
hnsw_index = ix.hnswlib_index()

print ("verifying index IDs")
ids = hnsw_index.get_ids_list()
ids.sort()
assert(ids == list(range(NUMVECTOR)))

print ("verifying index vectors")
jiggy_vectors = hnsw_index.get_items(ids)

for vector_id in range(NUMVECTOR):
    jv = hnsw_index.get_items([vector_id])[0]
    # check mse between original vectors and returned vectors is very small
    mse = np.square(np.subtract(vectors[vector_id], jv)).mean()
    assert(mse < 1e-12)
                     

import hnswlib

brute_force_index = hnswlib.BFIndex(space="l2", dim=DIM)
brute_force_index.init_index(max_elements=NUMVECTOR)

for vector_id in range(NUMVECTOR):
    brute_force_index.add_items([vectors[vector_id]], [vector_id])

test_elements = 200
top_k = 10

# create test vectors
query_data = np.float32(np.random.random((test_elements, DIM)))

labels_bf, distances_bf = brute_force_index.knn_query(query_data, top_k)

correct = 0
total = 0

# Query the elements and measure recall:
labels_hnsw, distances_hnsw = hnsw_index.knn_query(query_data, top_k)

# recall calc:
for i in range(test_elements):
    correct += len(set(labels_hnsw[i]) & set(labels_bf[i]))
    total   += len(set(labels_hnsw[i]))
recall = float(correct) / total


print("HNSW Search @ EF=%4d:  RECALL: %.1f %%" % (ix.hnswlib_ef_search, 100*recall))
collection.delete_collection()
