
from fastapi import HTTPException
import jwt
import os
from sqlmodel import Session, select, or_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound

from main import engine

from models import *

DOMAIN = "auth.jiggy.ai"
API_AUDIENCE = "https://api.jiggy.ai"
ALGORITHMS = ["RS256"]
ISSUER = "https://"+DOMAIN+"/"

jwks_url = 'https://%s/.well-known/jwks.json' % DOMAIN
jwks_client = jwt.PyJWKClient(jwks_url)



JWT_RSA_PUBLIC_KEY = os.environ['JIGGY_JWT_RSA_PUBLIC_KEY']
JWT_ISSUER = "Jiggy.AI"



def verify_jiggy_api_token(token):
    """Perform Jiggy API token verification using PyJWT.  raise HTTPException on error"""

    # This gets the 'kid' from the passed token
    try:
        signing_key = JWT_RSA_PUBLIC_KEY
    except jwt.exceptions.PyJWKClientError as error:
        raise HTTPException(status_code=401, detail=str(error))
    except jwt.exceptions.DecodeError as error:
        raise HTTPException(status_code=401, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=401, detail=str(error))
    
    try:
        payload = jwt.decode(token,
                             signing_key,
                             algorithms=ALGORITHMS,
                             issuer=JWT_ISSUER)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
    return payload

    
def verify_auth0_token(token):
    """Perform auth0 token verification using PyJWT.  raise HTTPException on error"""
    # This gets the 'kid' from the passed token
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
    except jwt.exceptions.PyJWKClientError as error:
        raise HTTPException(status_code=401, detail=str(error))
    except jwt.exceptions.DecodeError as error:
        raise HTTPException(status_code=401, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=401, detail=str(error))
    
    try:
        payload = jwt.decode(token,
                             signing_key,
                             algorithms=ALGORITHMS,
                             audience=API_AUDIENCE,
                             issuer=ISSUER)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
    return payload



def verified_user_id(token):
    """
    verify the supplied token and return the associated user_id
    """
    try:
        # first see if it is a token we issued from an API key
        user_id = verify_jiggy_api_token(token.credentials)['sub']
    except:
        # check if it is an auth0-issued token
        token_payload = verify_auth0_token(token.credentials)
        auth0_id = token_payload['sub']
        with Session(engine) as session:
            statement = select(User).where(User.auth0_id == auth0_id)
            user_id = session.exec(statement).first().id
    return user_id


user_teams = {}   # XXX expiring dict or a real cache

def verified_user_id_teams(token):
    """
    verify the supplied token and return the associated user id and list of the user's teams_ids
    """
    user_id = verified_user_id(token)
    # XXX cache team ids, or put them in the jwt?
    if user_id in user_teams:
        return user_id, user_teams[user_id]
    with Session(engine) as session:        
        statement = select(TeamMember).where(TeamMember.user_id == user_id)
        team_ids = [m.team_id for m in session.exec(statement)]
    user_teams[user_id] = team_ids
    return user_id, team_ids




    





###
### Auth0 Management API CLIENT
###

"""
JIGGY_AUTH0_API_URL = os.environ["JIGGY_AUTH0_API_URL"]
JIGGY_AUTH0_CLIENT_ID = os.environ["JIGGY_AUTH0_CLIENT_ID"]
JIGGY_AUTH0_CLIENT_SECRET = os.environ["JIGGY_AUTH0_CLIENT_SECRET"]
"""

access_token = None

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3 import Retry
from retrying import retry

auth0session = requests.session()
auth0session.mount('https://', HTTPAdapter(max_retries=Retry(connect=5,
                                                         read=5,
                                                         status=5,
                                                         redirect=2,
                                                         backoff_factor=.001,
                                                         status_forcelist=(500, 502, 503, 504))))




class Auth0Session(requests.Session):
    def __init__(self, *args, **kwargs):
        super(Auth0Session, self).__init__(*args, **kwargs)
        self.__authenticate__()
        
    def __authenticate__(self):
        payload = {"client_id"     : JIGGY_AUTH0_CLIENT_ID,
                   "client_secret" : JIGGY_AUTH0_CLIENT_SECRET,
                   "audience"      : JIGGY_AUTH0_API_URL,
                   "grant_type"    : "client_credentials"}
        resp = auth0session.post("https://cofounder-hiking.us.auth0.com/oauth/token", json=payload)
        assert(resp.status_code == 200)
        access_token = resp.json()['access_token']
        self.headers.update({"authorization": "Bearer %s" % access_token})

    @retry(stop_max_attempt_number=3)
    def request(self, method, url, *args, **kwargs):
        if url[0] == '/':
            url = url[1:]
        url =  JIGGY_AUTH0_API_URL + url
        resp = super(Auth0Session, self).request(method, url, *args, **kwargs)
        if resp.status_code == 401:
            self.__authenticate__()
            raise Exception("Unauthorized")
        #print(resp.json())
        return resp


                 
