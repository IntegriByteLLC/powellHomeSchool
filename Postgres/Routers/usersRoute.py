import os
import jwt
from datetime import datetime, timedelta

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from uuid import UUID

import bcrypt

from pydantic import BaseModel
import secrets

from Postgres.databaseConnection import get_db
from Postgres.models import User
from Postgres.schemas import UserCreate

router = APIRouter(prefix="/users", tags=["Users"])



JWT_SECRET = os.getenv("JWT_SECRET", "CzOe6Pr8HYsOT")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 60

def hash_password(raw_password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(raw_password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(raw_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(raw_password.encode('utf-8'), hashed_password.encode('utf-8'))



class LoginRequest(BaseModel):
    username: str
    password: str

from sqlalchemy.future import select

@router.post("/signup")
async def signup(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Email already in use")

    db_user = User(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        password_hash=hash_password(user.password),
        role="user"
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    return {"message": "Signup successful"}


@router.post("/signin")
async def signin(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    }
    jwt_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return {
        "token": jwt_token,
        "entityKey": str(user.id),
        "role": user.role,
        "grade": user.grade
    }
