import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from models import NamespaceRequest, NamespaceStatus
from typing import List
import datetime

logger = logging.getLogger(__name__)

def load_k8s_config():
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()

load_k8s_config()

core_v1    = client.CoreV1Api()
rbac_v1    = client.RbacAuthorizationV1Api()
custom_api = client.CustomObjectsApi()

GROUP   = "platform.company.io"
VERSION = "v1"
PLURAL  = "namespacerequests"


def create_namespace(req: NamespaceRequest) -> dict:
    ns_name = f"{req.team_name}-{req.environment}".lower()

    # 1. Create namespace
    namespace = client.V1Namespace(
        metadata=client.V1ObjectMeta(
            name=ns_name,
            labels={
                "team":        req.team_name,
                "environment": req.environment,
                "managed-by":  "platform-portal",
            },
            annotations={
                "owner":        req.owner_email,
                "requested-by": req.requested_by,
                "created-at":   datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        )
    )
    try:
        core_v1.create_namespace(namespace)
        logger.info(f"Namespace {ns_name} created")
    except ApiException as e:
        if e.status == 409:
            logger.warning(f"Namespace {ns_name} already exists")
        else:
            raise

    # 2. Apply ResourceQuota
    quota = client.V1ResourceQuota(
        metadata=client.V1ObjectMeta(name="default-quota"),
        spec=client.V1ResourceQuotaSpec(
            hard={
                "requests.cpu":    req.cpu_limit,
                "requests.memory": req.memory_limit,
                "limits.cpu":      req.cpu_limit,
                "limits.memory":   req.memory_limit,
                "pods":            "20",
                "services":        "10",
            }
        )
    )
    try:
        core_v1.create_namespaced_resource_quota(ns_name, quota)
    except ApiException as e:
        if e.status != 409:
            raise

    # 3. Apply LimitRange (default limits for pods)
    limit_range = client.V1LimitRange(
        metadata=client.V1ObjectMeta(name="default-limits"),
        spec=client.V1LimitRangeSpec(limits=[
            client.V1LimitRangeItem(
                type="Container",
                default={"cpu": "500m",  "memory": "512Mi"},
                default_request={"cpu": "100m", "memory": "128Mi"},
            )
        ])
    )
    try:
        core_v1.create_namespaced_limit_range(ns_name, limit_range)
    except ApiException as e:
        if e.status != 409:
            raise

    # 4. Create team RoleBinding
    role_binding = client.V1RoleBinding(
        metadata=client.V1ObjectMeta(name=f"{req.team_name}-binding"),
        role_ref=client.V1RoleRef(
            api_group="rbac.authorization.k8s.io",
            kind="ClusterRole",
            name="edit"
        ),
        subjects=[client.V1Subject(
            kind="Group",
            api_group="rbac.authorization.k8s.io",
            name=f"team:{req.team_name}"
        )]
    )
    try:
        rbac_v1.create_namespaced_role_binding(ns_name, role_binding)
    except ApiException as e:
        if e.status != 409:
            raise

    return {"namespace": ns_name, "status": "created"}


def list_namespaces() -> List[NamespaceStatus]:
    results = []
    ns_list = core_v1.list_namespace(
        label_selector="managed-by=platform-portal"
    )
    for ns in ns_list.items:
        quota_list = core_v1.list_namespaced_resource_quota(ns.metadata.name)
        cpu    = "unknown"
        memory = "unknown"
        if quota_list.items:
            hard = quota_list.items[0].spec.hard or {}
            cpu    = hard.get("limits.cpu", "unknown")
            memory = hard.get("limits.memory", "unknown")

        results.append(NamespaceStatus(
            name       = ns.metadata.name,
            status     = ns.status.phase,
            created_at = ns.metadata.annotations.get("created-at"),
            cpu_limit  = cpu,
            memory_limit = memory,
            owner      = ns.metadata.annotations.get("owner", "unknown"),
        ))
    return results


def delete_namespace(name: str) -> dict:
    try:
        core_v1.delete_namespace(name)
        return {"namespace": name, "status": "deleted"}
    except ApiException as e:
        if e.status == 404:
            return {"namespace": name, "status": "not_found"}
        raise