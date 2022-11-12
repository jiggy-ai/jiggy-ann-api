# Jiggy API
# Copyright (C) 2022 William S. Kish
#

from __future__ import annotations

from typing import List, Optional

from pydantic import conint

from fastapi import FastAPI, Path, Query, HTTPException, UploadFile, File, Depends
from fastapi.security import HTTPBearer 
from fastapi.routing import APIRouter
from fastapi.responses import Response
from time import time
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3 import Retry
from retrying import retry
import os
#from auth import verify_token, Auth0Session
from sqlmodel import Session, create_engine, SQLModel, select
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound
from datetime import datetime
#from auth import verified_user_id

from models import *



db_host = os.environ['JIGGY_POSTGRES_HOST']
user = os.environ['JIGGY_POSTGRES_USER']
passwd = os.environ['JIGGY_POSTGRES_PASS']
DBURI = 'postgresql+psycopg2://%s:%s@%s:5432/jiggy' % (user, passwd, db_host)
engine = create_engine(DBURI, pool_pre_ping=True, echo=False)


token_auth_scheme = HTTPBearer()
optional_token_auth_scheme = HTTPBearer(auto_error=False)


#auth0session = Auth0Session()


app = FastAPI(
    title='jiggy-api',
    version='0.0',
    summary='Jiggy Vector API',
    description='',
    contact={},
    servers=[{'url': 'https://api.jiggy.ai/jiggy-v0'}],
)

# make app appear under /cofounderhiking-v0"
if 'STAGING' in os.environ:
    app.mount("/jiggy-staging-v0", app)
    API_PATH = "jiggy-staging-v0"
else:
    app.mount("/jiggy-v0", app)
    API_PATH = "jiggy-v0"    




    
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


# import endpoints
import collection
import vector
import index
import apikey





