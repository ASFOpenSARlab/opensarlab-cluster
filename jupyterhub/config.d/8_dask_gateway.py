# 1. Sets `DASK_GATEWAY__PROXY_ADDRESS` in the singleuser environment.
# 2. Adds the URL for the Dask Gateway JupyterHub service.
import os

import z2jh

portal_domain = z2jh.get_config("custom.OPENSCIENCELAB_PORTAL_DOMAIN", None)
gateway_service_api_token = z2jh.get_config("custom.DASK_GATEWAY_API_TOKEN", None)

dask_release_namespace = os.environ.get("OPENSCIENCELAB_DASK_NAMESPACE", "dask-gateway")
jupyterhub_lab_name = os.environ.get("JUPYTERHUB_LAB_NAME", "")

if jupyterhub_lab_name:
    lab_prefix = f"/lab/{jupyterhub_lab_name}"
else:
    lab_prefix = ""

# Internal address to connect to the Dask Gateway.
gateway_address = f"http://proxy-public{lab_prefix}/services/dask-gateway"
# gateway_address = f"{portal_domain}{lab_prefix}/services/dask-gateway"
c.KubeSpawner.environment.setdefault("DASK_GATEWAY__ADDRESS", gateway_address)

# Internal address for the Dask Gateway proxy.
gateway_proxy = f"gateway://traefik-dask-gateway-release.{dask_release_namespace}:80"
c.KubeSpawner.environment.setdefault("DASK_GATEWAY__PROXY_ADDRESS", gateway_proxy)

# Relative address for the dashboard link.
gateway_dashboard_link = f"{lab_prefix}/services/dask-gateway/"
c.KubeSpawner.environment.setdefault(
    "DASK_GATEWAY__PUBLIC_ADDRESS", gateway_dashboard_link
)

# Use JupyterHub to authenticate with Dask Gateway.
c.KubeSpawner.environment.setdefault("DASK_GATEWAY__AUTH__TYPE", "jupyterhub")

# Add service to JupyterHub
gateway_service_url = f"http://traefik-dask-gateway-release.{dask_release_namespace}"

# c.JupyterHub.services is defined eariler in the JupyterHub config
c.JupyterHub.services.append(
    {
        "name": "dask-gateway",
        "display": True,
        "api_token": gateway_service_api_token,
        "url": gateway_service_url,
    }
)
