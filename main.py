from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import standings, races, drivers, predictions, telemetry, circuits

app = FastAPI(title="F1 Stats and Predictions API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    standings.router,
    prefix="/api/standings",
    tags=["Standings"]
)

app.include_router(
    races.router,
    prefix="/api/races",
    tags=["Races"]
)

app.include_router(
    drivers.router,
    prefix="/api/drivers",
    tags=["Drivers"]
)

app.include_router(
    predictions.router,
    prefix="/api/predict",
    tags=["Predictions"]
)

app.include_router(
    telemetry.router,
    prefix="/api/telemetry",
    tags=["Telemetry"]
)

app.include_router(
    circuits.router,
    prefix="/api/circuits",
    tags=["Circuits"]
)


@app.get("/")
def home():
    return {
        "message": "F1 Backend is running successfully"
    }