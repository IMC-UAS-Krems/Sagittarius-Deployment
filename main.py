import logging
import os
from base64 import b64encode
from random import choice

from azure.identity import UsernamePasswordCredential
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.web.models import Site, SiteConfig, NameValuePair
from azure.storage.fileshare import ShareFileClient
from dotenv import load_dotenv
from string import Template

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

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
GRAFANA_API_URL = os.environ.get("GRAFANA_API_URL") or "http://localhost:9000"

logger = create_logger("main")
logger.setLevel(
    logging.INFO if os.environ.get("DEBUG") not in ("True", "true") else logging.DEBUG
)


class UploadFields(BaseModel):
    user_id: str
    source: str


def generate_base64_compose() -> str:
    path = "grafana/docker-compose.yml"
    with open(path, "r") as f:
        compose = f.read()
    return b64encode(compose.encode("utf-8")).decode("utf-8")


def upload_file_to_share(data: UploadFields):
    file_share = ShareFileClient.from_connection_string(
        conn_str=FILE_SHARE_CONNECTION_STRING,
        share_name=FILE_SHARE_NAME,
        file_path=f"{data.user_id}_config.json",
    )
    grafana_config = requests.post(
        GRAFANA_API_URL,
        data=data.source,
        headers={"Content-Type": "application/json"},
    )
    if grafana_config.status_code != 200:
        logger.error(f"Grafana API returned {grafana_config.status_code}")
        logger.error(grafana_config.text)
        raise HTTPException(
            status_code=500, detail=f"Grafana API returned {grafana_config.status_code}"
        )

    file_share.upload_file(grafana_config.text)


def find_existing_webapp_by_userid(
    user_id: str, client: WebSiteManagementClient
) -> Site | None:
    for existing_name in client.web_apps.list():
        if user_id in existing_name.name:
            return existing_name
    return None


def create_web_app(
    compose_b64: str,
    user_id: str,
) -> str:
    credential = UsernamePasswordCredential(
        AZURE_CLIENT_ID, AZURE_USERNAME, AZURE_PASSWORD
    )
    client = WebSiteManagementClient(
        credential, SUBSCRIPTION_ID, api_version="2018-02-01"
    )  # NOTE: api version is important! this is the latest version that is supported and it works

    plan = client.app_service_plans.get(GROUP_NAME, APP_PLAN)

    if (existing_webapp := find_existing_webapp_by_userid(user_id, client)) is not None:
        client.web_apps.restart(GROUP_NAME, existing_webapp.name)
        logger.info(f"Webapp {existing_webapp.name} already exists. Restarting...")

        return (
            existing_webapp.host_names[0]
            if existing_webapp.host_names[0].startswith("http")
            else f"https://{existing_webapp.host_names[0]}"
        )

    # app_settings aka environment variables
    app_settings = {
        k.removeprefix("APP_"): v for k, v in os.environ.items() if k.startswith("APP_")
    }
    logger.debug(f"App settings: {app_settings}")
    logger.debug(f"Environment variables: {os.environ}")
    app_settings["URL_CONFIG"] = Template(app_settings["URL_CONFIG"]).safe_substitute(
        file_name=f"{user_id}_config.json"
    )
    web_app_name = f"sag-{user_id}-grafana"

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
async def deploy(fields: UploadFields) -> str:
    try:
        upload_file_to_share(fields)
        base64_compose = generate_base64_compose()
        hostname = create_web_app(base64_compose, fields.user_id)

        return hostname
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
def status() -> str:
    statuses = ["Single", "In a relationship", "Married", "In love", "It's complicated"]
    return choice(statuses)
