FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r /app/requirements.lock
COPY . /app

EXPOSE 8000
