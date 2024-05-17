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

@router.get("/getone")
async def get_user(request: Request):
    form_data = await request.form()
    user_id = form_data.get("id")
    try:
        user_id = int(user_id)
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User ID is required")
        
    
    with get_neo4j_driver().session() as session:
        result = session.run("MATCH (u:User) WHERE id(u) = $id RETURN u.username AS username, u.role AS role", id=user_id)
        record = result.single()
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        user = {
            "username": record["username"],
            "role": record["role"]
        }

    return user

@router.get("/getall")
async def get_all_users():
    with get_neo4j_driver().session() as session:
        result = session.run("MATCH (u:User) RETURN u.username AS username, u.role AS role")
        users = []
        for record in result:
            users.append({
                "username": record["username"],
                "role": record["role"]
            })
    return users

@router.get("/search")
async def search_users(request: Request):
    form_data = await request.form()
    search_query = form_data.get("search")

    with get_neo4j_driver().session() as session:
        result = session.run(
            "MATCH (u:User) WHERE u.username CONTAINS $search_query RETURN u.username AS username, u.role AS role", search_query=search_query
        )
        users = []
        for record in result:
            users.append({
                "username": record["username"],
                "role": record["role"]
            })

    return users


@router.put("/update")
async def update_user(request: Request):
    form_data = await request.form()
    user_id = form_data.get("id")
    user_new_role = form_data.get("new_role")

    try:
        user_id = int(user_id)
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User ID is required")

    with get_neo4j_driver().session() as session:
        result = session.run("MATCH (u:User) WHERE id(u) = $id RETURN u", id=user_id)
        if not result.single():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        session.run(
            "MATCH (u:User WHERE id(u) = $id) SET u.role = $new_role", id=user_id, new_role=user_new_role
        )

    return {"message": "User updated successfully"}

@router.delete("/delete")
async def delete_user(request: Request):
    form_data = await request.form()
    user_id = form_data.get("id")
    
    try:
        user_id = int(user_id)
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User ID is required")
    
    with get_neo4j_driver().session() as session:
        result = session.run("MATCH (u:User) WHERE id(u) = $id RETURN u", id=user_id)
        if not result.single():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        session.run("MATCH (u:User) WHERE id(u) = $id DELETE u", id=user_id)

    return {"message": "User deleted successfully"}