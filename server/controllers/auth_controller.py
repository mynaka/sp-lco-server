from fastapi import APIRouter, HTTPException, status
from fastapi.security import HTTPBasicCredentials
from passlib.context import CryptContext

from utils.auth import *

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Login
@router.post("/login")
async def login(credentials: HTTPBasicCredentials):
    user_id = authenticate_user(credentials.username, credentials.password)
    if user_id:
        access_token = create_access_token({"username": credentials.username, "id": user_id})
        return {"access_token": access_token, "token_type": "bearer"}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
