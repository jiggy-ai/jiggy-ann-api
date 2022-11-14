import jiggy
import numpy as np
from  time import time
from concurrent.futures import ThreadPoolExecutor

#jiggy.init("http://127.0.0.1:8000")

DIM=128
NUMVECTOR=1024

collection = jiggy.collection(f'random-{NUMVECTOR}-{DIM}')
print(collection)


print("requesting index")
ix = collection.create_index(target_recall=0.88)
print(ix)

print("downloading index")
hnsw_index = ix.hnswlib_index()

print ("verifying index IDs")
ids = hnsw_index.get_ids_list()
ids.sort()
assert(ids == list(range(NUMVECTOR)))

print ("verifying index vectors")
jiggy_vectors = hnsw_index.get_items(ids)

if hnsw_index.space != "cosine":  # cosine normalizes the vectors so can't check equality
    for vector_id in range(NUMVECTOR):
        jv = hnsw_index.get_items([vector_id])[0]
        # check mse between original vectors and returned vectors is very small
        mse = np.square(np.subtract(vectors[vector_id], jv)).mean()
        assert(mse < 1e-12)
                     

test_ef = 50
hnsw_index.set_ef(test_ef)

import hnswlib

brute_force_index = hnswlib.BFIndex(space="cosine", dim=DIM)
brute_force_index.init_index(max_elements=NUMVECTOR)

print("Add Vectors to Brute Force Index")
with ThreadPoolExecutor(max_workers=20) as pool:
    def add(vector_id):
        jv = collection.get(vector_id)
        brute_force_index.add_items([jv], [vector_id])
    for vector_id in range(NUMVECTOR):
        pool.submit(add, vector_id)
    pool.shutdown()


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


print("HNSW Search @ EF=%4d:  RECALL: %.1f %%" % (test_ef, 100*recall))
#collection.delete_collection()
