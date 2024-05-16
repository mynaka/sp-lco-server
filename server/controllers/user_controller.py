from fastapi import APIRouter, HTTPException, status, Request
from passlib.context import CryptContext

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/create")
async def create_user(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    role = form_data.get("role")

    if username in users_db:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")
    
    hashed_password = pwd_context.hash(password)
    new_user = User(username=username, password=hashed_password, role=role)
    users_db[username] = new_user
    
    return {"message": "User created successfully"}
