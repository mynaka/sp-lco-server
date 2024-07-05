from fastapi import APIRouter, HTTPException, status, Request, Depends
from passlib.context import CryptContext
from database import get_neo4j_driver
from controllers.auth_controller import get_current_user

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Create user
@router.post("/create")
async def create_user(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")

    with get_neo4j_driver().session() as session:
        # Check if user already exists
        result = session.run("MATCH (u:User {username: $username}) RETURN u", username=username)
        if result.single():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

        # Hash the password
        hashed_password = pwd_context.hash(password)

        # Create user node in Neo4j
        session.run(
            "CREATE (u:User {username: $username, password: $password})",
            username=username,
            password=hashed_password,
        )

    return {"status": 200, "user": [username, password]}

# GET one user
@router.get("/getone")
async def get_user(request: Request, current_user: dict = Depends(get_current_user)):
    form_data = await request.form()
    user_id = form_data.get("id")
    try:
        user_id = int(user_id)
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User ID is required")
        
    with get_neo4j_driver().session() as session:
        result = session.run("MATCH (u:User) WHERE id(u) = $id RETURN u.id AS id, u.username AS username", id=user_id)
        record = result.single()
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        user = {
            "id": record["id"],
            "username": record["username"],
        }

    return user

# GET all users
@router.get("/getall")
async def get_all_users(current_user: dict = Depends(get_current_user)):
    with get_neo4j_driver().session() as session:
        result = session.run("MATCH (u:User) RETURN id(u) AS id, u.username AS username")
        users = []
        for record in result:
            users.append({
                "id": record["id"],
                "username": record["username"],
            })
    return users

# User Searchbar backend
@router.get("/search")
async def search_users(request: Request, current_user: dict = Depends(get_current_user)):
    form_data = await request.form()
    search_query = form_data.get("search")

    with get_neo4j_driver().session() as session:
        result = session.run(
            "MATCH (u:User) WHERE u.username CONTAINS $search_query RETURN id(u) AS id, u.username AS username", search_query=search_query
        )
        users = []
        for record in result:
            users.append({
                "id": record["id"],
                "username": record["username"],
            })

    return users

# Delete User
@router.delete("/delete")
async def delete_user(request: Request, current_user: dict = Depends(get_current_user)):
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
