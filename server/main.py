from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from controllers.auth_controller import router as auth_router
from controllers.user_controller import router as user_router
from controllers.entry_controller import router as entry_router

app = FastAPI()

# TODO remove once you setup on a proper server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(user_router, prefix="/api/user")
app.include_router(entry_router, prefix="/api/entry")