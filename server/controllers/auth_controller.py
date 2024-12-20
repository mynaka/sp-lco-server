from fastapi import APIRouter, Form, HTTPException, status
from passlib.context import CryptContext

from utils.auth import *

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Login
@router.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    user_id = authenticate_user(username, password)
    if user_id:
        access_token = create_access_token({"username": username, "id": user_id})
        return {"access_token": access_token, "token_type": "bearer"}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
