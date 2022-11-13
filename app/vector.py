# Jiggy vector endpoints
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
from auth import verified_user_id
from sqlmodel import Session, select, or_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound


from main import app, engine, token_auth_scheme
from auth import verified_user_id_teams

from models import *

    
###
### Vectors
###

@app.post('/collections/{collection_id}/vectors/{vector_id}', response_model=VectorResponse)
def post_vectors(token: str = Depends(token_auth_scheme),
                 collection_id: str = Path(...),
                 vector_id: str = Path(...),
                 body: VectorPostRequest = ...) -> VectorResponse:
    """
    Create New Vector
    """
    user_id, user_team_ids = verified_user_id_teams(token)        
    with Session(engine) as session:
        collection = session.get(Collection, collection_id)
        if not collection or collection.team_id not in user_team_ids:
            raise HTTPException(status_code=404, detail="Collection not found")
        if collection.count >= 1000000:
            raise HTTPException(status_code=400,
                                detail="Largest supported collection size is currently 1M vectors during alpha test phase.")

        statement = select(Vector).where(Vector.vector_id == vector_id, Vector.collection_id == collection_id)
        vector = session.exec(statement).first()
        if vector:
            session.delete(vector)   # replace the existing vector with the same key
            collection.count -= 1
        if collection.dimension == 0:
            # update dimension to the actual length of the vector
            collection.dimension = len(body.vector)
            if collection.dimension > 12288:
                raise HTTPException(status_code=400, detail="Largest supported dimension is currently 12288")
            
        elif collection.dimension != len(body.vector):
            raise HTTPException(status_code=400,
                                detail="Vector dimension %d mismatches existing collection dimension of %d." % (len(body.vector), collection.dimension))
        vector = Vector(vector_id = vector_id,
                        collection_id = collection_id,
                        vector = body.vector)
        collection.count += 1        
        collection.updated_at = time()
        session.add(collection)
        session.add(vector)
        session.commit()
        session.refresh(vector)
        return vector


@app.delete('/collections/{collection_id}/vectors/{vector_id}')
def delete_vectors(token: str = Depends(token_auth_scheme),
                   collection_id: str = Path(...),
                   vector_id: str = Path(...)):
    """
    Delete Vector
    """
    user_id, user_team_ids = verified_user_id_teams(token)    
    with Session(engine) as session:
        collection = session.get(Collection, collection_id)
        if not collection or collection.team_id not in user_team_ids:
            raise HTTPException(status_code=404, detail="Collection not found")
        statement = select(Vector).where(Vector.vector_id == vector_id, Vector.collection_id == collection_id)
        vector = session.exec(statement).first()
        if not vector:
            raise HTTPException(status_code=404, detail="Vector not found")
        session.delete(vector)
        collection.count -= 1
        collection.updated_at = time()
        session.add(collection)
        session.commit()


    
@app.get('/collections/{collection_id}/vectors/{vector_id}', response_model=VectorResponse)
def get_vectors(token: str = Depends(token_auth_scheme),
                collection_id: str = Path(...),
                vector_id: str = Path(...)) -> VectorResponse:
    """
    Get Existing Vector
    """
    user_id, user_team_ids = verified_user_id_teams(token)
    with Session(engine) as session:
        collection = session.get(Collection, collection_id)
        if not collection or collection.team_id not in user_team_ids:
            raise HTTPException(status_code=404, detail="Collection not found")
        statement = select(Vector).where(Vector.vector_id == vector_id, Vector.collection_id == collection_id)
        vector = session.exec(statement).first()
        if not vector:
            raise HTTPException(status_code=404, detail="Vector not found")
        return VectorResponse(**vector.dict())

