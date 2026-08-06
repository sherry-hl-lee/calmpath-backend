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

## Bundled refuge data

The backend-ready refuge candidate snapshot is provided with the project at
`app/data/refuge_candidates.csv`. It contains the CSV header and 38 refuge
candidate records used by the nearby refuge feature.

The snapshot comes from the Shogo backend CSV data package:

- Data contract version: `2.0.0`
- Pipeline run: `validation_20260805T034000Z`
- Related source: City of Melbourne Open Data, including the landmarks and
  places of interest dataset
- Source page: <https://data.melbourne.vic.gov.au/explore/dataset/landmarks-and-places-of-interest-including-schools-theatres-health-services-spor/>

When redistributing or presenting derived data, retain appropriate City of
Melbourne Open Data attribution and follow the applicable CC BY licence terms
for the source dataset. The bundled CSV is development data and is not a
secret or an API credential.

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
