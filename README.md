# Kubernetes Platform Self-Service Portal

![Build](https://github.com/ravishekharg/k8s-platform-portal/actions/workflows/build-push.yaml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Kubernetes](https://img.shields.io/badge/Kubernetes-Operator-blue?logo=kubernetes)
![FastAPI](https://img.shields.io/badge/API-FastAPI-green?logo=fastapi)

A production-grade Kubernetes platform portal enabling teams to
self-provision namespaces with ResourceQuotas, LimitRanges, and RBAC
— without manual intervention from platform engineers.

## Architecture

Developer → HTML Portal → FastAPI Backend → Kubernetes API
↓
kopf Operator watches
NamespaceRequest CRDs
↓
Creates: Namespace + ResourceQuota
+ LimitRange + RoleBinding

## Tech Stack

| Layer | Tool |
|-------|------|
| API | Python FastAPI |
| Operator | kopf (Kubernetes Operator Framework) |
| CRD | NamespaceRequest (platform.company.io/v1) |
| Frontend | Vanilla HTML/JS |
| Runtime | Kubernetes (EKS/GKE/any) |
| CI/CD | GitHub Actions → GHCR |

## What Gets Provisioned

Each namespace request automatically creates:
- **Namespace** with team/environment labels and owner annotations
- **ResourceQuota** — CPU, memory, pod, and service limits
- **LimitRange** — default container limits (prevents unbounded pods)
- **RoleBinding** — team group gets `edit` ClusterRole on the namespace

## Prerequisites

- A Kubernetes cluster (kind/minikube for local testing, or any EKS/GKE/AKS cluster) with `kubectl` configured against it
- Python 3.12+ (only needed if running the backend/operator outside of containers)
- Docker, if you want to build the backend/operator images locally instead of using the prebuilt GHCR images from CI

## Quick Start

```bash
# 1. Apply CRD and operator RBAC
kubectl create namespace platform-system
kubectl apply -f kubernetes/crd-namespacerequest.yaml
kubectl apply -f kubernetes/operator-rbac.yaml

# 2. Deploy the operator
kubectl apply -f kubernetes/operator-deployment.yaml

# 3. Run the backend API
# There is no Kubernetes Deployment/Service manifest for the backend yet
# (see backend/Dockerfile). For now, run it directly:
docker build -t platform-portal-backend backend/
docker run -p 8080:8080 platform-portal-backend
# or, without Docker:
cd backend && pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080

# 4. Open the portal
# frontend/index.html is a static file that talks to the backend at
# http://localhost:8080 (see the `API` constant near the top of its <script>).
# Serve or open it directly once the backend above is running.
open frontend/index.html
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/namespaces` | Provision a new namespace |
| GET | `/api/namespaces` | List all managed namespaces |
| DELETE | `/api/namespaces/{name}` | Decommission a namespace |
| GET | `/health` | Health check |

## Example API Call

```bash
curl -X POST http://localhost:8080/api/namespaces \
  -H "Content-Type: application/json" \
  -d '{
    "team_name":    "payments",
    "environment":  "dev",
    "cpu_limit":    "4",
    "memory_limit": "8Gi",
    "owner_email":  "payments-lead@company.com",
    "requested_by": "ravi"
  }'

# Response:
# {"namespace": "payments-dev", "status": "created"}
```

## Example CRD Usage (Operator path)

```yaml
apiVersion: platform.company.io/v1
kind: NamespaceRequest
metadata:
  name: payments-dev-request
spec:
  teamName:     payments
  environment:  dev
  cpuLimit:     "4"
  memoryLimit:  8Gi
  ownerEmail:   payments-lead@company.com
```

```bash
kubectl apply -f namespace-request.yaml
# Operator auto-provisions namespace within seconds

kubectl get nsr   # short name for NamespaceRequest
kubectl get ns payments-dev
```

## Project Structure

```
backend/     FastAPI service — REST API for provisioning/listing/deleting namespaces
  main.py          Route handlers, CORS config
  k8s_client.py     Talks to the Kubernetes API (namespace, quota, limit range, role binding)
  models.py        Request/response dataclasses
operator/    kopf-based Kubernetes operator
  operator.py      Watches NamespaceRequest CRDs and reconciles cluster state
frontend/    Static HTML/JS portal UI (no build step, no framework)
kubernetes/  Cluster-side manifests: CRD, operator RBAC, operator Deployment
.github/     CI workflow that builds/pushes backend and operator images to GHCR
```

The backend and operator are independent provisioning paths that converge on
the same Kubernetes objects: the portal calls the backend's REST API directly,
while `kubectl apply`/GitOps users create `NamespaceRequest` CRDs that the
operator reconciles. Both paths produce the same Namespace + ResourceQuota +
LimitRange + RoleBinding shape.

## Security Notes

- The backend's CORS policy defaults to allowing any origin (`*`) for local
  development. Set the `ALLOWED_ORIGINS` environment variable (comma-separated)
  to the portal's real origin(s) before deploying anywhere reachable beyond
  localhost.
- Backend and operator containers both run as a non-root user (uid 10001) with
  `allowPrivilegeEscalation: false` and dropped Linux capabilities.
- The operator's ClusterRole is scoped to the specific resources it manages
  (namespaces, resourcequotas, limitranges, rolebindings, its own CRD) rather
  than using wildcard rules; it does not grant secret or cluster-admin access.

## Key Engineering Decisions

**Why a custom operator?** Decouples provisioning from the API layer —
namespaces can be requested via kubectl, GitOps, or the portal. The
operator is the single source of truth.

**Why ResourceQuota + LimitRange together?** ResourceQuota sets hard
namespace-level ceilings. LimitRange sets per-container defaults so
pods without explicit limits still get bounded resources.

**Why kopf?** Lightweight Python operator framework — consistent with
the rest of the platform's Python tooling and easy to extend.