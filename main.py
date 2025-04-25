import logging
import os
from base64 import b64encode
from enum import Enum
from random import choice
from traceback import print_exc

from azure.identity import UsernamePasswordCredential
from docker.models.containers import Container
from docker.models.images import Image

try:
    from azure.mgmt.web import WebSiteManagementClient
    from azure.mgmt.web.models import NameValuePair, Site, SiteConfig
except ImportError as e:
    raise ImportError(
        "Check Dockerfile and azure.mgmt.web.models.py. Some packages were removed for optimization"
    ) from e
from string import Template

import docker
from azure.storage.fileshare import ShareFileClient
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from utils import create_logger

load_dotenv()

logging.getLogger("azure").setLevel(logging.ERROR)

SUBSCRIPTION_ID = os.environ["AZURE_SUBSCRIPTION_ID"]
GROUP_NAME = os.environ["AZURE_GROUP_NAME"]
APP_PLAN = os.environ["AZURE_APP_PLAN"]
FILE_SHARE_CONNECTION_STRING = os.environ["AZURE_FILE_SHARE_CONNECTION_STRING"]
FILE_SHARE_NAME = os.environ["AZURE_FILE_SHARE_NAME"]
AZURE_PASSWORD = os.environ["AZURE_PASSWORD"]
AZURE_USERNAME = os.environ["AZURE_USERNAME"]
AZURE_CLIENT_ID = os.environ["AZURE_CLIENT_ID"]

logger = create_logger("main")
logger.setLevel(
    logging.INFO if os.environ.get("DEBUG") not in ("True", "true") else logging.DEBUG
)


class DashBoardType(str, Enum):
    GRAFANA = "grafana"
    DASH = "dash"


class DeploymentType(str, Enum):
    AZURE = "Azure"
    DOCKER = "Docker"


class UploadFields(BaseModel):
    user_id: str
    source: str
    dashboard_type: DashBoardType
    deployments: list[DeploymentType]


def generate_base64_compose(dashboard_type: DashBoardType) -> str:
    path = f"{dashboard_type.value}/docker-compose.yml"
    with open(path, "r") as f:
        compose = f.read()
    return b64encode(compose.encode("utf-8")).decode("utf-8")


def upload_file_to_share(data: UploadFields):
    file_share = ShareFileClient.from_connection_string(
        conn_str=FILE_SHARE_CONNECTION_STRING,
        share_name=FILE_SHARE_NAME,
        file_path=f"{data.user_id}_{data.dashboard_type.value}.json",
    )

    file_share.upload_file(data.source)


def find_existing_webapp_by_userid(
    user_id: str,
    dashboard_type: DashBoardType,
    client: WebSiteManagementClient,
) -> Site | None:
    for existing_name in client.web_apps.list():
        if user_id in existing_name.name and dashboard_type.value in existing_name.name:
            return existing_name
    return None


def create_web_app(
    compose_b64: str,
    user_id: str,
    dashboard_type: DashBoardType,
    client: WebSiteManagementClient,
    plan,
) -> str:
    # app_settings aka environment variables
    app_settings = {
        k.removeprefix("APP_"): v for k, v in os.environ.items() if k.startswith("APP_")
    }
    substituted = app_settings["URL_CONFIG"].replace("$$file_name", f"{user_id}_{dashboard_type.value}.json")
    app_settings["URL_CONFIG"] = substituted
    web_app_name = f"sag-{user_id}-{dashboard_type.value}"

    result = client.web_apps.begin_create_or_update(
        GROUP_NAME,
        web_app_name,
        Site(  # type: ignore
            type="Microsoft.Web/sites",
            kind="app,linux,container",
            location="Germany West Central",
            client_affinity_enabled=False,
            server_farm_id=plan.id,
            https_only=True,
            site_config=SiteConfig(
                linux_fx_version="COMPOSE|{}".format(compose_b64),
                ftps_state="FtpsOnly",
                always_on=False,
                app_settings=[
                    NameValuePair(
                        name=k,
                        value=v,
                    )
                    for k, v in app_settings.items()
                ],
                http_logging_enabled=True,
            ),
        ),
    ).result()

    logger.info(f"Webapp {result.name} created.")

    return (
        result.host_names[0]
        if result.host_names[0].startswith("http")
        else f"https://{result.host_names[0]}"
    )


def delete_web_app(web_app_name: str):
    credential = UsernamePasswordCredential(
        AZURE_CLIENT_ID, AZURE_USERNAME, AZURE_PASSWORD
    )
    client = WebSiteManagementClient(
        credential, SUBSCRIPTION_ID, api_version="2018-02-01"
    )  # NOTE: api version is important! this is the latest version that is supported and it works
    client.web_apps.delete(GROUP_NAME, web_app_name, delete_empty_server_farm=False)


def get_exposed_port(image: Image) -> str | None:
    config = image.attrs.get("Config")
    if not config:
        return

    port = config.get("ExposedPorts")
    if not port:
        return

    return list(port.keys())[0]


def start_local_container(
    client: docker.DockerClient,
    user_id: str,
    dashboard_type: DashBoardType,
    web_app_name: str,
):
    image_name: str = (
        "sagittarius.azurecr.io/grafana_dashboard:latest"
        if dashboard_type == "grafana"
        else "local/dash_dashboard:latest"
    )

    app_settings = {
        k.removeprefix("APP_"): v for k, v in os.environ.items() if k.startswith("APP_")
    }
    app_settings["URL_CONFIG"] = Template(app_settings["URL_CONFIG"]).safe_substitute(
        file_name=f"{user_id}_{dashboard_type.value}.json"
    )
    app_settings["FILE_PATH"] = app_settings["URL_CONFIG"]
    app_settings["GF_INSTALL_PLUGINS"] = "marcusolsson-json-datasource"
    app_settings["GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS"] = (
        "smartcomm-bulletgraph-panel,smartcomm-calendar-panel,smartcomm-extremevalues-panel,smartcomm-map-panel,smartcomm-multiplelinechart-panel,smartcomm-simpleline-panel,smartcomm-minmaxbarchart-panel"
    )
    app_settings["GF_FEATURE_TOGGLES_ENABLE"] = "transformationsVariableSupport"

    if "sagittarius.azurecr.io" in image_name:
        logger.debug(f"Pulling image {image_name} for {client.info()['Architecture']}")
        image = client.images.pull(image_name)
        logger.debug(
            f"Image {image_name}/{image.attrs['Architecture']} pulled ({image.id})"
        )
    else:
        logger.debug(f"Using local image {image_name}")
        image = client.images.get(image_name)

    port = get_exposed_port(image)
    if not port:
        raise ValueError("No port exposed in the image")

    _container = client.containers.run(
        image,
        detach=True,
        environment=app_settings,
        # ports={port: 61234},
        ports={port: 7777},
        name=web_app_name,
        extra_hosts={"localhost": "host-gateway"},
    )


def restart_local_or_remove(
    client: docker.DockerClient, dashboard_type: DashBoardType, container: Container
) -> bool:
    """Returns `True` if container was restarted else `False`"""
    
    repo_digests = container.image.attrs.get("RepoDigests", [])

    if repo_digests and (
        client.images.get_registry_data(
            container.image.attrs["RepoDigests"][0].split("@")[0]
        ).id
        != container.image.id
    ):
        logger.debug(f"Image {container.image.id} is outdated. Removing container...")
        client.containers.get(container.name).remove(force=True)
        return False

    if container.name[container.name.rfind("-") + 1 :] == dashboard_type.value:
        client.containers.get(container.name).restart()
        return True

    client.containers.get(container.name).remove(force=True)
    return False


def deploy_locally(
    user_id: str,
    dashboard_type: DashBoardType,
):
    client = docker.from_env()
    logger.debug(client.version())
    client.login(
        "sagittarius",
        password=os.environ["DOCKER_REG_PASSWORD"],
        registry="sagittarius.azurecr.io",
    )

    web_app_name = f"sag-{user_id}-{dashboard_type.value}"
    # URL = "http://localhost:61234"
    URL = "http://localhost:7777"

    running_containers: list[Container] = client.containers.list(
        filters={"name": web_app_name[: web_app_name.rfind("-")]}, all=True
    )
    if len(running_containers) > 1:
        raise Exception("Found more than one dashboard container")

    if len(running_containers) == 1 and restart_local_or_remove(
        client, dashboard_type, running_containers[0]
    ):
        logger.debug(f"Container {web_app_name} already exists. Restarting...")
        return URL

    start_local_container(client, user_id, dashboard_type, web_app_name)

    logger.info(f"Container {web_app_name} created.")

    return URL


def deploy_azure(user_id: str, dashboard_type: DashBoardType) -> str:
    credential = UsernamePasswordCredential(
        AZURE_CLIENT_ID, AZURE_USERNAME, AZURE_PASSWORD
    )
    client = WebSiteManagementClient(
        credential, SUBSCRIPTION_ID, api_version="2018-02-01"
    )  # NOTE: api version is important! this is the latest version that is supported and it works

    if (
        existing_webapp := find_existing_webapp_by_userid(
            user_id, dashboard_type, client
        )
    ) is not None:
        client.web_apps.restart(GROUP_NAME, existing_webapp.name)
        logger.info(f"Webapp {existing_webapp.name} already exists. Restarting...")

        return (
            existing_webapp.host_names[0]
            if existing_webapp.host_names[0].startswith("http")
            else f"https://{existing_webapp.host_names[0]}"
        )

    plan = client.app_service_plans.get(GROUP_NAME, APP_PLAN)
    base64_compose = generate_base64_compose(dashboard_type)
    hostname = create_web_app(base64_compose, user_id, dashboard_type, client, plan)

    return hostname


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse("/status")


@app.post("/deploy")
async def deploy(fields: UploadFields) -> str | list[str]:
    hostnames = []

    try:
        upload_file_to_share(fields)
        logger.info(f"Preparing deployment...{fields}")
        for deployment_entry in fields.deployments:
            if deployment_entry == DeploymentType.AZURE:
                hostname = deploy_azure(fields.user_id, fields.dashboard_type)
                logger.info(f"Deployed to Azure for {fields.user_id}: {hostname}")
            else:
                hostname = deploy_locally(fields.user_id, fields.dashboard_type)
                logger.info(f"Deployed locally for {fields.user_id}: {hostname}")
            hostnames.append(hostname)

        if len(hostnames) == 1:
            return hostnames[0]
        return hostnames

    except Exception as e:
        print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
def status() -> str:
    statuses = ["Single", "In a relationship", "Married", "In love", "It's complicated"]
    return choice(statuses)
