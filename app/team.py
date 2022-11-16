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
from auth import verified_user_id
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

from s3 import  create_presigned_url, bucket

from main import app, engine, token_auth_scheme
from auth import verified_user_id_teams

from models import *


JWT_RSA_PUBLIC_KEY = os.environ['JIGGY_JWT_RSA_PUBLIC_KEY']
JWT_RSA_PRIVATE_KEY = os.environ['JIGGY_JWT_RSA_PRIVATE_KEY']
JWT_ISSUER = "Jiggy.AI"

@app.get('/teams')
def get_teams(token: str = Depends(token_auth_scheme)) -> UserTeams:
    """
    return all of the user's teams
    """
    user_id, user_team_ids = verified_user_id_teams(token)
    with Session(engine) as session:    
        items = []
        for team_id in user_team_ids:
            items.append(session.get(Team, team_id))
        return UserTeams(items = items)
    
              
@app.post('/team', response_model=Jwt)
def post_team(token: str = Depends(token_auth_scheme),
              body: TeamPostRequest = ...) -> Team:
    """
    Create a Team
    """
    user_id, user_team_ids = verified_user_id_teams(token)
    with Session(engine) as session:    
        statement = select(Team).where(Team.name == body.name)
        if list(session.exec(statement)):
            raise HTTPException(status_code=409, detail="The specified team name is not available.")
        
        team = Team(name=body.name, description=body.description)
        session.add(team)
        session.commit()
        session.refresh(team)

        member = TeamMember(team_id=team.id,
                            user_id=user_id,
                            invited_by=user_id,
                            role=TeamRole.admin,
                            accepted=True)
        
        session.add(member)
        session.commit()


@app.delete('/team/{team_id}')
def delete_team(token: str = Depends(token_auth_scheme),
                team_id: str = Path(...)):
    user_id, user_team_ids = verified_user_id_teams(token)
    with Session(engine) as session:
        team = session.get(Team, team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        #XXX
        
    
        
@app.post('/team/{team_id}/member')
def post_team_member(token: str = Depends(token_auth_scheme),
                     team_id: str = Path(...),
                     body: TeamMemberPostRequest = ...) -> TeamMember:

    user_id, user_team_ids = verified_user_id_teams(token)
    with Session(engine) as session:    
        team = session.get(Team, team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        # verify calling user is a member of the specified team
        statement = select(Team).where(TeamMember.user_id == user_id, TeamMember.team_id == team_id)
        user_member = session.exec(statement)
        if not user_member:
            raise HTTPException(status_code=404, detail="Team not found")

        # verify user has sufficient permissions to add new user 
        if user_member.role not in [TeamRole.admin, TeamRole.member]:
            raise HTTPException(status_code=409, detail="Insufficient permissions to add member to the specified team.")

        # verify new user exists
        new_user = session.get(User, body.user_id)
        if not new_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Verify new user is not already a member of the team
        statement = select(TeamMember).where(TeamMember.user_id == body.user_id, TeamMember.team_id == team_id)
        if list(session.exec(statement)):
            raise HTTPException(status_code=409, detail="User is already a member of the specified team.") 
        
        new_member = TeamMember(team_id=team.id,
                                user_id=body.user_id,
                                invited_by=user_id,
                                role=TeamRole.admin,
                                accepted=True)        
        session.add(new_member)
        session.commit()
        return new_member


@app.delete('/team/{team_id}/member/{member_id}')
def delete_team_member(token: str = Depends(token_auth_scheme),
                       team_id: str = Path(...),
                       member_id: str = Path(...)):
    """
    remove  the specified member from the team
    """
    user_id = verified_user_id(token)        
    with Session(engine) as session:    
        team = session.get(Team, team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # verify calling user is a member of the specified team
        statement = select(Team).where(TeamMember.user_id == user_id, TeamMember.team_id == team_id)
        user_member = session.exec(statement)
        if not user_member:
            raise HTTPException(status_code=404, detail="Team not found")  

        # get user membership entry that is the target of the request
        target_member = session.get(TeamMember, member_id)

        # determine if the requesting user is the target of the membership entry
        requesting_user_is_target = target_member.user_id == user_id
    
        # determine if the requesting user is an admin of the target collection
        requesting_user_is_admin = user_member.role == TeamRole.admin
    
        # reject the delete operation unless the requesting user is the target of the entry (removing himself from the collection)
        # or an admin of the target collection
        if not requesting_user_is_target and not requesting_user_is_admin:
            raise HTTPException(status_code=403, detail="Insufficient permission.")

        # prevent removal of admin unless there is another admin specified for the team
        if requesting_user_is_target and user_member.role == TeamRole.admin:
            statement = select(TeamMember).where(TeamMember.role == TeamRole.admin, TeamMember.team_id == team_id)
            num_admins = len(session.exec(statement))
        if num_admins == 1:
            raise HTTPException(status_code=403, detail="Team admin must designate another admin before removal.")
        session.delete(target_member)
        
    
        
