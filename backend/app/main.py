from fastapi import FastAPI

from app.api.v1 import auth

app = FastAPI(title="Support Resolution Copilot API")

# Exposed as /api/auth/login and /api/auth/me
app.include_router(auth.router, prefix="/api")
