from fastapi import APIRouter, HTTPException, status, Request
from passlib.context import CryptContext
from database import get_neo4j_driver

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/create")
async def create_user(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    role = form_data.get("role")

    # Connect to Neo4j database
    with get_neo4j_driver().session() as session:
        # Check if user already exists
        result = session.run("MATCH (u:User {username: $username}) RETURN u", username=username)
        if result.single():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

        # Hash the password
        hashed_password = pwd_context.hash(password)

        # Create user node in Neo4j
        session.run(
            "CREATE (u:User {username: $username, password: $password, role: $role})",
            username=username,
            password=hashed_password,
            role=role
        )

    return {"message": "User created successfully"}
