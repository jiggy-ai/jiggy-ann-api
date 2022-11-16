Jiggy is an open source vector persistence and indexing service build around hnswlib (with support for faiss/autofaiss in the future).

Vector search can be decomposed into 3 stages:

1) Vector Persistence
2) Index Build from Persistence (including Index Optimization)
3) Vector Search using an Index

With the Jiggy architecture, #1 and #2 are handled by the Jiggy service and #3 is handled in your own code by using hnswlib locally. 

Currently a demo version of this is running at api.jiggy.ai.

See https://github.com/jiggy-ai/jiggy-client-py/blob/master/quickstart.py 
