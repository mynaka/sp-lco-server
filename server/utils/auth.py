import os
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError
from passlib.context import CryptContext
from database import get_neo4j_driver
from fastapi import Depends, HTTPException, Header, status

# Initialize password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable not set")

def get_token(authorization: str = Header(...)):
    """Get session token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    token = authorization.split("Bearer ")[1]
    return token

# Decode and validate token
def decode_token(token: str):
    """Decode token for authorization"""
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded_token
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# Authenticate user credentials
def authenticate_user(username: str, password: str):
    """Check if given credentials are correct."""
    with get_neo4j_driver().session() as session:
        result = session.run(
            "MATCH (u:User {username: $username}) RETURN u.password AS password, elementId(u) AS id",
            username=username,
        )
        record = result.single()
        if record and pwd_context.verify(password, record["password"]):
            return record["id"]
        else:
            return None

def create_access_token(data: dict):
    """Create access token for session"""
    return jwt.encode(data, SECRET_KEY, algorithm="HS256")

def get_current_user(token: str = Depends(get_token)):
    """Get currently logged in user"""
    decoded_token = decode_token(token)
    return decoded_token["id"]
