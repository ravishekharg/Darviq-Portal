# Generation script for the Darviq Portal High-Level Design document.
# Run with: python gen_hld.py   (from inside Docs/, or adjust the import path)
#
# This script is kept in Docs/ so the HLD can be regenerated later if the
# repo's architecture changes. It is not part of the running application.
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from docx_builder import DesignDoc

PROJECT = "Darviq Portal"
SUBTITLE = "Kubernetes Namespace Self-Service Portal — Operator, API & UI"
VERSION = "1.0"
DATE = "July 31, 2026"

doc = DesignDoc(
    project_name=PROJECT,
    subtitle=SUBTITLE,
    doc_kind="High-Level Design (HLD)",
    version=VERSION,
    date=DATE,
)
doc.add_document_control()
doc.add_toc_field()

# ---------------------------------------------------------------------------
# 1. Introduction
# ---------------------------------------------------------------------------
doc.add_heading1("1. Introduction")

doc.add_heading2("1.1 Purpose")
doc.add_paragraph(
    "This document describes the high-level design of Darviq Portal, a "
    "Kubernetes namespace self-service system. It explains the problem the "
    "system solves, the components involved, how they interact end to end, "
    "and the key architectural, security, and operational decisions behind "
    "the implementation. It is intended to give a reader unfamiliar with "
    "the codebase a correct mental model of the system before they read the "
    "code or the companion Low-Level Design (LLD) document."
)

doc.add_heading2("1.2 Scope")
doc.add_paragraph("In scope for this document:")
doc.add_bullets([
    "The kopf-based Kubernetes operator that reconciles the NamespaceRequest "
    "custom resource (operator/operator.py).",
    "The FastAPI backend REST API that provisions, lists, and deletes "
    "namespaces directly against the Kubernetes API (backend/main.py, "
    "backend/k8s_client.py, backend/models.py).",
    "The static HTML/JavaScript self-service frontend (frontend/index.html).",
    "The Kubernetes manifests that install the CRD, the operator's RBAC, "
    "and the operator's Deployment (kubernetes/).",
    "The GitHub Actions CI/CD pipeline that builds and publishes container "
    "images to GHCR.",
])
doc.add_paragraph("Out of scope for this document:")
doc.add_bullets([
    "Any downstream tooling teams may use inside the namespaces this portal "
    "provisions (application deployments, service meshes, ingress, etc.) — "
    "the portal's responsibility ends at the namespace boundary.",
    "Cluster provisioning itself (EKS/GKE/AKS/kind bootstrap) — this portal "
    "assumes a running cluster with a reachable API server.",
    "Identity/group management for the RBAC subjects the portal references "
    "(e.g. team:<team_name> groups) — group membership is assumed to be "
    "managed by whatever OIDC/identity provider the cluster already trusts.",
])

doc.add_heading2("1.3 Intended audience")
doc.add_bullets([
    "Platform / DevOps engineers evaluating or extending the portal.",
    "Software engineers implementing changes to the operator, backend, or "
    "frontend.",
    "Reviewers assessing the system's architecture and security posture.",
])

doc.add_heading2("1.4 Definitions & abbreviations")
doc.add_table(
    headers=["Term", "Definition"],
    rows=[
        ["CRD", "Custom Resource Definition — extends the Kubernetes API with a new resource type."],
        ["NamespaceRequest", "The CRD (group platform.company.io, version v1) this system defines; a declarative request for a provisioned namespace."],
        ["kopf", "Kubernetes Operator Pythonic Framework — the library used to implement the operator's watch/reconcile loop."],
        ["Operator", "A controller process that watches Kubernetes resources and reconciles cluster state to match them (here: operator/operator.py)."],
        ["ResourceQuota", "A Kubernetes object that caps aggregate resource consumption (CPU, memory, pod/service counts) within a namespace."],
        ["LimitRange", "A Kubernetes object that sets default and minimum/maximum resource requests/limits for containers in a namespace."],
        ["RoleBinding", "A Kubernetes RBAC object that grants a Role or ClusterRole to a subject (user, group, or ServiceAccount) within a namespace."],
        ["ClusterRole / ClusterRoleBinding", "Cluster-scoped RBAC objects; used here to grant the operator's ServiceAccount the permissions it needs."],
        ["GHCR", "GitHub Container Registry — where CI publishes the backend and operator container images."],
        ["CORS", "Cross-Origin Resource Sharing — browser security mechanism the backend configures via the ALLOWED_ORIGINS setting."],
        ["FastAPI", "The Python web framework used to implement the backend REST API."],
        ["GitOps", "Managing infrastructure by applying declarative manifests (e.g. NamespaceRequest CRs) via version-controlled configuration and kubectl/CD tooling."],
    ],
)

# ---------------------------------------------------------------------------
# 2. System overview
# ---------------------------------------------------------------------------
doc.add_heading1("2. System overview")

doc.add_heading2("2.1 Problem statement")
doc.add_paragraph(
    "Provisioning a new Kubernetes namespace for a team is rarely just "
    "\"kubectl create namespace\". In practice it requires a matching "
    "ResourceQuota (so one team cannot exhaust cluster capacity), a "
    "LimitRange (so pods that omit resource requests/limits still get "
    "sane defaults), and a RoleBinding (so the team can actually use the "
    "namespace without being handed cluster-admin). Done manually, this is "
    "a multi-step, easy-to-get-wrong, ticket-driven process that bottlenecks "
    "on a platform engineer for every new team, environment, or project. "
    "Darviq Portal exists to close that gap: it lets a namespace request be "
    "expressed once — either through a form or a declarative YAML object — "
    "and have the resulting Kubernetes objects created consistently, "
    "without a human manually running kubectl for each one."
)

doc.add_heading2("2.2 Proposed solution summary")
doc.add_paragraph(
    "Darviq Portal offers two convergent ways to request a namespace, both "
    "of which end up creating the same category of Kubernetes objects "
    "(Namespace, ResourceQuota, and — depending on the path — LimitRange "
    "and RoleBinding; see section 5 for the current gap between the two "
    "paths):"
)
doc.add_bullets([
    "A REST API path: a lightweight static HTML/JS portal submits a form "
    "to a FastAPI backend, which calls the Kubernetes API directly to "
    "create the namespace and its associated objects, and can list or "
    "delete namespaces it manages.",
    "A GitOps/declarative path: a user or CD pipeline applies a "
    "NamespaceRequest custom resource; a kopf-based operator running in "
    "the cluster watches for these objects and reconciles the namespace "
    "into existence.",
])
doc.add_paragraph(
    "Both paths write directly to the same live Kubernetes API; there is no "
    "separate database — the Kubernetes API server itself is the system of "
    "record for what namespaces exist and their current state."
)

# ---------------------------------------------------------------------------
# 3. Architecture overview
# ---------------------------------------------------------------------------
doc.add_heading1("3. Architecture overview")

doc.add_table(
    headers=["Component", "Responsibility", "Technology"],
    rows=[
        ["Frontend portal", "Single static page: form to request a namespace, table of currently managed namespaces, polls for updates.", "Vanilla HTML/CSS/JavaScript (no framework, no build step)"],
        ["Backend REST API", "Exposes /api/namespaces (create/list) and /api/namespaces/{name} (delete); validates input; calls the Kubernetes client layer.", "Python 3.12, FastAPI, Pydantic, Uvicorn"],
        ["Kubernetes provisioning client", "Talks to the Kubernetes API on the backend's behalf: creates Namespace + ResourceQuota + LimitRange + RoleBinding; lists/deletes namespaces.", "Python, official `kubernetes` client library"],
        ["kopf operator", "Watches NamespaceRequest custom resources cluster-wide; on create, provisions a Namespace + ResourceQuota; on delete, removes the Namespace.", "Python 3.12, kopf 1.37, `kubernetes` client library"],
        ["NamespaceRequest CRD", "Declares the schema for the GitOps-style namespace request object (platform.company.io/v1).", "Kubernetes CustomResourceDefinition"],
        ["Kubernetes API server", "Source of truth for all cluster objects (namespaces, quotas, limit ranges, role bindings, and the custom resources themselves).", "Kubernetes (EKS/GKE/AKS/kind/minikube — any distribution)"],
        ["CI/CD pipeline", "Builds and pushes the backend and operator container images on every push to main.", "GitHub Actions, Docker Buildx, GHCR"],
    ],
)

doc.add_heading2("3.1 Component descriptions")
doc.add_paragraph(
    "Frontend portal: a single index.html file with inline CSS and "
    "JavaScript, no build tooling and no framework dependency. It renders a "
    "request form and a table of managed namespaces, and refreshes the "
    "table on a fixed 30-second interval (setInterval) — there is no "
    "push/websocket channel. The backend base URL is hardcoded as a "
    "JavaScript constant (http://localhost:8080), which is a real "
    "constraint on how this file can be deployed (see section 8)."
)
doc.add_paragraph(
    "Backend REST API: a FastAPI application (backend/main.py) that "
    "validates incoming requests with a Pydantic model, applies a simple "
    "allow-list check on the `environment` field (dev/staging/prod only), "
    "and delegates all Kubernetes interaction to backend/k8s_client.py. "
    "CORS is configurable via the ALLOWED_ORIGINS environment variable and "
    "defaults to allowing any origin."
)
doc.add_paragraph(
    "Kubernetes provisioning client: backend/k8s_client.py wraps the "
    "official Python Kubernetes client. On create, it issues four separate "
    "API calls in sequence — create Namespace, create ResourceQuota, "
    "create LimitRange, create RoleBinding — each tolerating a 409 Conflict "
    "(already exists) as a non-error. On list, it queries namespaces "
    "labeled managed-by=platform-portal and, for each one, makes an "
    "additional call to read its ResourceQuota."
)
doc.add_paragraph(
    "kopf operator: operator/operator.py registers two kopf handlers for "
    "the platform.company.io/v1 namespacerequests resource — one for "
    "create, one for delete. On create it derives a namespace name from "
    "`{teamName}-{environment}`, creates the Namespace and a ResourceQuota, "
    "and returns a status dict that kopf persists to the CR's .status "
    "subresource. It authenticates to the API server using in-cluster "
    "ServiceAccount credentials when available, falling back to a local "
    "kubeconfig for development."
)
doc.add_paragraph(
    "NamespaceRequest CRD: a cluster-scoped custom resource "
    "(kubernetes/crd-namespacerequest.yaml) with OpenAPI validation on its "
    "spec — required fields teamName, environment, ownerEmail; an enum "
    "constraint on environment; a regex pattern on teamName; and defaulted "
    "cpuLimit/memoryLimit fields. It has a status subresource so the "
    "operator can report reconciliation results separately from spec."
)
doc.add_paragraph(
    "Kubernetes API server: there is no portal-specific persistence layer. "
    "Both the backend and the operator read and write directly against the "
    "live Kubernetes API, so the cluster's actual object state is always "
    "the current source of truth — there is nothing to keep in sync."
)

# ---------------------------------------------------------------------------
# 4. End-to-end functional workflow
# ---------------------------------------------------------------------------
doc.add_heading1("4. End-to-end functional workflow")
doc.add_figure_placeholder(
    "Figure 1 — Two request paths (portal form and NamespaceRequest CR) "
    "converging on the same Kubernetes objects"
)
doc.add_paragraph(
    "There are two independent entry points that lead to a provisioned "
    "namespace:"
)
doc.add_paragraph("Path A — self-service portal:")
doc.add_bullets([
    "A user fills in the form in frontend/index.html (team name, "
    "environment, CPU/memory limits, owner email, requester) and clicks "
    "Provision Namespace.",
    "The page issues a POST to {API}/api/namespaces with a JSON body.",
    "FastAPI validates the payload against the NamespaceRequestBody model "
    "and the environment allow-list, then calls "
    "k8s_client.create_namespace().",
    "The client creates the Namespace, ResourceQuota, LimitRange, and "
    "RoleBinding against the Kubernetes API, tolerating already-exists "
    "(409) responses.",
    "The API returns {\"namespace\": ..., \"status\": \"created\"}; the "
    "frontend shows a success/error banner and re-polls the namespace "
    "table.",
])
doc.add_paragraph("Path B — GitOps / declarative:")
doc.add_bullets([
    "A user or CD pipeline runs `kubectl apply -f namespace-request.yaml` "
    "with a NamespaceRequest object.",
    "The Kubernetes API server persists the custom resource and, because "
    "the operator's kopf watch is registered for this group/version/"
    "resource, emits a watch event to the operator process.",
    "kopf invokes on_namespace_request_created, which derives the "
    "namespace name and creates the Namespace and ResourceQuota directly "
    "against the API server.",
    "kopf writes the handler's return value ({\"namespace\": ..., "
    "\"status\": \"provisioned\"}) into the NamespaceRequest's .status "
    "subresource, visible via `kubectl get nsr`.",
])
doc.add_paragraph(
    "Either way, the resulting namespace is visible to the frontend's next "
    "poll of GET /api/namespaces, because that endpoint lists namespaces "
    "by label (managed-by=platform-portal) rather than by which path "
    "created them — with the caveat noted in section 5.1 that objects "
    "created via Path B currently carry the label managed-by=platform-"
    "operator rather than managed-by=platform-portal, so operator-created "
    "namespaces do not currently show up in the portal's own list view."
)

# ---------------------------------------------------------------------------
# 5. Module-wise design overview
# ---------------------------------------------------------------------------
doc.add_heading1("5. Module-wise design overview")

doc.add_heading2("5.1 NamespaceRequest CRD & kopf reconciler")
doc.add_paragraph(
    "operator/operator.py is the entire operator. It registers "
    "@kopf.on.create and @kopf.on.delete handlers for "
    "platform.company.io/v1 namespacerequests. The create handler builds "
    "a namespace name as f\"{team}-{env}\".lower(), creates a Namespace "
    "with team/environment/managed-by labels and an owner annotation, and "
    "then creates a ResourceQuota named default-quota with limits.cpu, "
    "limits.memory, and a fixed pods cap of 20. It does not currently "
    "create a LimitRange or RoleBinding — unlike the backend's "
    "k8s_client.create_namespace(), which creates all four objects. It "
    "also labels the namespace managed-by=platform-operator, whereas the "
    "backend labels it managed-by=platform-portal and the backend's list "
    "endpoint filters on that exact label — so namespaces created purely "
    "through the CRD path will not currently appear in the portal's "
    "namespace table. These are real, code-level gaps between the two "
    "provisioning paths that the README describes as producing \"the same "
    "... shape\"; they are flagged again in section 12 as near-term "
    "cleanup work. The delete handler removes the Namespace outright, "
    "which cascades to delete any namespaced objects within it "
    "(ResourceQuota, LimitRange, RoleBinding) automatically."
)

doc.add_heading2("5.2 Backend REST API layer")
doc.add_paragraph(
    "backend/main.py defines the FastAPI application, CORS middleware "
    "(origin list from ALLOWED_ORIGINS, methods restricted to GET/POST/"
    "DELETE), and four routes: GET /health, POST /api/namespaces, GET "
    "/api/namespaces, and DELETE /api/namespaces/{name}. Request bodies "
    "are validated with a Pydantic model (NamespaceRequestBody); the only "
    "business-rule validation beyond typing is that `environment` must be "
    "one of dev, staging, or prod. All Kubernetes-facing logic is "
    "delegated to backend/k8s_client.py; main.py's job is HTTP concerns "
    "only (routing, validation, status codes, logging of failures)."
)

doc.add_heading2("5.3 Kubernetes provisioning client")
doc.add_paragraph(
    "backend/k8s_client.py holds all direct Kubernetes API interaction for "
    "the backend: create_namespace() (Namespace + ResourceQuota + "
    "LimitRange + RoleBinding, in that order, each idempotent against 409 "
    "Conflict), list_namespaces() (label-selector query plus a per-"
    "namespace ResourceQuota lookup, mapped into NamespaceStatus records), "
    "and delete_namespace() (namespace deletion, treating 404 as a "
    "\"not_found\" result rather than an error). It authenticates the same "
    "way the operator does: load_incluster_config() first, falling back to "
    "load_kube_config() for local development."
)

doc.add_heading2("5.4 Self-service frontend portal")
doc.add_paragraph(
    "frontend/index.html is a single static file: no framework, no npm "
    "dependency, no build step. It contains a request form (team name, "
    "environment select, CPU/memory limit inputs, owner email, requester "
    "name) and a table driven by GET /api/namespaces, refreshed on load "
    "and every 30 seconds via setInterval. The backend base URL is a "
    "hardcoded JavaScript constant, so pointing this file at a non-"
    "localhost backend currently requires editing the file (or serving a "
    "templated/rewritten copy) rather than passing runtime configuration."
)

# ---------------------------------------------------------------------------
# 6. Data design
# ---------------------------------------------------------------------------
doc.add_heading1("6. Data design")
doc.add_paragraph(
    "Darviq Portal has no database. All persisted state lives in the "
    "Kubernetes API server as native objects, so \"data design\" here means "
    "the shape of the CRD and the in-process request/response models both "
    "code paths use to describe a namespace."
)
doc.add_table(
    headers=["Model", "Fields", "Where used"],
    rows=[
        ["NamespaceRequest CRD .spec", "teamName (string, pattern ^[a-z0-9-]+$, required), environment (enum dev|staging|prod, required), cpuLimit (string, default \"2\"), memoryLimit (string, default \"4Gi\"), ownerEmail (string, required)", "kubernetes/crd-namespacerequest.yaml; read by operator/operator.py"],
        ["NamespaceRequest CRD .status", "Free-form (x-kubernetes-preserve-unknown-fields); populated with {namespace, status} by the operator's return value", "Set by kopf after each reconcile; readable via kubectl get nsr -o yaml"],
        ["NamespaceRequestBody (Pydantic)", "team_name, environment, cpu_limit (default \"4\"), memory_limit (default \"8Gi\"), owner_email, requested_by", "backend/main.py — the REST API's request schema"],
        ["NamespaceRequest (dataclass)", "team_name, environment, cpu_limit, memory_limit, owner_email, requested_by", "backend/models.py — internal representation passed into k8s_client.create_namespace()"],
        ["NamespaceStatus (dataclass)", "name, status, created_at, cpu_limit, memory_limit, owner", "backend/models.py — shape returned by GET /api/namespaces"],
    ],
)
doc.add_paragraph(
    "Note the field-default asymmetry: the CRD defaults cpuLimit/memoryLimit "
    "to \"2\"/\"4Gi\" while the REST API's Pydantic model defaults them to "
    "\"4\"/\"8Gi\" — a small but real inconsistency between the two request "
    "paths that a caller relying on defaults (rather than specifying "
    "explicit limits) would experience differently depending on which path "
    "they use."
)

# ---------------------------------------------------------------------------
# 7. Technology stack
# ---------------------------------------------------------------------------
doc.add_heading1("7. Technology stack")
doc.add_table(
    headers=["Layer", "Technology", "Notes"],
    rows=[
        ["Language runtime", "Python 3.12", "Both backend and operator; python:3.12-slim base images"],
        ["Operator framework", "kopf 1.37.2", "Kubernetes Operator Pythonic Framework — decorator-based watch/reconcile handlers"],
        ["Kubernetes client", "kubernetes (Python) 30.1.0", "Official client library; used identically by backend and operator"],
        ["Backend API framework", "FastAPI 0.111.0 + Uvicorn 0.30.0", "ASGI app; Uvicorn as the ASGI server"],
        ["Request validation", "Pydantic 2.7.1", "NamespaceRequestBody model in backend/main.py"],
        ["Frontend", "Vanilla HTML/CSS/JavaScript", "No framework, no bundler, no npm dependency; single index.html file"],
        ["CRD schema validation", "Kubernetes OpenAPI v3 schema", "Enforced by the API server itself at admission time"],
        ["Containers", "Docker (python:3.12-slim base)", "Separate Dockerfiles for backend/ and operator/; non-root user (uid 10001) in both"],
        ["Container registry", "GHCR (ghcr.io)", "ghcr.io/ravishekharg/k8s-platform-portal/{backend,operator}"],
        ["CI/CD", "GitHub Actions", "Matrix build over [backend, operator]; builds and pushes on every push to main"],
        ["Target runtime", "Any Kubernetes distribution", "EKS, GKE, AKS, kind, minikube — no cloud-specific API usage"],
    ],
)

# ---------------------------------------------------------------------------
# 8. Deployment architecture
# ---------------------------------------------------------------------------
doc.add_heading1("8. Deployment architecture")
doc.add_figure_placeholder(
    "Figure 2 — platform-system namespace running the operator, alongside "
    "a manually-run backend and a statically-served frontend"
)
doc.add_paragraph(
    "The CRD, operator RBAC (ServiceAccount, ClusterRole, "
    "ClusterRoleBinding), and operator Deployment are the only pieces of "
    "this system with checked-in Kubernetes manifests today "
    "(kubernetes/crd-namespacerequest.yaml, "
    "kubernetes/operator-rbac.yaml, kubernetes/operator-deployment.yaml). "
    "They install into a platform-system namespace: a single-replica "
    "operator Deployment running as a non-root user (uid 10001) with "
    "allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, and "
    "all Linux capabilities dropped, with modest CPU/memory requests and "
    "limits (100m/128Mi requests, 500m/256Mi limits)."
)
doc.add_paragraph(
    "The backend currently has no checked-in Kubernetes Deployment or "
    "Service manifest — the README states this explicitly as a current "
    "gap. It is intended to be run either as a container built from "
    "backend/Dockerfile (docker run -p 8080:8080 ...) or directly via "
    "uvicorn during local development. Whoever deploys this repo today "
    "must write their own Deployment/Service for the backend before "
    "running it inside the cluster it manages."
)
doc.add_paragraph(
    "The frontend has no Dockerfile or manifest at all: it is a single "
    "static HTML file intended to be opened directly or served by any "
    "static file host, with its backend URL hardcoded to "
    "http://localhost:8080 in the page's inline script."
)
doc.add_paragraph(
    "CI/CD: the GitHub Actions workflow (.github/workflows/build-push.yaml) "
    "runs a two-way build matrix over [backend, operator] on every push to "
    "main, builds each Dockerfile, and pushes both a :{git-sha} tag and a "
    ":latest tag to GHCR. There is no CD step that applies manifests to a "
    "cluster or that builds/publishes anything for the frontend."
)
doc.add_table(
    headers=["Variable", "Used by", "Purpose / default"],
    rows=[
        ["ALLOWED_ORIGINS", "backend/main.py", "Comma-separated list of allowed CORS origins; defaults to \"*\" (any origin) if unset — intended to be overridden before any non-local deployment"],
        ["(implicit) KUBECONFIG / in-cluster ServiceAccount", "backend/k8s_client.py, operator/operator.py", "Both processes call load_incluster_config() first and fall back to load_kube_config(); no explicit environment variable is read for this, it relies on the standard Kubernetes client auto-detection"],
    ],
)

# ---------------------------------------------------------------------------
# 9. Security design
# ---------------------------------------------------------------------------
doc.add_heading1("9. Security design")
doc.add_paragraph(
    "Operator RBAC: the operator's ClusterRole "
    "(kubernetes/operator-rbac.yaml) is scoped to exactly the resources it "
    "needs — namespaces, resourcequotas, limitranges (core API group), "
    "rolebindings (rbac.authorization.k8s.io), its own "
    "namespacerequests/namespacerequests-status (platform.company.io), and "
    "read-only access to customresourcedefinitions. It grants full CRUD "
    "verbs (get/list/watch/create/update/patch/delete) on the first three "
    "groups but does not reference Secrets, Pods, or any wildcard resource, "
    "and is not bound to cluster-admin."
)
doc.add_paragraph(
    "Backend API authentication: there is currently none. main.py defines "
    "no authentication or authorization middleware — any client able to "
    "reach the backend's HTTP port can provision or delete namespaces via "
    "the REST API. The only access-control lever exposed is the "
    "ALLOWED_ORIGINS CORS setting, which restricts which browser origins "
    "may call the API cross-origin, but does not restrict direct HTTP "
    "clients (curl, other services) at all, and defaults wide open (\"*\") "
    "if not explicitly set. This is a genuine, current limitation rather "
    "than an oversight in this document — see section 12."
)
doc.add_paragraph(
    "Frontend access control: the static portal page performs no "
    "authentication of its own user; it relies entirely on network-level "
    "controls (e.g., who can reach the host serving the file and the "
    "backend it talks to) for access control."
)
doc.add_paragraph(
    "Container hardening: both the backend and operator Dockerfiles create "
    "and switch to a dedicated non-root user (uid 10001, gid 10001). The "
    "operator's Deployment manifest additionally enforces "
    "allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, and "
    "capabilities.drop: [ALL] at the pod level. Because no backend "
    "Deployment manifest exists yet, that pod-level hardening is not yet "
    "codified for the backend in-cluster — only the Dockerfile's USER "
    "directive is in effect for the backend today."
)
doc.add_paragraph(
    "RBAC subject model for provisioned namespaces: each namespace gets a "
    "RoleBinding granting the built-in ClusterRole `edit` to the group "
    "team:{team_name}. This assumes the cluster's authentication layer "
    "(OIDC, cloud IAM mapping, etc.) already maps real users into groups "
    "named that way — the portal does not create, verify, or manage group "
    "membership itself."
)

# ---------------------------------------------------------------------------
# 10. Non-functional requirements
# ---------------------------------------------------------------------------
doc.add_heading1("10. Non-functional requirements")
doc.add_table(
    headers=["Attribute", "Target / approach"],
    rows=[
        ["Reconciliation latency", "kopf's watch is event-driven (not polling), so a NamespaceRequest is typically reconciled within low single-digit seconds of being applied, bounded mainly by API server watch latency and the operator's own processing time."],
        ["API responsiveness", "POST/DELETE calls are effectively bounded by 2-4 synchronous Kubernetes API calls each (sub-second to low single-digit seconds under normal cluster load); no async job queue exists, so the HTTP request blocks until all K8s calls complete."],
        ["Frontend refresh rate", "Fixed 30-second polling interval (setInterval); not real-time — a namespace created via the CRD/operator path may take up to 30s to visibly appear (or, per the labeling gap in 5.1, may not appear at all)."],
        ["Scalability with cluster size / namespace count", "list_namespaces() performs one label-selector list call plus one additional ResourceQuota-list call per matching namespace (an N+1 pattern). This is adequate for the tens of namespaces a small platform team would manage but would add latency and API server load as the managed namespace count grows into the hundreds."],
        ["Availability / redundancy", "The operator Deployment runs a single replica with no leader-election configuration visible in the manifest; the backend has no Deployment manifest at all, so redundancy is whatever the operator of a given deployment chooses to add."],
        ["Idempotency", "Both the operator and the backend client tolerate 409 Conflict responses when creating already-existing objects, so re-applying a NamespaceRequest or resubmitting a form is safe and does not error."],
        ["Resource footprint", "The operator Deployment requests 100m CPU / 128Mi memory and caps at 500m CPU / 256Mi memory — appropriately lightweight for a control-loop process handling a low request volume."],
    ],
)

# ---------------------------------------------------------------------------
# 11. Assumptions & constraints
# ---------------------------------------------------------------------------
doc.add_heading1("11. Assumptions & constraints")
doc.add_heading2("11.1 Assumptions")
doc.add_bullets([
    "A Kubernetes cluster with a reachable API server already exists; this "
    "system does not provision clusters.",
    "The built-in `edit` ClusterRole exists in the target cluster (it is a "
    "Kubernetes default and is referenced, not created, by this system).",
    "Group-based RBAC subjects (team:{team_name}) are meaningful to the "
    "cluster's configured authentication provider; this system does not "
    "manage identity or group membership.",
    "Both the operator and the backend are expected to run with credentials "
    "that have the RBAC permissions described in section 9 — either via "
    "in-cluster ServiceAccount tokens or an operator-provided kubeconfig.",
])
doc.add_heading2("11.2 Constraints")
doc.add_bullets([
    "No database or persistent store beyond the Kubernetes API server "
    "itself — all state (including \"which namespaces does this portal "
    "manage\") is derived live from cluster labels at query time.",
    "The frontend has no build step and no runtime configuration "
    "mechanism, so its backend URL is fixed at edit time, not deploy time.",
    "The backend has no authentication layer today, which constrains where "
    "it can safely be exposed (see section 9).",
    "The operator and backend provisioning paths are implemented "
    "independently and have already drifted apart (LimitRange/RoleBinding "
    "creation, managed-by label value, and default resource limits all "
    "differ between the two — see sections 5.1 and 6); anyone relying on "
    "them being interchangeable should verify this against the current "
    "code before depending on it.",
])

# ---------------------------------------------------------------------------
# 12. Future enhancements
# ---------------------------------------------------------------------------
doc.add_heading1("12. Future enhancements")
doc.add_bullets([
    "Add a Kubernetes Deployment/Service manifest for the backend (called "
    "out directly in the repo's own README as not yet done).",
    "Bring the operator's reconciler up to parity with the backend's "
    "provisioning client — create the missing LimitRange and RoleBinding "
    "on the CRD path, and align the managed-by label value and default "
    "cpuLimit/memoryLimit values between the two paths.",
    "Add authentication/authorization to the backend REST API (e.g. an API "
    "key, OAuth2/OIDC bearer token, or mTLS) before exposing it beyond a "
    "trusted local network — currently there is none.",
    "Set ALLOWED_ORIGINS to a specific origin (rather than the \"*\" "
    "default) before any deployment reachable beyond localhost, per the "
    "README's own security note.",
    "Make the frontend's backend URL runtime-configurable (e.g. injected "
    "via a small config endpoint or environment-substituted at container "
    "build/start time) instead of hardcoded.",
    "Replace fixed 30-second polling with push-based updates (WebSocket or "
    "Server-Sent Events) for a more real-time namespace table.",
    "Add leader election / multi-replica support for the operator, and a "
    "documented HA story for the backend once it has a Deployment "
    "manifest.",
    "Reduce the N+1 API-call pattern in list_namespaces() as the number of "
    "managed namespaces grows (e.g. cache quota data, or watch instead of "
    "poll).",
])

# ---------------------------------------------------------------------------
# 13. Appendix
# ---------------------------------------------------------------------------
doc.add_heading1("13. Appendix")
doc.add_heading2("13.1 References")
doc.add_bullets([
    "Repository README.md",
    "operator/operator.py, operator/requirements.txt, operator/Dockerfile",
    "backend/main.py, backend/k8s_client.py, backend/models.py, "
    "backend/requirements.txt, backend/Dockerfile",
    "frontend/index.html",
    "kubernetes/crd-namespacerequest.yaml, kubernetes/operator-rbac.yaml, "
    "kubernetes/operator-deployment.yaml",
    ".github/workflows/build-push.yaml",
    "kopf documentation (https://kopf.readthedocs.io/)",
    "Kubernetes API reference for Namespace, ResourceQuota, LimitRange, "
    "RoleBinding, and CustomResourceDefinition objects",
])
doc.add_heading2("13.2 Change history")
doc.add_table(
    headers=["Version", "Date", "Description"],
    rows=[["1.0", DATE, "Initial high-level design document"]],
)

doc.save("Darviq_Portal_High_Level_Design.docx")
print("HLD written")
