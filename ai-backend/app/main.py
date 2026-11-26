from fastapi import FastAPI

app = FastAPI(
    title="MADA - MuleSoft AI Developer Assistant",
    description="AI-powered assistant for MuleSoft developers",
    version="0.1.0"
)

@app.get("/")
async def root():
    return {
        "application": "MADA",
        "message": "MuleSoft AI Developer Assistant is running"
    }

@app.get("/health")
async def health():
    return {
        "application": "MADA",
        "status": "healthy",
        "version": "0.1.0"
    }
