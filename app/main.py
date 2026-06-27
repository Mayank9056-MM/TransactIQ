from fastapi import FastAPI

app = FastAPI(
    title="TransactIQ",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

@app.get("/")
def health():
    return {
        "status": "healthy",
        "service": "TransactIQ"
    }