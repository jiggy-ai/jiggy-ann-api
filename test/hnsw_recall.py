import hnswlib
import numpy as np
from time import time
import os
import psutil
import sys
import json


"""

VERIFY: Each HNSW graph uses roughly 1.1 * (4 * d + 8 * M) * num_vectors bytes of memory


Index Parameters

M - the number of bi-directional links created for every new element during construction. 
    Reasonable range for M is 2-100. Higher M work better on datasets with high intrinsic 
    dimensionality and/or high recall, while low M work better for datasets with low intrinsic 
    dimensionality and/or low recalls. 
    
    The parameter also determines the algorithm's memory consumption, 
    which is roughly M * 8-10 bytes per stored element.

     As an example for dim=4 random vectors optimal M for search is somewhere around 6, 
     while for high dimensional datasets (word embeddings, good face descriptors), 
     higher M are required (e.g. M=48-64) for optimal performance at high recall. 
     The range M=12-48 is ok for the most of the use cases. 
     When M is changed one has to update the other parameters. 
     Nonetheless, ef and ef_construction parameters can be roughly estimated by assuming 
     that M*ef_{construction} is a constant.

ef_construction - the parameter has the same meaning as ef, but controls the index_time/index_accuracy.
                  Bigger ef_construction leads to longer construction, but better index quality. 
                  At some point, increasing ef_construction does not improve the quality of the index. 
                  One way to check if the selection of ef_construction was ok is to measure a recall for 
                  M nearest neighbor search when ef =ef_construction: if the recall is lower than 0.9, 
                  than there is room for improvement.

num_elements - defines the maximum number of elements in the index. 
               The index can be extened by saving/loading
               (load_index function has a parameter which defines the new maximum number of elements).


Search Parameters

ef - the size of the dynamic list for the nearest neighbors (used during the search). 
     Higher ef leads to more accurate but slower search. 
      ef cannot be set lower than the number of queried nearest neighbors k. 
      The value ef of can be anything between k and the size of the dataset.

k  -  number of nearest neighbors to be returned as the result. 
      The knn_query function returns two numpy arrays, containing labels and distances
      to the k found nearest elements for the queries. 
      Note that in case the algorithm is not be able to find k neighbors to all of the queries, 
      (this can be due to problems with graph or k>size of the dataset) an exception is thrown.
"""

np.random.seed(int(time()))

results = []

def hnsf_recall_perf(data,                     #  list of elements vectors for index
                     query_data,               #  list of test vectors
                     index_M,                  #  M links for building the index
                     index_ef_construction,    #  ef for building the index
                     test_ef_list,             #  list of search-time ef to test against
                     test_k=10,                #  test k size
                     distance_metric='cosine', #  cosine, l2, ip
                     num_threads=10):

    index_elements = len(data)
    vector_dimension = len(data[0])
    
    print("\n============================================")
    print("============================================")
    print("vector_dimension:      ", vector_dimension)
    print("index_elements:        ", index_elements)
    print("index_M:               ", index_M)
    print("index_ef_construction: ", index_ef_construction)
    print("test_ef_list:          ", test_ef_list)
    print("============================================\n")
    
    # Declaring index: HNSW and also Brute Force KNN as source of Ground Truth
    hnsw_index = hnswlib.Index(space=distance_metric, dim=vector_dimension)
    bf_index = hnswlib.BFIndex(space=distance_metric, dim=vector_dimension)

    # Set number of threads used during batch search/construction in hnsw
    # By default using all available cores    
    hnsw_index.set_num_threads(num_threads)
    
    # Initing both hnsw and brute force indices
    # hnsw construction params:
    # ef_construction - controls index search speed/build speed tradeoff
    #
    # M - is tightly connected with internal dimensionality of the data. Strongly affects the memory consumption (~M)
    # Higher M leads to higher accuracy/run_time at fixed ef/efConstruction

    hnsw_index.init_index(max_elements=index_elements,
                          ef_construction=index_ef_construction,
                          M=index_M)
        
    print("Index batch of %d elements of dimension %d (ef=%d, M=%d)" % (index_elements, vector_dimension, index_ef_construction, index_M))
    
    t0 = time()
    hnsw_index.add_items(data)
    HNSW_INDEX_CREATE_TIME = time()-t0
    print("HNSF index built in %.1f seconds (%d ips)" % (HNSW_INDEX_CREATE_TIME, index_elements/HNSW_INDEX_CREATE_TIME))

    fn = "random_%d_%s_%d_%d_%d.hnsf" % (vector_dimension,
                                         distance_metric,
                                         index_elements,
                                         index_M,
                                         index_ef_construction)
    t0 = time()
    hnsw_index.save_index(fn)
    HNSW_INDEX_SAVE_TIME = time()-t0
    index_size_bytes = os.stat(fn).st_size
    print("%s: %d MB (%.3f seconds to save)" % (fn, index_size_bytes/1e6, HNSW_INDEX_SAVE_TIME))
    os.unlink(fn)

    to = time()
    # create brute-force index for recall comparison
    bf_index.init_index(max_elements=index_elements)    
    bf_index.add_items(data)
    #print("brute-force index created in %d seconds" % (time()-t0))
    

    # ground truth KNN from brute forth method
    labels_bf, distances_bf = bf_index.knn_query(query_data, test_k)
    print()
    
    for test_ef in test_ef_list:
        hnsw_index.set_ef(test_ef)        
        # Measure HNSW recall at specified EF
        correct = 0
        total = 0

        # Query the elements and measure recall:
        t0 = time()
        labels_hnsw, distances_hnsw = hnsw_index.knn_query(query_data, test_k)
        HNSW_BATCH_QUERY_TIME = time() - t0

        # recall calc:
        for i in range(len(query_data)):
            correct += len(set(labels_hnsw[i]) & set(labels_bf[i]))
            total   += len(set(labels_hnsw[i]))
        recall = float(correct) / total

        LATENCY_TESTS = 100
        t0 = time()        
        for i in range(LATENCY_TESTS):
            hnsw_index.knn_query([query_data[i]], test_k)
        SINGLE_QUERY_LATENCY = (time() - t0) / LATENCY_TESTS
        
        print("HNSW Search latency %4.1f ms @ EF=%4d:  RECALL: %.1f" % (1000*SINGLE_QUERY_LATENCY,
                                                                         test_ef,
                                                                         100*recall))
    
