Jiggy is an open source vector persistence and indexing service build around hnswlib (with support for faiss/autofaiss in the future).

Vector search can be decomposed into 3 stages:

1) Vector Persistence
2) Index Build from Persistence (including Index Optimization)
3) Vector Search using an Index

With the Jiggy architecture, #1 and #2 are handled by the Jiggy service and #3 is handled in your own code by using hnswlib locally with the jiggy-generated index files (downloaded from the Jiggy service).

Currently a demo version of this is running at api.jiggy.ai (see https://api.jiggy.ai/jiggy-v0/docs#/ for API doc).

See https://github.com/jiggy-ai/jiggy-client-py/blob/master/quickstart.py 


**Dependencies**

Jiggy service depends on a Postgres database and S3 compatible object storage.

Configuration for these services is passed via the following environment variables:

- JIGGY_STORAGE_KEY_ID
- JIGGY_STORAGE_KEY_SECRET
- JIGGY_STORAGE_ENDPOINT_URL

- JIGGY_POSTGRES_USER
- JIGGY_POSTGRES_PASS
- JIGGY_POSTGRES_HOST

In addition it needs the following environment variables for generating jwt keys:

- JIGGY_JWT_RSA_PRIVATE_KEY
- JIGGY_JWT_RSA_PUBLIC_KEY
