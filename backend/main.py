import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from k8s_client import create_namespace, list_namespaces, delete_namespace
from models import NamespaceRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="K8s Platform Self-Service Portal",
    description="Provision Kubernetes namespaces with quotas and RBAC",
    version="1.0.0"
)

# Origins allowed to call this API. Defaults to "*" for local/dev use, but
# should be set to the portal's actual origin(s) in any real deployment via
# the ALLOWED_ORIGINS env var (comma-separated list).
_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*")
allow_origins = ["*"] if _allowed_origins == "*" else [
    origin.strip() for origin in _allowed_origins.split(",") if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


class NamespaceRequestBody(BaseModel):
    team_name:     str
    environment:   str
    cpu_limit:     str = "4"
    memory_limit:  str = "8Gi"
    owner_email:   str
    requested_by:  str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/namespaces")
def provision_namespace(body: NamespaceRequestBody):
    if body.environment not in ["dev", "staging", "prod"]:
        raise HTTPException(status_code=400, detail="environment must be dev, staging, or prod")
    req = NamespaceRequest(**body.model_dump())
    try:
        result = create_namespace(req)
        return result
    except Exception as e:
        logger.error(f"Failed to create namespace: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/namespaces")
def get_namespaces():
    try:
        return [vars(ns) for ns in list_namespaces()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/namespaces/{name}")
def remove_namespace(name: str):
    try:
        result = delete_namespace(name)
    except Exception as e:
        logger.error(f"Failed to delete namespace {name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Namespace not found")
    return result