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
from sqlmodel import Session, select, delete, or_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound
from threading import Thread
import hnswlib
import psutil
from decimal import Decimal
import jwt
from string import ascii_lowercase
from random import sample

from main import app, engine, token_auth_scheme
from auth import *
from models import *



def create_api_user(username, email=None):
    """
    Create a new user via API.  
    Returns the new user id
    """

    with Session(engine) as session:
        statement = select(User).where(User.username == username)
        if list(session.exec(statement)):
            raise HTTPException(status_code=409, detail="The specified username is not available.")
        statement = select(User).where(User.email == email)
        if list(session.exec(statement)):
            raise HTTPException(status_code=409, detail="The specified email already exists.")

        team = Team(name=username)
        session.add(team)
        session.commit()
        session.refresh(team)
        
        user = User(username=username,
                    email=email,
                    default_team_id=team.id,
                    link_key = "".join([sample(ascii_lowercase,1)[0] for x in range(50)]))
        session.add(user)
        session.commit()
        session.refresh(user)
        
        member = TeamMember(team_id=team.id,
                            user_id=user.id,
                            invited_by=user.id,
                            role=TeamRole.admin,
                            accepted=True)

        session.add(member)
        session.commit()
        
        # XXX send email to user to facilitate full account creation and linkage to API key
        return user.id




###
### Users
###

@app.post('/users', response_model=User)
def post_users(token: str = Depends(token_auth_scheme), body: UserPostRequest = ...) -> User:
    """
    Create new User and associate it with the auth0 token used to authenticate this call.
    This can only be called by a frontend user authenticated via auth0;
    An API Key can not be used to create a new user.
    """

    token_payload = verify_auth0_token(token.credentials)
    auth0_id = token_payload['sub']
    with Session(engine) as session:
        # verify auth0 id does not exist
        statement = select(User).where(User.auth0_userid == auth0_id)
        if session.exec(statement).first():
            raise HTTPException(status_code=400, detail="The authenticated user already exists.")

        statement = select(User).where(User.username == body.username)
        if list(session.exec(statement)):
            raise HTTPException(status_code=409, detail="The specified username is not available.")
        # create user's own team
        team = Team(name=body.username)
        session.add(team)
        session.commit()
        session.refresh(team)

        # create user's object, with default team of his own team        
        user = User(**body.dict(exclude_unset=True),
                    default_team_id=team.id,
                    auth0_userid = auth0_id)
        
        session.add(user)
        session.commit()
        session.refresh(user)
        # Add user as member of his own team
        member = TeamMember(team_id=team.id,
                            user_id=user.id,
                            invited_by=user.id,
                            role=TeamRole.admin,
                            accepted=True)

        session.add(member)

        # create apikey for user
        key = ApiKey(user_id = user.id,
                     key = "jgy-" + "".join([sample(ascii_lowercase,1)[0] for x in range(48)]))
        session.add(key)
        session.commit()
        session.refresh(user)
        return user




@app.get('/users/current', response_model=User)
def get_users_current(token: str = Depends(token_auth_scheme)) -> User:
    """
    return the authenticated user
    """
    user_id = verified_user_id(token)
    with Session(engine) as session:
        return session.get(User, user_id)





@app.delete('/users/{user_id}')
def delete_users_user_id(token: str = Depends(token_auth_scheme),
                         user_id: str = Path(...)):
    """
    Delete specified user
    """
    token_user_id = verified_user_id(token)
    if int(token_user_id) != int(user_id):
        raise HTTPException(status_code=401, detail="Authenticated user does not match the requested user_id")
    
    with Session(engine) as session:
        user = session.get(User, user_id)
        session.exec(delete(TeamMember).where(TeamMember.user_id == user_id))
        session.exec(delete(ApiKey).where(ApiKey.user_id == user_id))
        session.exec(delete(Team).where(Team.name == user.username))
        session.delete(user)
        session.commit()

