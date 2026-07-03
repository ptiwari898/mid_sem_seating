from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="SIRT Seating API")


@app.get("/")
async def root():
    return JSONResponse({"message": "SIRT seating project - minimal API. See README for deployment options."})


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})
