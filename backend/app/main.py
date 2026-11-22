import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth
from app.api.v1.camunda_workflow import router as camunda_workflow_router
from app.api.v1.ingestion import router as ingestion_router
from app.core.config import settings

app = FastAPI(title="Support Resolution Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exposed as /api/auth/login and /api/auth/me
app.include_router(auth.router, prefix="/api")

# WP 02 Ingestion — DAT 01-03
app.include_router(ingestion_router)

# CRM-44 Camunda BPMN Intent Routing & Process Status
app.include_router(camunda_workflow_router)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
