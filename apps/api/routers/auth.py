import datetime
import os
from typing import Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from apps.api.models.db import get_db_path

SECRET_KEY = os.getenv("JWT_SECRET", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + (expires_delta or datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def _get_user_by_email(email: str) -> Optional[dict]:
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,))
        row = await cursor.fetchone()
        await cursor.close()
    if row:
        return {"id": row[0], "email": row[1], "password_hash": row[2]}
    return None


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    existing = await _get_user_by_email(request.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    db_path = get_db_path()
    created_at = datetime.datetime.utcnow().isoformat()
    password_hash = hash_password(request.password)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (request.email, password_hash, created_at),
        )
        await db.commit()
    access_token = create_access_token({"sub": request.email})
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    user = await _get_user_by_email(request.email)
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access_token = create_access_token({"sub": user["email"]})
    return TokenResponse(access_token=access_token)
