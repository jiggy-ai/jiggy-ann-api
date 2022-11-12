from typing import Optional, List

from sqlmodel import Field, SQLModel, Column, ARRAY, Float, Enum
from pydantic import EmailStr, BaseModel, ValidationError, validator
from array import array
from pydantic import condecimal
import json
from time import time
import enum
import re

timestamp = condecimal(max_digits=14, decimal_places=3)

ALLOWED_NAME = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)   # REGEX for valid Name, based on DNS name component requirements

def _is_valid_namestr(checkstr, display):
    """
    validate the checkstring is a valid name per DNS name rules.
    raises ValueError if the checkstring is invalid.
    Will refer to the name as type "display" in the error messages to accomodate different field names using this validator
    """
    if len(checkstr) > 64 or not checkstr:
        raise ValueError('"%s" is an invalid %s. It must not be empty and is limited to 64 characters.' % (checkstr, display))
    elif not bool(ALLOWED_NAME.match(checkstr)):
        raise ValueError('"%s" is an invalid %s. It can only contain letters, numbers, and hyphens, and must not start or end with a hyphen.' % (checkstr, display))


    
###
##  Collection
###

class Collection(SQLModel, table=True):
    
    id: int = Field(default=None,
                    primary_key=True,
                    description='Unique identifier for a particular collection.')

    name:  str = Field(index=True, description="The Collection's unique name within the team context.")
    
    dimension: int         = Field(default= 0, index=True, description="The dimension of the vectors in this collection.")
    team_id:   int         = Field(None, index=True, description="The team that this collection is associated with.")
    count: int             = Field(default=0, description="The number of vectors in the collection")
    created_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the collection was created.')
    updated_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the collection was updated.')

    @validator('name')
    def _name(cls, v):
        _is_valid_namestr(v, 'name')
        return v

class CollectionPostRequest(BaseModel):
    
    name:   str = Field(description="The Collection's unique name within the team context.")
    team_id: Optional[int]  = Field(default=None, description="The team that this collection is associated with. If unspecified will use the users default team.")
    @validator('name')
    def _name(cls, v):
        _is_valid_namestr(v, 'name')
        return v

class CollectionsGetResponse(BaseModel):
    items: List[Collection] = Field(..., description='List of collections owned by the callers team_id')

 




###
##    Vector
### 

    
class Vector(SQLModel, table=True):
    id: int = Field(default=None,
                    primary_key=True,
                    description='Unique database identifier for a given vector. This is not the user-supplied identifier')

    collection_id: int = Field(index=True,
                               foreign_key="collection.id",
                               description='The collection that this vector belongs to.')

    created_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the vector was created.')
    
    vector: List[float] = Field(sa_column=Column(ARRAY(Float(24))), description='The user-supplied vector element.')
    vector_id:  int     = Field(index=True, description='The user-supplied id for this vector element.')


class  VectorPostRequest(BaseModel):
    vector: List[float] = Field(description='The user-supplied vector element.')

    
class VectorResponse(BaseModel):
    collection_id: int = Field(description='The collection that this vector belongs to.')
    created_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the vector was created.')
    
    vector: List[float] = Field(description='The user-supplied vector element.')
    vector_id:  int     = Field(description='The user-supplied id for this vector element.')

    

###
##   Index
###


class IndexLibraries(str, enum.Enum):
    """
    The library used to create the index.
    Currently only 'hnswlib' is supported.
    """
    hnswlib = 'hnswlib'


class DistanceMetric(str, enum.Enum):
    """
    The distance metric to use for the nearest neighbor index.
    """
    cosine = 'cosine'
    ip     = 'ip'
    l2     = 'l2'

class IndexBuildState(str, enum.Enum):
    prep = "preparing data"
    indexing = "indexing vectors"
    saving = "saving index"
    complete = "index complete"
    failed = "indexing failure"
    
    
class Index(SQLModel, table=True):

    id: int = Field(default=None,
                    primary_key=True,
                    description='Unique database identifier for a given index')

    tag:  str = Field(index=True, description="User tag for this Index.  Uniquely identifies an index in the context of a collection.")
    name: str = Field(description="The full name for this index in the form of TEAM_NAME/COLLECTION_NAME:TAG")
    
    collection_id:  int = Field(foreign_key="collection.id", description='The collection used to build this index')
    
    target_library:    IndexLibraries = Field(sa_column=Column(Enum(IndexLibraries)))
    metric:            DistanceMetric = Field(sa_column=Column(Enum(DistanceMetric)))
    
    hnswlib_M:  int   = Field(default=None, ge=2, description="The M value passed to hnswlib when creating the index.")
    hnswlib_ef: int   = Field(default=None, ge=10, description="The ef_construction value passed to hnswlib when creating the index.")
    
    count: int = Field(default=0, description="The number of vectors included in the index.  The number of vectors in the collection at the time of index build.")
    
    created_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the index was requested to be created.')
    state: IndexBuildState = Field(sa_column=Column(Enum(IndexBuildState)))
    completed_at: timestamp = Field(description='The epoch timestamp when the index build was completed.')
    build_status: str     = Field(description='Informational status message for the index build.')
    objkey: str = Field(description='The index key name in object store')
        
    
    @validator('tag')
    def _tag(cls, v):
        _is_valid_namestr(v, 'tag')
        return v

class IndexRequest(BaseModel):
    tag: str = Field(default='latest', description="User tag for this Index.  Uniquely identifies an index in the context of a collection.")
    target_library:    IndexLibraries = Field(default=IndexLibraries.hnswlib, description="The library use to create the index")
    metric:     Optional[str] = Field(default='cosine', description='The distance metric ("space" in hnswlib): "cosine", "ip", or "l2"')
    hnswlib_M:  int  = Field(default=None, description="The M value passed to hnswlib when creating the index.")
    hnswlib_ef: int  = Field(default=None, description="The ef_construction value passed to hnswlib when creating the index")
    @validator('tag')
    def _tag(cls, v):
        _is_valid_namestr(v, 'tag')
        return v


class IndexResponse(BaseModel):
    id: int            = Field(description='Unique identifier for a given index.')
    collection_id: int = Field(description='The collection used to build this index')
    tag:  str = Field(description="User tag for this Index.  Uniquely identifies an index in the context of a collection.")
    name: str = Field(description="The full name for this index in the form of TEAM_NAME/COLLECTION_NAME:TAG")
    target_library:    IndexLibraries = Field(default=IndexLibraries.hnswlib, description="The library use to create the index")
    metric:        str = Field(description='The distance metric ("space" in hnswlib): "cosine", "ip", or "l2"')
    hnswlib_M:  Optional[int] = Field(default=None, description="The M value passed to hnswlib when creating the index.")
    hnswlib_ef: Optional[int]  = Field(default=None, description="The ef_construction value passed to hnswlib when creating the index.")
    count: int = Field(description="The number of vectors included in the index.  The number of vectors in the collection at the time of index build.")
    created_at: float = Field(description='The epoch timestamp when the index was requested to be created.')
    state: IndexBuildState = Field(description = "The current build status.")
    completed_at: float = Field(description='The epoch timestamp when the index build was completed.')
    build_status: str     = Field(description='Informational status message for the index build.')
    url: Optional[str] = Field(default=None, description='The url the index can be downloaded from.  The url is valid for a limited time.')



class CollectionsIndexGetResponse(BaseModel):
    items: List[IndexResponse] = Field(..., description='List of collection index')

 

###
##  IndexTest
###

class IndexTest(SQLModel, table=True):

    id: int = Field(default=None,
                    primary_key=True,
                    description='Unique database identifier for a given index test.')
    
    index_id: int = Field(foreign_key="index.id",
                          index=True,
                          description='Unique index under test.')

    test_k:     int  = Field(default=10, description="The number of nearest neighbors (k) to query for each test vector.")
    
    hnswlib_ef: int  = Field(default=None, description="The ef value passed to hnswlib when testing the index")
                               
    created_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the test was requested.')
    completed_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the index build was completed.')
    
    recall: Optional[float] = Field(default=0, description="The recall of the index.")
    qps:    Optional[float] = Field(default=0, description="The qps of the index.")
    



class HnswlibTestResult(BaseModel):
    index_id:    int = Field(description='Unique index under test.')    
    hnswlib_ef: int  = Field(default=None, description="The recall of the index.")
    recall:    float = Field(default=0, description="The qps of the index.")





    

    
class PendingVector(SQLModel, table=True):
    id: int = Field(default=None,
                    primary_key=True,
                    description='Unique identifier. This is not the user-supplied identifier')

    collection_id: int = Field(default=None,
                               index=True,
                               description='The collection that this vector belongs to.')

    created_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the vector was created.')
    
    vector: List[float] = Field(sa_column=Column(ARRAY(Float(24))), description='The user-supplied vector element')
    value:  int         = Field(index=True, description='The user-supplied identifier for this vector element')
    vector_id: int      = Field(index=True, description='The database vector_id for this vector element')

    

class CollectionBlob(SQLModel, table=True):
    id: int = Field(default=None,
                    primary_key=True,
                    description='Unique identifier for this blob')

    objkey: str = Field(description='The blob key name in object store')
    
    collection_id: int = Field(default=None,
                               index=True,
                               description='The collection that this vector blob belongs to.')
    

    

    

###
## API Key
###

class ApiKey(SQLModel, table=True):
    key: str = Field(primary_key=True,
                     description='Unique secret api key')
    user_id: int = Field(index=True, description='The user_id that owns this key.')
    description: Optional[str] = Field(default=None, description='Optional user supplied description of the key.')
    created_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the vector was created.')
    last_used : timestamp = Field(default_factory=time, description='The epoch timestamp when the key was last used to create a JWT.')
    

class  ApiKeyRequest(BaseModel):
    description: Optional[str] = Field(default=None, description='Optional user supplied description of the key.')


class AccountCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=39, description='The requested username.  This can not be changed.')
    email: Optional[EmailStr] = Field(description='Email address to allow API key request from unauthenticated source.')

    

class  ApiKeyResponse(BaseModel):
    key: str = Field(default=None, description='The api key.')
    description: Optional[str] = Field(default=None, description='Optional user supplied description of the key.')
    created_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the key was created.')
    last_used : timestamp = Field(default_factory=time, description='The epoch timestamp when the key was last used to create a JWT.')
    
    
class AuthRequest(BaseModel):
    key : str = Field(description = "The API key")
    
class Jwt(BaseModel):
    jwt: str = Field(description='The JWT to used as bearer token')


###
## User
###

class User(SQLModel, table=True):
    id: int = Field(primary_key=True, description="Internal user_id")
    username: str = Field(index=True, min_length=3, max_length=39, description='Unique name for the user.')
    auth0_userid : Optional[str] = Field(default=None, index=True, description='Auth0 userid.  This can be None for anonymous accounts created via api key')
    email : Optional[EmailStr] = Field(default=None, index=True, description='User-supplied email address if the user was anonymously created via api.')
    link_key: Optional[str] = Field(index=True, description='Key that is sent in email url to an unauthenticated user to enable them to eventually link an account to this key.')
    default_team_id: int = Field(description="The default team for this user")



###
## Team
###

class Team(SQLModel, table=True):
    id: int = Field(primary_key=True, description="Internal team id")
    name: str = Field(index=True, min_length=3, max_length=39, description='Unique name for this team.')
    description: Optional[str] = Field(default=None, description='Optional user supplied description.')
    created_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the team was created.')
    updated_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the team was updated.')


class TeamRole(str, enum.Enum):
    owner = 'owner'
    admin = 'admin'
    member = 'member'

    
class TeamMember(SQLModel, table=True):
    id: int = Field(primary_key=True, description="Internal membership id")
    team_id: int = Field(index=True, description="The team_id that the associated user is a member of.")
    user_id: int = Field(index=True, description="The user_id that is  a member of the associated team.")
    created_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the membership was created.')
    updated_at: timestamp = Field(default_factory=time, description='The epoch timestamp when the membership was updated.')
    invited_by: int = Field(index=True, description="The user that invited this member to the team.")
    role:  TeamRole = Field(sa_column=Column(Enum(TeamRole)), description="The user's role in the team")
    accepted: bool = Field(False, description='True if the user has accepted the team membership.')
