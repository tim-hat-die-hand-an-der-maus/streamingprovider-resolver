import dataclasses
import json
import os
import socket
from typing import List, Optional, Dict

import bs4
import requests
import urllib3
import uvicorn
from bs4 import Tag
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from fastapi import FastAPI
from pydantic import BaseModel

LOG_DIRECTORY = "/var/log/werstreamtes" if os.name != "nt" else os.path.join(os.getenv("APPDATA"), "werstreamtes")
LOG_FILENAME = "log.docx"
BASE_URL = os.getenv("BASE_URL") or "https://werstreamt.es"
SEARCH_PATH = os.getenv("SEARCH_PATH") or "/suggestTitle?term="


def log(message: str):
    path = os.path.join(LOG_DIRECTORY, LOG_FILENAME)
    try:
        document = Document(path)
    except PackageNotFoundError:
        document = Document()

    document.add_paragraph(message)
    document.save(path)


class SearchRequest(BaseModel):
    werstreamtesLink: str


app = FastAPI()


def search_vodster_by_title(title_query: str):
    url = "/".join([BASE_URL, SEARCH_PATH, title_query])
    return requests.get(url)


@dataclasses.dataclass
class Provider:
    name: str
    options: Dict


def get_providers(link: str) -> Optional[List[Provider]]:
    try:
        result = requests.get(link)
        body = result.text
    except (requests.exceptions.ConnectionError, socket.gaierror, urllib3.exceptions.MaxRetryError):
        log("Failed to retrieve {} due to")
        return None

    soup = bs4.BeautifulSoup(body, "lxml")
    provider_elements: List[Tag] = soup.find_all(attrs={"class": "provider"})[1:]

    providers = []
    for element in provider_elements:
        name_element = element.find("a", attrs={"class": "left"})
        # value for sky is `Sky Go\nsky` for example
        name = name_element.text.strip().splitlines()[0]

        options = element.get("data-options")

        providers.append(Provider(name, options))

    return providers


@app.post("/")
def movie_by_link(req: SearchRequest):
    providers = get_providers(req.werstreamtesLink)

    return [provider.name for provider in providers]


if __name__ == "__main__":
    if not os.path.exists(LOG_DIRECTORY):
        os.makedirs(LOG_DIRECTORY)

    log("Starting")
    # noinspection PyTypeChecker
    uvicorn.run(app)
