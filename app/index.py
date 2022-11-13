# Jiggy Index endpoints
# Copyright (C) 2022 William S. Kish


from __future__ import annotations
from typing import List, Optional
from pydantic import conint
from fastapi import FastAPI, Path, Query, HTTPException, UploadFile, File, Depends
from fastapi.security import HTTPBearer 
from fastapi.routing import APIRouter
from fastapi.responses import Response
import string
import random
from time import time
import os
from auth import verified_user_id_teams
from sqlmodel import Session, select, or_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound
from threading import Thread
import hnswlib
import psutil
from decimal import Decimal
import numpy as np

from s3 import  create_presigned_url, bucket

from main import app, engine, token_auth_scheme

from models import *
   
CPU_COUNT = psutil.cpu_count()


###
##  Index
###

def _create_index(index):
    with Session(engine) as session:
        print("create_index")
        session.add(index)
        index.build_status = "Preparing data for indexing."
        index.state = IndexBuildState.prep
        session.commit()
        collection = session.get(Collection, index.collection_id)
        statement = select(Vector).where(Vector.collection_id == index.collection_id)
        vectors = list(session.exec(statement))

        index.state = IndexBuildState.indexing
        index.count = len(vectors)
        index.build_status = "Index build of %d (dimension %d) vectors in progress." % (len(vectors),
                                                                                        collection.dimension)
        session.commit()
        
        hnsw_index = hnswlib.Index(space=index.metric, dim=collection.dimension)
        hnsw_index.set_num_threads(int(CPU_COUNT/2))
        hnsw_index.init_index(max_elements=len(vectors),
                              ef_construction=index.hnswlib_ef,
                              M=index.hnswlib_M)
        t0 = time()
        for v in vectors:
            hnsw_index.add_items([v.vector], [v.vector_id])

        index.build_status = "Saving index."
        index.state = IndexBuildState.saving
        session.commit()
        HNSW_INDEX_CREATE_TIME = time()-t0
        filename = "index-%d.hnsf" % index.id
        hnsw_index.save_index(filename)
        import hashlib
        print(hashlib.md5(open(filename,'rb').read()).hexdigest())

        INDEX_SIZE_BYTES = os.stat(filename).st_size
        index.completed_at = time()
        index.build_status = "Index build of %d (dimension %d) vectors completed in %.1f seconds generating %.1f MB index." % (len(vectors),
                                                                                                                               collection.dimension,
                                                                                                                               HNSW_INDEX_CREATE_TIME,
                                                                                                                               INDEX_SIZE_BYTES/1024/1024)
        index.state = IndexBuildState.complete
        bucket.upload_file(filename, index.objkey)

        session.commit()
        print("test")
        # Test the Index
        hnsw_index.set_ef(index.hnswlib_ef)
        DIM = collection.dimension
        NUMVECTOR=len(vectors)

        # verify elements
        ids = hnsw_index.get_ids_list()
        ids.sort()
        original_ids = [v.vector_id for v in vectors]
        original_ids.sort()
        assert(ids == original_ids)
        
        brute_force_index = hnswlib.BFIndex(space=index.metric, dim=DIM)
        brute_force_index.init_index(max_elements=NUMVECTOR)

        for v in vectors:
            brute_force_index.add_items([v.vector], [v.vector_id])

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

        print("HNSW Search @ EF=%4d:  RECALL: %.1f %%" % (index.hnswlib_ef, 100*recall))
        
        # Test the Index
        # Delete the Index
        os.unlink(filename)
        
def create_index(index):
    try:
        _create_index(index)
        print("Complete Index:", index)
    except Exception as e:
        print("Exception:")
        with Session(engine) as session:
            print(e)
            print(index)
            index.completed_at = time()
            index.state = IndexBuildState.failed
            index.build_status = f"Index {index.id} failed to build.  Please contact support@jiggy.ai"
            session.add(index)
            session.commit()



@app.post('/collections/{collection_id}/index', response_model=IndexResponse)
def post_index(token: str = Depends(token_auth_scheme),
               collection_id: str = Path(...),
               body: IndexRequest = ...) -> IndexResponse:
    """
    Create New Index
    """
    user_id, user_team_ids = verified_user_id_teams(token)    
        
    with Session(engine) as session:
        
        # validate collection_id and user access to collection_id        
        collection = session.get(Collection, collection_id)
        if not collection or collection.team_id not in user_team_ids:
            raise HTTPException(status_code=404, detail="Collection not found")

        team = session.get(Team, collection.team_id)

        # create the new index
        index = Index(**body.dict(exclude_unset=True),
                      state=IndexBuildState.prep,
                      build_status="Init",
                      completed_at = 0,    # doesn't work if set directly to a float or Decimal?  workaround below
                      name   = f"{team.name}/{collection.name}:{body.tag}",
                      objkey = f"{team.name}/{collection.name}-{body.tag}.{body.target_library}",
                      collection_id = collection_id)

        # estimate completed_at time
        completed_at = time() + 1000
        index.completed_at = completed_at

        # clear out any existing index with the same name (similar to docker image tags) just prior to adding the new index
        statement = select(Index).where(Index.collection_id == collection_id, Index.tag == body.tag)
        for old_index in session.exec(statement):
            session.delete(old_index)
            # XXX TODO: delete associated index file assets
        
        session.add(index)
        session.commit()
        session.refresh(index)
    # create the response before we start the build thread in case there is an Exception creating the reponse.
    response = IndexResponse(**index.dict())
    Thread(target=create_index, args=(index,)).start()
    return response

    
@app.get('/collections/{collection_id}/index', response_model=CollectionsIndexGetResponse)
def get_collection_index(token: str = Depends(token_auth_scheme),
                         collection_id: str = Path(...),
                         tag: Optional[str] = Query(alias='tag')) -> CollectionsIndexGetResponse:
    """
    Get all indices for the specified collection,
    or optimally the index corresponding to the specified tag.
    """
    user_id, user_team_ids = verified_user_id_teams(token)
    
    with Session(engine) as session:
        # validate collection_id and user access to collection_id
        collection = session.get(Collection, collection_id)
        if not collection or collection.team_id not in user_team_ids:
            raise HTTPException(status_code=404, detail="Collection not found")        
        if tag:
            statement = select(Index).where(Index.collection_id == collection_id, Index.tag ==tag)
        else:
            statement = select(Index).where(Index.collection_id == collection_id)
        results = [IndexResponse(**r.dict(), url=create_presigned_url(r.objkey) ) for r in session.exec(statement)]
        if not results:
            raise HTTPException(status_code=404, detail="No matching index found.")
        return CollectionsIndexGetResponse(items=results)


