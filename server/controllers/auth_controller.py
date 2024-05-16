# controllers/auth_controller.py

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBasicCredentials
from database import get_neo4j_driver
from jose import jwt
from passlib.context import CryptContext

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Function to authenticate user credentials
def authenticate_user(username: str, password: str):
    session = get_neo4j_driver().session()
    with get_neo4j_driver().session() as session:
        result = session.run(
            "MATCH (u:User {username: $username}) RETURN u.password AS password",
            username=username,
        )
        record = result.single()
        if record and pwd_context.verify(password, record["password"]):
            return True
        else:
            return False

# Function to create JWT token
def create_access_token(data: dict):
    return jwt.encode(data, "SECRET_KEY")

# Login route
@router.post("/login")
async def login(credentials: HTTPBasicCredentials):
    if authenticate_user(credentials.username, credentials.password):
        access_token = create_access_token({"username": credentials.username})
        return {"access_token": access_token, "token_type": "bearer"}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
