from fastapi import APIRouter, HTTPException, status, Request, Depends
from passlib.context import CryptContext
from database import get_neo4j_driver
from controllers.auth_controller import UserRole, get_current_user_role

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Create user
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

# GET one user
@router.get("/getone")
async def get_user(request: Request, user_role: UserRole = Depends(get_current_user_role)):
    if user_role != UserRole.ADMINISTRATOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can perform this action")
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

#GET all users
@router.get("/getall")
async def get_all_users(user_role: UserRole = Depends(get_current_user_role)):
    if user_role != UserRole.ADMINISTRATOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can perform this action")
    with get_neo4j_driver().session() as session:
        result = session.run("MATCH (u:User) RETURN u.username AS username, u.role AS role")
        users = []
        for record in result:
            users.append({
                "username": record["username"],
                "role": record["role"]
            })
    return users

# User Searchbar backend
@router.get("/search")
async def search_users(request: Request, user_role: UserRole = Depends(get_current_user_role)):
    if user_role != UserRole.ADMINISTRATOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can perform this action")
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

#Update user role
@router.put("/update")
async def update_user(request: Request, user_role: UserRole = Depends(get_current_user_role)):
    if user_role != UserRole.ADMINISTRATOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can perform this action")
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

# Delete User
@router.delete("/delete")
async def delete_user(request: Request, user_role: UserRole = Depends(get_current_user_role)):
    if user_role != UserRole.ADMINISTRATOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can perform this action")
    form_data = await request.form()
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