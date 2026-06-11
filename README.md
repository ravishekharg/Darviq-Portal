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

## Quick Start

```bash
# 1. Apply CRD and RBAC
kubectl create namespace platform-system
kubectl apply -f kubernetes/crd-namespacerequest.yaml
kubectl apply -f kubernetes/operator-rbac.yaml

# 2. Deploy the operator
kubectl apply -f kubernetes/operator-deployment.yaml

# 3. Deploy the backend API
kubectl apply -f kubernetes/backend-deployment.yaml

# 4. Open the portal
kubectl port-forward svc/platform-portal 8080:8080
open http://localhost:8080
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

## Key Engineering Decisions

**Why a custom operator?** Decouples provisioning from the API layer —
namespaces can be requested via kubectl, GitOps, or the portal. The
operator is the single source of truth.

**Why ResourceQuota + LimitRange together?** ResourceQuota sets hard
namespace-level ceilings. LimitRange sets per-container defaults so
pods without explicit limits still get bounded resources.

**Why kopf?** Lightweight Python operator framework — consistent with
the rest of the platform's Python tooling and easy to extend.