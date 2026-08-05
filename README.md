# CalmPath Backend

FIT5120 CalmPath backend service.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open the FastAPI documentation at `http://127.0.0.1:8000/docs`.

## Current scope

The first backend feature is the sensory refuge search User Story.

## Project structure

```text
app/
  api/routes/    HTTP endpoints
  schemas/       request and response data models
  services/      business logic
  models/        database models
tests/           automated tests
docs/api/        short API contracts
```
