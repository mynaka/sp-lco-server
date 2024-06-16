from fastapi import APIRouter, HTTPException, status, Depends, Header
from fastapi.security import HTTPBasicCredentials
from database import get_neo4j_driver
from jose import jwt
from jose.exceptions import JWTError
from passlib.context import CryptContext

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Get session token
def get_token(authorization: str = Header(...)):
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    token = authorization.split("Bearer ")[1]
    return token

# Decode and validate token
def decode_token(token: str):
    try:
        decoded_token = jwt.decode(token, "SECRET_KEY", algorithms=["HS256"])
        return decoded_token
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# Authenticate user credentials
def authenticate_user(username: str, password: str):
    with get_neo4j_driver().session() as session:
        result = session.run(
            "MATCH (u:User {username: $username}) RETURN u.password AS password, id(u) AS id",
            username=username,
        )
        record = result.single()
        if record and pwd_context.verify(password, record["password"]):
            return record["id"]
        else:
            return None

# Create JWT Token
def create_access_token(data: dict):
    return jwt.encode(data, "SECRET_KEY", algorithm="HS256")

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

# Dependency to get current user's ID
def get_current_user(token: str = Depends(get_token)):
    decoded_token = decode_token(token)
    return decoded_token["id"]
