# Generation script for the Darviq Portal Low-Level Design document.
# Run with: python gen_lld.py   (from inside Docs/, or adjust the import path)
#
# This script is kept in Docs/ so the LLD can be regenerated later if the
# repo's implementation changes. It is not part of the running application.
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
    doc_kind="Low-Level Design (LLD)",
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
    "This Low-Level Design document provides the implementation-level "
    "detail behind the architecture described in the Darviq Portal "
    "High-Level Design (HLD): concrete file and package structure, the "
    "NamespaceRequest CRD schema, the backend's REST API contract, the "
    "step-by-step reconciliation and provisioning flows, and the actual "
    "error-handling and validation logic present in the code today. Where "
    "the code has a known gap or inconsistency, this document states it "
    "plainly rather than describing an idealized version of the system."
)

doc.add_heading2("1.2 Scope")
doc.add_paragraph(
    "This document covers the same four components as the HLD — the kopf "
    "operator, the FastAPI backend, its Kubernetes client layer, and the "
    "static frontend — at the level of actual functions, routes, and "
    "object fields."
)

doc.add_heading2("1.3 References")
doc.add_bullets([
    "Darviq_Portal_High_Level_Design.docx (this document's companion HLD)",
    "operator/operator.py",
    "backend/main.py, backend/k8s_client.py, backend/models.py",
    "frontend/index.html",
    "kubernetes/crd-namespacerequest.yaml, kubernetes/operator-rbac.yaml, "
    "kubernetes/operator-deployment.yaml",
    ".github/workflows/build-push.yaml",
    "Repository README.md",
])

# ---------------------------------------------------------------------------
# 2. Detailed module design
# ---------------------------------------------------------------------------
doc.add_heading1("2. Detailed module design")

doc.add_heading2("2.1 NamespaceRequest CRD & kopf reconciler (operator/operator.py)")
doc.add_paragraph(
    "The entire operator lives in one file, operator/operator.py. On "
    "import, it configures Kubernetes API access with "
    "config.load_incluster_config(), falling back to "
    "config.load_kube_config() in an except clause (this is the standard "
    "pattern for code that must run both inside and outside a cluster), "
    "and instantiates client.CoreV1Api() and "
    "client.RbacAuthorizationV1Api() at module scope."
)
doc.add_paragraph(
    "@kopf.on.create(\"platform.company.io\", \"v1\", \"namespacerequests\") "
    "decorates on_namespace_request_created(spec, name, namespace, logger, "
    "**kwargs). It reads teamName, environment, cpuLimit (default \"2\"), "
    "memoryLimit (default \"4Gi\"), and ownerEmail from spec, computes "
    "ns_name = f\"{team}-{env}\".lower(), and:"
)
doc.add_bullets([
    "Calls core_v1.create_namespace() with labels {team, environment, "
    "managed-by: \"platform-operator\"} and annotation {owner}. A 409 "
    "ApiException is swallowed (namespace already exists); any other "
    "ApiException is re-raised as kopf.PermanentError, which tells kopf "
    "not to retry.",
    "Calls core_v1.create_namespaced_resource_quota() with hard limits "
    "limits.cpu, limits.memory, and a fixed pods: \"20\" cap, again "
    "tolerating 409.",
    "Returns {\"namespace\": ns_name, \"status\": \"provisioned\"}, which "
    "kopf writes into the CR's .status subresource automatically.",
])
doc.add_paragraph(
    "Notably, this handler does not create a LimitRange or a RoleBinding — "
    "only Namespace and ResourceQuota. This differs from "
    "k8s_client.create_namespace() in the backend (section 2.3), which "
    "creates all four objects. It also uses the label value "
    "managed-by=platform-operator, while the backend's list query filters "
    "on managed-by=platform-portal — so a namespace provisioned purely "
    "through this CRD path will not currently be returned by GET "
    "/api/namespaces (section 4)."
)
doc.add_paragraph(
    "@kopf.on.delete(...) decorates on_namespace_request_deleted(spec, "
    "name, logger, **kwargs), which re-derives ns_name the same way and "
    "calls core_v1.delete_namespace(ns_name), tolerating a 404 "
    "(already gone) and raising kopf.PermanentError on any other error. "
    "Because ResourceQuota, LimitRange, and RoleBinding are all namespaced "
    "objects, deleting the Namespace cascades to remove them without the "
    "handler needing to delete them individually."
)

doc.add_heading2("2.2 Backend REST API layer (backend/main.py)")
doc.add_paragraph(
    "backend/main.py constructs the FastAPI app with title \"K8s Platform "
    "Self-Service Portal\" and installs CORSMiddleware with "
    "allow_methods=[\"GET\", \"POST\", \"DELETE\"] and allow_headers=["
    "\"Content-Type\"]. allow_origins is computed from the ALLOWED_ORIGINS "
    "environment variable: the literal value \"*\" (the default if unset) "
    "maps to [\"*\"]; any other value is split on commas and stripped."
)
doc.add_paragraph(
    "NamespaceRequestBody (a Pydantic BaseModel) declares team_name, "
    "environment, cpu_limit (default \"4\"), memory_limit (default "
    "\"8Gi\"), owner_email, and requested_by — all typed as str except the "
    "two defaulted fields. Four routes are registered: GET /health "
    "(liveness probe target, returns {\"status\": \"ok\"}); POST "
    "/api/namespaces (validates environment is one of dev/staging/prod, "
    "constructs a models.NamespaceRequest from the body, calls "
    "k8s_client.create_namespace(), and maps any exception to HTTP 500); "
    "GET /api/namespaces (calls k8s_client.list_namespaces() and returns "
    "vars(ns) for each NamespaceStatus dataclass instance); DELETE "
    "/api/namespaces/{name} (calls k8s_client.delete_namespace(), returns "
    "HTTP 404 if the result status is \"not_found\")."
)

doc.add_heading2("2.3 Kubernetes provisioning client (backend/k8s_client.py)")
doc.add_paragraph(
    "backend/k8s_client.py performs its own load_k8s_config() at import "
    "time (same in-cluster-then-kubeconfig fallback as the operator) and "
    "constructs core_v1 (CoreV1Api), rbac_v1 (RbacAuthorizationV1Api), and "
    "custom_api (CustomObjectsApi) clients — note that custom_api is "
    "constructed but not currently used anywhere in this file; the backend "
    "does not itself read or write NamespaceRequest custom resources, it "
    "only manipulates native Namespace/ResourceQuota/LimitRange/"
    "RoleBinding objects directly."
)
doc.add_paragraph("create_namespace(req: NamespaceRequest) -> dict performs, in order:")
doc.add_bullets([
    "core_v1.create_namespace() — labels {team, environment, managed-by: "
    "\"platform-portal\"}, annotations {owner, requested-by, created-at: "
    "an ISO-8601 UTC timestamp generated at request time}. A 409 is logged "
    "as a warning and treated as success; other exceptions propagate.",
    "core_v1.create_namespaced_resource_quota() named \"default-quota\", "
    "hard limits requests.cpu, requests.memory, limits.cpu, limits.memory "
    "(all set to req.cpu_limit/req.memory_limit), plus fixed pods: \"20\" "
    "and services: \"10\" caps. 409 tolerated.",
    "core_v1.create_namespaced_limit_range() named \"default-limits\", one "
    "Container-type item with default {cpu: 500m, memory: 512Mi} and "
    "default_request {cpu: 100m, memory: 128Mi}. 409 tolerated.",
    "rbac_v1.create_namespaced_role_binding() named "
    "\"{team_name}-binding\", role_ref = ClusterRole/edit, subject = Group "
    "\"team:{team_name}\". 409 tolerated.",
])
doc.add_paragraph(
    "list_namespaces() -> List[NamespaceStatus] calls "
    "core_v1.list_namespace(label_selector=\"managed-by=platform-"
    "portal\"), then for each matching namespace performs a second call, "
    "core_v1.list_namespaced_resource_quota(ns.metadata.name), reading "
    "hard.limits.cpu/limits.memory from the first quota object found (or "
    "\"unknown\" if none). This is an N+1 API-call pattern: one list call "
    "plus one additional call per namespace."
)
doc.add_paragraph(
    "delete_namespace(name) -> dict calls core_v1.delete_namespace(name); "
    "on ApiException with status 404 it returns "
    "{\"namespace\": name, \"status\": \"not_found\"} instead of raising, "
    "which main.py's route handler translates into an HTTP 404 response."
)

doc.add_heading2("2.4 Self-service frontend portal (frontend/index.html)")
doc.add_paragraph(
    "A single static file with no external dependencies. Inline CSS "
    "styles a header bar, two \".card\" sections (a request form and an "
    "active-namespaces table), and status badges. Inline JavaScript "
    "defines a module-level API constant (const API = "
    "'http://localhost:8080') and two async functions: "
    "createNamespace(), which reads the six form fields into an object, "
    "POSTs it as JSON to `${API}/api/namespaces`, shows a success or error "
    "message div (#msg) based on the response, and calls loadNamespaces() "
    "again on success; and loadNamespaces(), which GETs `${API}"
    "/api/namespaces` and re-renders the #nsTable tbody as one <tr> per "
    "namespace (name, status badge, cpu_limit, memory_limit, owner, and "
    "created_at truncated to its date portion). loadNamespaces() is called "
    "once on page load and then every 30000ms via setInterval — there is "
    "no websocket or server-push channel, and no error retry/backoff "
    "beyond replacing the table body with a \"Could not load namespaces\" "
    "row on fetch failure."
)

# ---------------------------------------------------------------------------
# 3. CRD schema design
# ---------------------------------------------------------------------------
doc.add_heading1("3. CRD schema design")
doc.add_paragraph(
    "This system's schema-equivalent artifact is the NamespaceRequest "
    "CustomResourceDefinition (kubernetes/crd-namespacerequest.yaml), "
    "group platform.company.io, version v1, cluster-scoped, with short "
    "name `nsr`. Its OpenAPI v3 schema, enforced by the Kubernetes API "
    "server at admission time:"
)
doc.add_table(
    headers=["Field", "Type", "Constraints", "Description"],
    rows=[
        ["spec.teamName", "string", "required; pattern ^[a-z0-9-]+$", "Team identifier; combined with environment to form the namespace name."],
        ["spec.environment", "string", "required; enum [dev, staging, prod]", "Deployment environment tier."],
        ["spec.cpuLimit", "string", "optional; default \"2\"", "Aggregate CPU limit applied via the generated ResourceQuota's limits.cpu."],
        ["spec.memoryLimit", "string", "optional; default \"4Gi\"", "Aggregate memory limit applied via the generated ResourceQuota's limits.memory."],
        ["spec.ownerEmail", "string", "required", "Recorded as the `owner` annotation on the created Namespace."],
        ["status", "object", "x-kubernetes-preserve-unknown-fields: true; served via the status subresource", "Free-form; populated by kopf with the create handler's return value, e.g. {namespace, status}."],
    ],
)
doc.add_paragraph(
    "Because the CRD declares a status subresource, spec and status "
    "updates are versioned independently — a client updating .status (as "
    "kopf does after each reconcile) does not race with or overwrite "
    "concurrent .spec edits, and vice versa. There is only one served/"
    "stored version (v1); no conversion webhook is defined or needed."
)

# ---------------------------------------------------------------------------
# 4. API specification
# ---------------------------------------------------------------------------
doc.add_heading1("4. API specification")
doc.add_table(
    headers=["Method & path", "Auth", "Description"],
    rows=[
        ["GET /health", "None", "Liveness check; returns {\"status\": \"ok\"}."],
        ["POST /api/namespaces", "None", "Provisions a namespace (+ ResourceQuota + LimitRange + RoleBinding) for a team/environment."],
        ["GET /api/namespaces", "None", "Lists namespaces labeled managed-by=platform-portal, with their quota limits and owner."],
        ["DELETE /api/namespaces/{name}", "None", "Deletes the named namespace; 404 if it does not exist."],
    ],
)
doc.add_paragraph(
    "None of these routes require a credential today (see HLD section 9 "
    "for the security implications). The two most important endpoints are "
    "detailed below."
)

doc.add_heading2("4.1 POST /api/namespaces")
doc.add_paragraph("Request body:")
doc.add_code_block(
    "{\n"
    '  "team_name":    "payments",\n'
    '  "environment":  "dev",\n'
    '  "cpu_limit":    "4",\n'
    '  "memory_limit": "8Gi",\n'
    '  "owner_email":  "payments-lead@company.com",\n'
    '  "requested_by": "ravi"\n'
    "}"
)
doc.add_paragraph(
    "cpu_limit and memory_limit are optional (defaulting to \"4\" and "
    "\"8Gi\" respectively); environment must be one of dev, staging, or "
    "prod, enforced with a 400 response otherwise, before "
    "k8s_client.create_namespace() is ever called."
)
doc.add_paragraph("Success response (HTTP 200):")
doc.add_code_block(
    "{\n"
    '  "namespace": "payments-dev",\n'
    '  "status": "created"\n'
    "}"
)
doc.add_paragraph("Validation error response (HTTP 400):")
doc.add_code_block(
    "{\n"
    '  "detail": "environment must be dev, staging, or prod"\n'
    "}"
)
doc.add_paragraph("Downstream failure response (HTTP 500) — any exception from k8s_client:")
doc.add_code_block(
    "{\n"
    '  "detail": "<str(exception)>"\n'
    "}"
)

doc.add_heading2("4.2 GET /api/namespaces")
doc.add_paragraph("Success response (HTTP 200) — array of NamespaceStatus objects:")
doc.add_code_block(
    "[\n"
    "  {\n"
    '    "name": "payments-dev",\n'
    '    "status": "Active",\n'
    '    "created_at": "2026-07-31T09:12:44.512930+00:00",\n'
    '    "cpu_limit": "4",\n'
    '    "memory_limit": "8Gi",\n'
    '    "owner": "payments-lead@company.com"\n'
    "  }\n"
    "]"
)
doc.add_paragraph(
    "`status` is the live Kubernetes namespace phase (ns.status.phase, "
    "typically \"Active\" or \"Terminating\"), not an application-level "
    "status. cpu_limit/memory_limit are read back from the namespace's "
    "ResourceQuota's hard.limits.cpu/limits.memory at query time (\"unknown\" "
    "if no quota is found), not stored redundantly anywhere — this "
    "endpoint always reflects live cluster state."
)

# ---------------------------------------------------------------------------
# 5. Sequence flows / process flows
# ---------------------------------------------------------------------------
doc.add_heading1("5. Sequence flows / process flows")

doc.add_heading2("5.1 Portal-driven namespace provisioning")
doc.add_table(
    headers=["Step", "Actor/Component", "Action"],
    rows=[
        ["1", "User (browser)", "Fills the request form in frontend/index.html and clicks Provision Namespace."],
        ["2", "Frontend JS (createNamespace())", "POSTs the form fields as JSON to {API}/api/namespaces."],
        ["3", "FastAPI (main.py)", "Validates the body against NamespaceRequestBody and the environment allow-list."],
        ["4", "k8s_client.create_namespace()", "Creates Namespace, then ResourceQuota, then LimitRange, then RoleBinding against the Kubernetes API, tolerating 409 on each."],
        ["5", "Kubernetes API server", "Persists each object; namespace becomes Active."],
        ["6", "FastAPI (main.py)", "Returns {namespace, status: \"created\"} (or a 4xx/5xx on failure)."],
        ["7", "Frontend JS", "Shows a success/error banner and calls loadNamespaces() to refresh the table."],
    ],
)

doc.add_heading2("5.2 GitOps-driven namespace provisioning (operator path)")
doc.add_table(
    headers=["Step", "Actor/Component", "Action"],
    rows=[
        ["1", "User / CD pipeline", "Runs kubectl apply -f namespace-request.yaml with a NamespaceRequest object."],
        ["2", "Kubernetes API server", "Validates the object against the CRD's OpenAPI schema and persists it; emits a watch event."],
        ["3", "kopf runtime", "Delivers the create event to on_namespace_request_created() (operator/operator.py)."],
        ["4", "Operator handler", "Derives ns_name and creates the Namespace, then the ResourceQuota, tolerating 409 on each."],
        ["5", "kopf runtime", "Writes the handler's return value into the NamespaceRequest's .status subresource."],
        ["6", "User", "Observes the result via kubectl get nsr or kubectl get ns."],
    ],
)

doc.add_heading2("5.3 Namespace listing (frontend poll)")
doc.add_table(
    headers=["Step", "Actor/Component", "Action"],
    rows=[
        ["1", "Frontend JS (setInterval, 30s)", "Calls loadNamespaces(), which GETs {API}/api/namespaces."],
        ["2", "FastAPI (main.py)", "Delegates to k8s_client.list_namespaces()."],
        ["3", "k8s_client.list_namespaces()", "Lists namespaces with label managed-by=platform-portal, then queries each one's ResourceQuota individually."],
        ["4", "FastAPI (main.py)", "Serializes the resulting NamespaceStatus dataclasses (via vars()) as a JSON array."],
        ["5", "Frontend JS", "Re-renders the #nsTable rows from the response, or shows a fallback row on fetch failure."],
    ],
)

doc.add_heading2("5.4 Namespace deletion")
doc.add_table(
    headers=["Step", "Actor/Component", "Action"],
    rows=[
        ["1", "Client (portal or kubectl delete on the CR)", "Portal: DELETE {API}/api/namespaces/{name}. CRD path: kubectl delete nsr triggers the operator's on_delete handler instead."],
        ["2", "FastAPI (main.py) or operator handler", "Calls delete_namespace() (backend) or core_v1.delete_namespace() (operator) directly."],
        ["3", "Kubernetes API server", "Marks the namespace Terminating, then cascades deletion to all namespaced objects inside it (ResourceQuota, LimitRange, RoleBinding) automatically."],
        ["4", "Caller", "Backend path: receives {namespace, status: \"deleted\"} or HTTP 404 if the namespace was already gone. Operator path: NamespaceRequest object itself is removed once finalizers (if any) clear."],
    ],
)

# ---------------------------------------------------------------------------
# 6. Key algorithms & business logic
# ---------------------------------------------------------------------------
doc.add_heading1("6. Key algorithms & business logic")
doc.add_paragraph(
    "Namespace naming: both the operator (operator.py, line ~29) and the "
    "backend (k8s_client.py, line ~28) derive the namespace name "
    "identically — f\"{team}-{environment}\".lower() — so the same "
    "NamespaceRequest submitted through either path resolves to the same "
    "physical namespace name, which is what allows the two paths to be "
    "described as convergent despite their other differences."
)
doc.add_paragraph(
    "Idempotent creation via 409 suppression: every create_* call in both "
    "k8s_client.py and operator.py is wrapped in a try/except ApiException "
    "that checks `e.status != 409` before re-raising. This makes repeated "
    "application of the same request (a re-submitted form, or `kubectl "
    "apply` run twice) a no-op on the already-existing objects rather than "
    "an error — a simple but effective idempotency strategy given there is "
    "no separate state store to check against first."
)
doc.add_paragraph(
    "No reconciliation/diff loop: unlike a full controller pattern that "
    "continuously reconciles desired vs. observed state, this operator "
    "only acts on create and delete watch events for the CRD itself. It "
    "does not watch or reconcile drift in the Namespace/ResourceQuota/"
    "LimitRange/RoleBinding objects it created — if someone manually edits "
    "or deletes the ResourceQuota inside an already-provisioned namespace, "
    "the operator will not detect or repair that drift (there is no "
    "@kopf.on.update handler and no periodic re-sync timer registered)."
)
doc.add_paragraph(
    "No caching layer: list_namespaces() queries the Kubernetes API fresh "
    "on every call (one list-namespaces call plus one list-resourcequota "
    "call per namespace); there is no in-memory or external cache, so "
    "every 30-second frontend poll produces a fresh round of API-server "
    "reads proportional to the number of managed namespaces."
)

# ---------------------------------------------------------------------------
# 7. Validation & error handling
# ---------------------------------------------------------------------------
doc.add_heading1("7. Validation & error handling")
doc.add_paragraph(
    "Request-level validation: FastAPI/Pydantic reject malformed bodies "
    "(missing required fields, wrong types) with an automatic HTTP 422 "
    "before main.py's handler code runs at all. main.py adds one explicit "
    "business rule on top — environment must be dev/staging/prod — "
    "returned as HTTP 400."
)
doc.add_paragraph(
    "Kubernetes API errors: k8s_client.py and operator.py both special-"
    "case ApiException status 409 (Conflict, i.e. already exists) as a "
    "non-error on every create_* call, and 404 (Not Found) as a non-error "
    "on delete. Any other ApiException propagates: in the backend, "
    "main.py's route handlers catch the generic Exception, log it, and "
    "return HTTP 500 with str(e) as the detail — which does leak internal "
    "exception text (e.g. underlying Kubernetes client error messages) to "
    "the API caller, a minor information-disclosure consideration worth "
    "tightening if this API is exposed beyond a trusted network. In the "
    "operator, any non-409/404 ApiException is wrapped and re-raised as "
    "kopf.PermanentError, which tells kopf to mark the handler failed and "
    "not retry it (as opposed to kopf.TemporaryError, which would be "
    "retried) — meaning a transient API server hiccup during provisioning "
    "currently results in a permanently failed reconcile rather than an "
    "automatic retry."
)
doc.add_paragraph(
    "Known gaps (stated plainly, consistent with the honesty already in "
    "the repo's own README):"
)
doc.add_bullets([
    "The operator does not create a LimitRange or RoleBinding, so "
    "namespaces provisioned purely via kubectl apply on a NamespaceRequest "
    "are missing per-container default limits and the team's edit access "
    "— someone would need to create those manually today.",
    "The operator's managed-by=platform-operator label does not match the "
    "backend's managed-by=platform-portal filter, so operator-created "
    "namespaces are invisible to GET /api/namespaces and thus to the "
    "portal's table.",
    "There is no partial-failure rollback: if, say, ResourceQuota creation "
    "succeeds but LimitRange creation then fails, the Namespace and "
    "ResourceQuota are left in place rather than being cleaned up — a "
    "retry (or a manual kubectl apply of the missing piece) is required to "
    "reach the fully-provisioned state.",
    "No authentication on the backend API means there is no way today to "
    "attribute or restrict who can call POST/DELETE — requested_by and "
    "owner_email are recorded as free-text annotations, not verified "
    "identities.",
])

# ---------------------------------------------------------------------------
# 8. Non-functional implementation details
# ---------------------------------------------------------------------------
doc.add_heading1("8. Non-functional implementation details")
doc.add_paragraph(
    "Security implementation: the operator's ClusterRole "
    "(kubernetes/operator-rbac.yaml) grants get/list/watch/create/update/"
    "patch/delete on namespaces, resourcequotas, and limitranges (core API "
    "group) and on rolebindings (rbac.authorization.k8s.io), get/list/"
    "watch/create/update/patch/delete on its own "
    "namespacerequests/namespacerequests-status, and read-only get/list/"
    "watch on customresourcedefinitions — no Secret, Pod, or wildcard (*) "
    "resource access is granted, and the ClusterRoleBinding attaches this "
    "only to the platform-operator ServiceAccount in platform-system, not "
    "to any broader group."
)
doc.add_paragraph(
    "Container-level hardening actually codified in-cluster today is "
    "limited to the operator Deployment: runAsNonRoot: true, runAsUser: "
    "10001 at the pod level, plus allowPrivilegeEscalation: false, "
    "readOnlyRootFilesystem: true, and capabilities.drop: [ALL] at the "
    "container level. Both Dockerfiles (backend and operator) additionally "
    "create and USER-switch to uid 10001 at the image level, independent "
    "of whatever Deployment manifest eventually runs them."
)
doc.add_paragraph(
    "Performance/scaling considerations: the dominant cost as the number "
    "of managed namespaces grows is the N+1 query pattern in "
    "list_namespaces() (one extra Kubernetes API call per namespace, on "
    "every 30-second frontend poll from every open browser tab). For a "
    "small platform team (tens of namespaces, a handful of concurrent "
    "portal users) this is unlikely to be noticeable; it is the first "
    "thing to revisit if this system were scaled to hundreds of managed "
    "namespaces or many concurrent viewers, since API server list/get "
    "calls and the client-side rate limiter (the Python kubernetes client's "
    "default QPS/burst settings, unmodified here) would start to bind."
)

# ---------------------------------------------------------------------------
# 9. Appendix
# ---------------------------------------------------------------------------
doc.add_heading1("9. Appendix")

doc.add_heading2("9.1 Repo module/file map")
doc.add_code_block(
    "Darviq-Portal/\n"
    "├── backend/\n"
    "│   ├── main.py           FastAPI app: routes, CORS, request validation\n"
    "│   ├── k8s_client.py     Kubernetes API calls: create/list/delete namespace + quota/limitrange/rolebinding\n"
    "│   ├── models.py         NamespaceRequest / NamespaceStatus dataclasses\n"
    "│   ├── requirements.txt  fastapi, uvicorn, kubernetes, pydantic\n"
    "│   └── Dockerfile        python:3.12-slim, non-root uid 10001, uvicorn entrypoint\n"
    "├── operator/\n"
    "│   ├── operator.py       kopf handlers: on.create / on.delete for NamespaceRequest\n"
    "│   ├── requirements.txt  kopf, kubernetes\n"
    "│   └── Dockerfile        python:3.12-slim, non-root uid 10001, `kopf run --standalone`\n"
    "├── frontend/\n"
    "│   └── index.html        Static portal: request form + namespace table, 30s poll\n"
    "├── kubernetes/\n"
    "│   ├── crd-namespacerequest.yaml   NamespaceRequest CRD (platform.company.io/v1)\n"
    "│   ├── operator-rbac.yaml          ServiceAccount + ClusterRole + ClusterRoleBinding\n"
    "│   └── operator-deployment.yaml    Operator Deployment (platform-system namespace)\n"
    "├── .github/workflows/\n"
    "│   └── build-push.yaml   CI: matrix build [backend, operator] -> GHCR on push to main\n"
    "└── README.md"
)

doc.add_heading2("9.2 Environment variable / configuration reference")
doc.add_table(
    headers=["Variable", "Component", "Default", "Purpose"],
    rows=[
        ["ALLOWED_ORIGINS", "backend/main.py", "\"*\" (all origins)", "Comma-separated CORS allow-list; should be restricted before any non-local deployment."],
        ["(kubeconfig / in-cluster ServiceAccount)", "backend/k8s_client.py, operator/operator.py", "Auto-detected", "Standard Kubernetes client credential resolution: in-cluster first, local kubeconfig fallback. Not a named env var read directly by this code."],
        ["API (JS constant, not an env var)", "frontend/index.html", "\"http://localhost:8080\"", "Hardcoded backend base URL; must be edited in the file to point elsewhere since there is no build-time or runtime injection today."],
    ],
)

doc.add_heading2("9.3 Change history")
doc.add_table(
    headers=["Version", "Date", "Description"],
    rows=[["1.0", DATE, "Initial low-level design document"]],
)

doc.save("Darviq_Portal_Low_Level_Design.docx")
print("LLD written")
