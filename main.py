import dataclasses
import json
import logging
import os
import socket
import urllib.parse
from collections import defaultdict
from typing import Optional

import bs4
import requests
import urllib3
import uvicorn
from bs4 import Tag
from fastapi import FastAPI, HTTPException
from thefuzz import fuzz

from streamingprovider.models import (
    Provider,
    PlexResolverResponseItem,
    SearchProvider,
    TitleSearchRequest,
    PlexResolverMovie,
    SearchItem,
    StreamProvider,
    SearchRequest,
)

BASE_URL = os.getenv("BASE_URL") or "https://werstreamt.es"
SEARCH_PATH = os.getenv("SEARCH_PATH") or "/suggestTitle?term="


def create_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    import sys

    logger = logging.Logger(name)
    ch = logging.StreamHandler(sys.stdout)

    formatting = "[{}] %(asctime)s\t%(levelname)s\t%(module)s.%(funcName)s#%(lineno)d | %(message)s".format(
        name
    )
    formatter = logging.Formatter(formatting)
    ch.setFormatter(formatter)

    logger.addHandler(ch)
    logger.setLevel(level)

    return logger


app = FastAPI()


@dataclasses.dataclass
class Plex(Provider, SearchProvider):
    def __init__(self):
        super().__init__("plex")
        self.url = os.getenv("PLEX_RESOLVER_URL") or "http://plex-resolver/movies"
        self.use_name_prefix = True

    def get_movies(self, url: str = None) -> Optional[list[PlexResolverResponseItem]]:
        if not url:
            url = self.url

        try:
            result = requests.get(url)
        except (
            requests.exceptions.ConnectionError,
            socket.gaierror,
            urllib3.exceptions.MaxRetryError,
        ) as e:
            create_logger("get_movies").error(f"Failed to retrieve {url} due to {e}")
            return None

        return [
            PlexResolverResponseItem.from_json(j) for j in result.json().get("data", [])
        ]

    def get_streaming_providers(self, info: str, **kwargs):
        raise NotImplementedError()

    def search(
        self, request: TitleSearchRequest, **kwargs
    ) -> Optional[dict[str, list[PlexResolverMovie]]]:
        results = defaultdict(list)
        response = self.get_movies()
        if not response:
            return None

        for response in response:
            movies = response.movies

            for movie in movies:
                if (
                    fuzz.token_set_ratio(request.title, movie.title) > 80
                    or request.title.lower() in movie.title.lower()
                ):
                    item = SearchItem(title=movie.title)
                    if request.year:
                        if request.year == movie.year:
                            item.year = movie.year
                            results[response.name].append(item)
                    else:
                        results[response.name].append(item)

        return results


@dataclasses.dataclass
class WerStreamtEs(Provider, SearchProvider):
    def __init__(self):
        super().__init__("werstreamt.es")

    def get_by_id(self, _id: str) -> Optional[list[StreamProvider]]:
        url = f"https://www.werstreamt.es/film/details/{_id}"
        return self.get_streaming_providers(url)

    def get_streaming_providers(
        self, info: str, **kwargs
    ) -> Optional[set[StreamProvider]]:
        try:
            result = requests.get(info)
            body = result.text
        except (
            requests.exceptions.ConnectionError,
            socket.gaierror,
            urllib3.exceptions.MaxRetryError,
        ):
            create_logger("get_streaming_providers").error(
                "Failed to retrieve {} due to"
            )
            return None

        soup = bs4.BeautifulSoup(body, "lxml")
        provider_elements: list[Tag] = soup.find_all(attrs={"class": "provider"})[1:]

        providers = set()
        for element in provider_elements:
            name_element = element.find("a", attrs={"class": "left"})
            # value for sky is `Sky Go\nsky` for example
            name = name_element.text.strip().splitlines()[0]

            flatrate = element.find("i", {"class": "fi-check"})
            if not flatrate:
                create_logger("get_streaming_providers").info(
                    f"skip {name} since it's not a flatrate"
                )
                continue

            options = json.loads(element.get("data-options"))
            stream_provider_id = options.get("StreamProviderID")
            providers.add(StreamProvider(stream_provider_id, name))

        return providers

    def search(
        self, request: TitleSearchRequest, **kwargs
    ) -> Optional[dict[str, list[SearchItem]]]:
        title = urllib.parse.quote(request.title)
        url = "https://www.werstreamt.es/suche/suggestTitle?term=" + title

        req = requests.get(url, headers={"Accept": "application/json"})
        if req.ok:
            js = req.json()
            search_items: list[SearchItem] = [
                SearchItem.from_json_item(key, value)
                for key, value in js.items()
                if key.startswith("id-")
            ]
            if request.year is not None:
                search_items = [
                    item for item in search_items if item.year == request.year
                ]

            results = defaultdict(list)
            for search_item in search_items:
                for provider in self.get_by_id(search_item.id):
                    results[provider.name].append(search_item)

            return results

        return None


@app.post("/search")
def movie_by_title(req: TitleSearchRequest):
    results = []
    providers = [WerStreamtEs()]

    for provider in providers:
        if result := provider.search(req):
            if isinstance(result, dict):
                for name, movies in result.items():
                    if provider.use_name_prefix:
                        name = f"{provider.name}-{name}"

                    item = {"name": name, "movies": movies}
                    results.append(item)
            else:
                results.append({"name": provider.name, "movies": result})

    if not results:
        raise HTTPException(status_code=404, detail="Title not found")

    return {"results": results}


@app.post("/")
def movie_by_link(req: SearchRequest):
    results = {}
    providers = [WerStreamtEs()]

    for provider in providers:
        results[provider.name] = provider.get_streaming_providers(req.werstreamtesLink)

    return results


if __name__ == "__main__":
    create_logger("__main__").info("Starting")
    # noinspection PyTypeChecker
    uvicorn.run(app)
