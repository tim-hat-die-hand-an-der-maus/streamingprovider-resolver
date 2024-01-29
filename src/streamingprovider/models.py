import dataclasses
from abc import ABC, abstractmethod
from typing import Optional

import bs4
from pydantic import BaseModel


class IncompleteSearchItem(Exception):
    pass


@dataclasses.dataclass
class SearchItem:
    title: str
    id: Optional[str] = None
    year: Optional[int] = None
    type: Optional[str] = None

    @classmethod
    def from_json_item(cls, key: str, js: dict) -> "SearchItem":
        _id = key[3:]
        title = js["value"]
        label = js["label"]
        soup = bs4.BeautifulSoup(label, "lxml")
        span = soup.find("span")
        if not span:
            raise IncompleteSearchItem

        res = span.text.strip().split(", ")
        year: int | None
        if len(res) != 2:
            _type = res[0]
            year = None
        else:
            _type, _year = res
            year = int(_year)
        _type = _type.split("\n")[-1].strip()
        return cls(title, _id, year, _type)

    def to_json(self):
        return {
            "id": self.id,
            "title": self.title,
            "year": self.year,
            "type": self.type,
        }


class SearchRequest(BaseModel):
    werstreamtesLink: str


class TitleSearchRequest(BaseModel):
    title: str
    year: Optional[int] = None


@dataclasses.dataclass
class StreamProvider:
    id: Optional[str]
    name: str

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return hash(self.name.lower())


@dataclasses.dataclass
class SearchProvider(ABC):
    name: str

    @abstractmethod
    def search(self, request, **kwargs) -> Optional[list[SearchItem]]:
        pass


@dataclasses.dataclass
class Provider(ABC):
    name: str
    use_name_prefix: bool = False

    @abstractmethod
    def get_streaming_providers(self, info: str, **kwargs):
        pass


@dataclasses.dataclass
class PlexResolverMovie:
    title: str
    year: int

    @classmethod
    def from_json(cls, _json: dict) -> "PlexResolverMovie":
        return cls(_json["title"], _json["year"])


@dataclasses.dataclass
class PlexResolverResponseItem:
    name: str
    movies: list[PlexResolverMovie]
    error: Optional[str]  # is this correct?

    @classmethod
    def from_json(cls, _json: dict) -> "PlexResolverResponseItem":
        return cls(
            _json["name"],
            [PlexResolverMovie.from_json(movie) for movie in _json.get("movies", [])],
            _json["error"],
        )
