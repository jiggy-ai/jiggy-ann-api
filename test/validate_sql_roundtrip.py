# verify that data that is written to and then read from DB produces same index recall as original data
# this tests against data precision errors as data is converted into database real and back

import os
from sqlmodel import Session, create_engine, SQLModel, select
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound
from random import random, choice
import json
from models import *
from hnsw_recall import hnsf_recall_perf
import string

db_host = os.environ['JIGGY_POSTGRES_HOST']
user = os.environ['JIGGY_POSTGRES_USER']
passwd = os.environ['JIGGY_POSTFRES_PASS']
DBURI = 'postgresql+psycopg2://%s:%s@%s:5432/jiggy' % (user, passwd, db_host)
engine = create_engine(DBURI, pool_pre_ping=True, echo=False)


SQLModel.metadata.create_all(engine)

DIMENSION=128
SIZE=10000
TEST_SIZE=2000
index_M=256
index_ef_construction=64
test_ef_list=[32, 64, 128, 256]

# make a collection name for this test
COLLECTION =  ''.join(choice(string.ascii_uppercase) for i in range(10))
      
# make the real vector data
DATA = [[random() for i in range(DIMENSION)] for j in range(SIZE)]

# Generate query test data used against original and db data
query_data = [[random() for i in range(DIMENSION)] for j in range(TEST_SIZE)]


# save it to database
with Session(engine) as session:
    collection = Collection(name=COLLECTION, dimension=DIMENSION)
    session.add(collection)
    session.commit()
    session.refresh(collection)

    for i in range(SIZE):
        v = Vector(collection_id = collection.id,
                   vector        = DATA[i],
                   value         = i)
        session.add(v)
        if not i % 1000: print(i)
    session.commit()


    
# hnsflib perf on original data
hnsf_recall_perf(data = DATA,
                 query_data = query_data,
                 index_M=index_M,
                 index_ef_construction=index_ef_construction,
                 test_ef_list=test_ef_list)
                 

# hnsflib perf on database data
with Session(engine) as session:
    statement = select(Collection).where(Collection.name == COLLECTION)
    collection = session.exec(statement).one()
    statement = select(Vector).where(Vector.collection_id == collection.id).order_by(Vector.value)
    hnsf_recall_perf(data = [v.vector for v in session.exec(statement)],
                     query_data = query_data,
                     index_M=index_M,
                     index_ef_construction=index_ef_construction,
                     test_ef_list=test_ef_list)






    
