from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBasicCredentials
from jose import jwt
from passlib.context import CryptContext
from typing import Dict

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# User model
class User:
    def __init__(self, username: str, password: str, role: str):
        self.username = username
        self.password = password
        self.role = role

# User database (in memory for demonstration purposes)
users_db: Dict[str, User] = {
    "user2": User(username="user2", password=pwd_context.hash("password2"), role="editor"),
    "admin": User(username="admin", password=pwd_context.hash("adminpassword"), role="administrator")
}

# Authentication
def authenticate_user(credentials: HTTPBasicCredentials):
    user = users_db.get(credentials.username)
    if not user or not pwd_context.verify(credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user

# Token generation
def create_access_token(data: dict):
    return jwt.encode(data, "SECRET_KEY")

# Routes
@router.post("/login")
async def login(credentials: HTTPBasicCredentials):
    user = authenticate_user(credentials)
    access_token = create_access_token({"username": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer", "type": user.role}

@router.get("/protected")
async def protected_route(user: User = Depends(authenticate_user)):
    return {"message": "This is a protected route for administrators"}
