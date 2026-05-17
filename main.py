from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import standings

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


@app.get("/")
def home():
    return {
        "message": "F1 Backend is running successfully"
    }