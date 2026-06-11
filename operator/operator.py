"""
Kubernetes Operator using kopf.
Watches NamespaceRequest CRDs and auto-provisions namespaces.
"""

import kopf
import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException

try:
    config.load_incluster_config()
except Exception:
    config.load_kube_config()

core_v1 = client.CoreV1Api()
rbac_v1 = client.RbacAuthorizationV1Api()

logger = logging.getLogger(__name__)


@kopf.on.create("platform.company.io", "v1", "namespacerequests")
def on_namespace_request_created(spec, name, namespace, logger, **kwargs):
    team      = spec.get("teamName")
    env       = spec.get("environment")
    cpu       = spec.get("cpuLimit", "2")
    memory    = spec.get("memoryLimit", "4Gi")
    owner     = spec.get("ownerEmail")
    ns_name   = f"{team}-{env}".lower()

    logger.info(f"Processing NamespaceRequest: {name} → namespace: {ns_name}")

    # Create namespace
    ns = client.V1Namespace(
        metadata=client.V1ObjectMeta(
            name=ns_name,
            labels={"team": team, "environment": env, "managed-by": "platform-operator"},
            annotations={"owner": owner}
        )
    )
    try:
        core_v1.create_namespace(ns)
        logger.info(f"Created namespace: {ns_name}")
    except ApiException as e:
        if e.status != 409:
            raise kopf.PermanentError(f"Failed to create namespace: {e}")

    # Apply resource quota
    quota = client.V1ResourceQuota(
        metadata=client.V1ObjectMeta(name="default-quota"),
        spec=client.V1ResourceQuotaSpec(hard={
            "limits.cpu":    cpu,
            "limits.memory": memory,
            "pods":          "20",
        })
    )
    try:
        core_v1.create_namespaced_resource_quota(ns_name, quota)
    except ApiException as e:
        if e.status != 409:
            raise

    logger.info(f"Namespace {ns_name} fully provisioned")
    return {"namespace": ns_name, "status": "provisioned"}


@kopf.on.delete("platform.company.io", "v1", "namespacerequests")
def on_namespace_request_deleted(spec, name, logger, **kwargs):
    team    = spec.get("teamName")
    env     = spec.get("environment")
    ns_name = f"{team}-{env}".lower()

    try:
        core_v1.delete_namespace(ns_name)
        logger.info(f"Deleted namespace: {ns_name}")
    except ApiException as e:
        if e.status != 404:
            raise kopf.PermanentError(f"Failed to delete namespace: {e}")