FROM python:3.12-slim

RUN apt-get update && \
    apt-get install gcc -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

ENV TZ=Europe/Berlin

ADD main.py .
ADD streamingprovider/ streamingprovider/
ADD requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

CMD uvicorn main:app --host 0.0.0.0
