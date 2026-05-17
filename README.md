# F1 Stats and Predictions Backend

This is the FastAPI backend for the F1 Stats and Predictions website.

## Features

- FastAPI backend server
- Driver standings API
- Current drivers API
- Race schedule API
- Pit stop prediction demo API
- External API integration with Jolpica and OpenF1

## Tech Stack

- Python
- FastAPI
- Uvicorn
- Requests

## Project Structure

```text
f1-backend/
├── main.py
├── requirements.txt
├── routers/
│   ├── standings.py
│   ├── races.py
│   ├── drivers.py
│   └── predictions.py
├── services/
│   ├── jolpica_client.py
│   └── openf1_client.py
└── README.md
API Routes
Route	Method	Description
/	GET	Backend health check
/api/standings/drivers	GET	Current F1 driver standings
/api/drivers/current	GET	Current F1 drivers
/api/races/schedule?year=2026	GET	F1 race schedule
/api/predict/pitstop-demo	POST	Demo pit stop prediction
Run Locally

Create virtual environment:

python -m venv .venv

Activate virtual environment:

.venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Run server:

python -m uvicorn main:app --reload

Backend will run at:

http://127.0.0.1:8000

API docs:

http://127.0.0.1:8000/docs
Render Deployment

Build command:

pip install -r requirements.txt

Start command:

uvicorn main:app --host 0.0.0.0 --port $PORT