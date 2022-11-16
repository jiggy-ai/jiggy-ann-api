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
from sqlmodel import Session, select, or_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound
from threading import Thread
import hnswlib
import psutil
from decimal import Decimal
import jwt
from string import ascii_lowercase
from random import sample

from main import app, engine #, token_auth_scheme, optional_token_auth_scheme, get_user_by_auth0_id

from models import *



def create_api_user(username, email=None):
    """
    Create a new user via API.  
    Returns the new user database object
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
