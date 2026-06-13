import traceback
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from db.database import init_db
from routes import patients, record, search

load_dotenv()

app = FastAPI(title="Clinical AI Assistant")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f"\n[ERROR] {request.method} {request.url}\n{tb}", flush=True)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


init_db()

app.include_router(patients.router)
app.include_router(record.router)
app.include_router(search.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_spa():
    return FileResponse("static/index.html")


@app.get("/patients")
def serve_patients():
    return FileResponse("static/index.html")


@app.get("/patients/{patient_id}")
def serve_patient_detail(patient_id: int):
    return FileResponse("static/index.html")
