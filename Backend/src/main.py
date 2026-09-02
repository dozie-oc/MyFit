from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.database import create_db_and_tables

from src.auth.router import router as auth_router

from src.routers.meals import router as meals_router
from src.routers.exercises import router as exercises_router
from src.routers.habits import router as habits_router
from src.routers.weight import router as weight_router
from src.routers.daily_summary import router as summary_router
from src.routers.foods import router as food_router


@asynccontextmanager
async def lifespan(app: FastAPI):

    create_db_and_tables()

    yield


app = FastAPI(
    title="Fitness Tracker API",
    version="1.0.0",
    lifespan=lifespan
)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)

app.include_router(meals_router)
app.include_router(exercises_router)
app.include_router(habits_router)
app.include_router(weight_router)
app.include_router(summary_router)
app.include_router(food_router)


@app.get("/")
def root():
    return {
        "message": "Fitness Tracker API is running"
    }