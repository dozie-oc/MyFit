from fastapi import FastAPI

from .database import create_db_and_tables
from .routers.foods import router as foods_router
from .routers.meals import router as meals_router

app = FastAPI()

create_db_and_tables

app.include_router(foods_router)
app.include_router(meals_router)
