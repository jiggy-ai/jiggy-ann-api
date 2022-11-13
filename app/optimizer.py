import json
import numpy as np
from sklearn import datasets, linear_model
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from random import shuffle, sample
from math import log
from time import time

data = json.load(open('results.json'))
shuffle(data)
print(len(data))

def vector(d):
    return [d['vector_dimension'], d['index_elements'], d['index_ef_construction'], d['index_M'], d['test_ef']]


# deduplicate datapoints
vset = {}

filtered = 0
ddata = []
for d in data:
    v = vector(d)
    if tuple(v) not in vset:
        ddata.append(d)
    else:
        filtered += 1
    vset[tuple(v)] = d

data = ddata
print(len(data), filtered)


def dict_to_X(d):
    memusage = (4*d['vector_dimension'] + 8*d['index_M']) * d['index_elements']
    v = vector(d)
    # X form is
    v.append(memusage)
    v.append(d['vector_dimension'] *  d['index_elements'])
    v.append(d['vector_dimension'] *  log(d['index_elements']))
    return np.array(v)

X = np.array([dict_to_X(d) for d in data])

Y_index_bytes           = np.array([d['index_bytes'] for d in data])
Y_recall                = np.array([d['recall'] for d in data])
Y_index_create_seconds  = np.array([d['index_create_seconds'] for d in data])
Y_latency               = np.array([d['single_query_latency_seconds'] for d in data])


s_ix = int(.98*len(data))    # split index

def REGRESSION(X, Y, X_test, Y_test):
    regr = linear_model.LinearRegression()
    regr.fit(X, Y)
    y_pred = regr.predict(X_test)
    #print("Coefficients: \n", regr.coef_)
    print("ERROR  %.2f" % mean_squared_error(y_pred, Y_test)**0.5)
    return regr

print("INDEX BYTES REGRESSION")
# index bytes
index_byte_rgr = REGRESSION(X[:s_ix], Y_index_bytes[:s_ix], X[s_ix:], Y_index_bytes[s_ix:])

print("\nRANDOM FORREST\n")

def RFR(X, Y, X_test, Y_test):
    rfr = RandomForestRegressor()
    rfr.fit(X, Y)
    score = rfr.score(X, Y)
    print("R-squared:", score)
    y_pred = rfr.predict(X_test)
    print("ERROR  %.3f" % mean_squared_error(y_pred, Y_test)**0.5)
    return rfr


#print("INDEX BYTES RFR")
# index bytes
#rfr(X[:s_ix], Y_index_bytes[:s_ix], X[s_ix:], Y_index_bytes[s_ix:])

print()
print("RECALL RFR")
recall_rfr = RFR(X[:s_ix], Y_recall[:s_ix], X[s_ix:], Y_recall[s_ix:])


print()
print("RECALL INDEX CREATE SECONDS RFR")
creation_seconds_rfr = RFR(X[:s_ix], Y_index_create_seconds[:s_ix], X[s_ix:], Y_index_create_seconds[s_ix:])

print()
print("RECALL latency RFR")
latency_seconds_rfr = RFR(X[:s_ix], Y_latency[:s_ix], X[s_ix:], Y_latency[s_ix:])




def predict_hnswlib(input_dict):
    """
    takes input dict with the following elements:
      vector_dimension (int)
      index_elements (int)
      index_ef_construction (int)
      index_M (int)
      test_ef (int)
    and returns a dict with the following predictions
      recall (float) recall between 0 and 1
      creation_seconds (int) creating time in seconds
      latency_seconds (float) search latency in seconds
      index_bytes (int) index size in bytes
    """
    X = dict_to_X(input_dict)
    results = {}
    results['recall'] = recall_rfr.predict([X])[0]
    results['creation_seconds'] = int(creation_seconds_rfr.predict([X])[0])
    results['latency_seconds'] = latency_seconds_rfr.predict([X])[0]
    results['index_bytes'] = int(index_byte_rgr.predict([X])[0])
    return results





M = [16, 32, 48, 64, 96, 128, 256, 512]
EF_CONSTRUCTION = [100, 200, 500, 1000, 2000]
EF_TEST         = [50, 100, 200, 500, 1000, 2000, 5000]


def optimize_hnswlib_params(vector_dimension,
                            index_elements,
                            min_recall):
    best_recall = 0
    best = None
    options = []
    t0 = time()
    seen = set()
    while ((time() - t0) < 10) and (len(options) < 50):  # run for max 10 seconds or 50 options
        
        x = {'vector_dimension': vector_dimension,
             'index_elements': index_elements,
             'index_M': sample(M,1)[0],
             'index_ef_construction': sample(EF_CONSTRUCTION, 1)[0],
             'test_ef': sample(EF_TEST, 1)[0]}
        if (x['index_M'],x['index_ef_construction'],x['test_ef']) in seen:
            continue
        seen.add((x['index_M'],x['index_ef_construction'],x['test_ef']))
        p = predict_hnswlib(x)
        if p['recall'] > best_recall:
            best  = (x, p)
            best_recall = p['recall']
        if p['recall'] > min_recall:
            options.append((x,p))            

    options.sort(key=lambda t:t[1]['recall'])
    if len(options):
        print(options[0])        
        x, p = options[0]        
    else:
        x, p = best
    x.update(p)
    print(len(list(seen)))
    return x


