FROM ghcr.io/blindfoldedsurgery/poetry:1.1.1-pipx-3.12-bookworm

WORKDIR /usr/src/app

ADD poetry.toml .
ADD poetry.lock .
ADD pyproject.toml .
ADD README.md .

ADD src/streamingprovider/ src/streamingprovider/

RUN poetry install --no-interaction --ansi --without dev --without types

CMD poetry run python src/streamingprovider/main.py
