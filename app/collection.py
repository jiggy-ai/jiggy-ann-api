# Jiggy collection endpoints
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
from sqlmodel import Session, delete, select, or_, and_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound

from decimal import Decimal

from main import app, engine, token_auth_scheme, optional_token_auth_scheme
from auth import verified_user_id_teams

from models import *

    
###
### Collections
###

@app.post('/collections', response_model=Collection)
def post_collections(token: str = Depends(token_auth_scheme),
                     body: CollectionPostRequest = ...) -> Collection:
    """
    Create New Collection
    """
    user_id, user_team_ids = verified_user_id_teams(token)
    

    with Session(engine) as session:
        
        if body.team_id is None:
            # team_id is not specified; use the user's default team
            user = session.get(User, user_id)
            body.team_id = user.default_team_id
        elif body.team_id not in user_team_ids:  # validate user membership in the requested team
            raise HTTPException(status_code=404, detail="User is not a member of the specified team.")

        statement = select(Collection).where(Collection.team_id == body.team_id, Collection.name == body.name)
        if list(session.exec(statement)):
            raise HTTPException(status_code=409, detail="Collection name already exists in the team.")
        
        collection = Collection(**body.dict(exclude_unset=True))
        
        session.add(collection)
        session.commit()
        session.refresh(collection)
        return collection




@app.get('/collections/{collection_id}', response_model=Collection)
def get_collections_collection_id(token: str = Depends(token_auth_scheme),
                                  collection_id: str = Path(...)) -> Collection:
    """
    Get Collection Info by Collection ID
    """
    user_id, user_team_ids = verified_user_id_teams(token)
    with Session(engine) as session:    
        collection = session.get(Collection, collection_id)
        if not collection or collection.team_id not in user_team_ids:
            raise HTTPException(status_code=404, detail="Collection not found")
        return collection



from s3 import bucket


@app.delete('/collections/{collection_id}')
def delete_collections_collection_id(token: str = Depends(token_auth_scheme),
                                     collection_id: str = Path(...)):
    """
    Delete specified collection, including all associated vectors and index.
    This deletion is permanent and can not be undone.
    """
    user_id, user_team_ids = verified_user_id_teams(token)    
    with Session(engine) as session:    
        collection = session.get(Collection, collection_id)
        if not collection or collection.team_id not in user_team_ids:
            raise HTTPException(status_code=404, detail="Collection not found")
        # delete all vector data
        statement = delete(Vector).where(Vector.collection_id == collection_id)
        # delete all index adata
        session.exec(statement)
        statement = select(Index).where(Index.collection_id == collection_id)
        for index in session.exec(statement):
            bucket.delete(index.objkey)
            session.delete(index)
        # delete the collection
        session.commit()        
        session.delete(collection)
        session.commit()

        
@app.get('/collections', response_model=CollectionsGetResponse)
def get_collections(token: str = Depends(token_auth_scheme),
                    team_id: int = Query(default=None, alias='team_id'),
                    name: Optional[str] = Query(default=None, alias='name')) -> CollectionsGetResponse:
    """
    Get all collections for the calling user's team,
    or optinally the collection that marches the specified name.
    """
    user_id, user_team_ids = verified_user_id_teams(token)        
    with Session(engine) as session:
        if team_id is None:
            # team_id is not specified; use the user's default team
            user = session.get(User, user_id)
            team_id = user.default_team_id
        elif team_id not in user_team_ids:  # validate user membership in the requested team
            raise HTTPException(status_code=404, detail="User is not a member of the specified team.")
        if name is not None:
            statement = select(Collection).where(Collection.team_id == team_id, Collection.name == name)
        else:
            statement = select(Collection).where(Collection.team_id == team_id)
        results = list(session.exec(statement))
        return CollectionsGetResponse(items=results)


        

    


        








    

