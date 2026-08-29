from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import create_db_and_tables

from .auth.router import router as auth_router

from .routers.meals import router as meals_router
from .routers.exercises import router as exercises_router
from .routers.habits import router as habits_router
from .routers.weight import router as weight_router
from .routers.daily_summary import router as summary_router


@asynccontextmanager
async def lifespan(app: FastAPI):

    create_db_and_tables()

    yield


app = FastAPI(
    title="Fitness Tracker API",
    version="1.0.0",
    lifespan=lifespan
)


app.include_router(auth_router)

app.include_router(meals_router)
app.include_router(exercises_router)
app.include_router(habits_router)
app.include_router(weight_router)
app.include_router(summary_router)


@app.get("/")
def root():
    return {
        "message": "Fitness Tracker API is running"
    }