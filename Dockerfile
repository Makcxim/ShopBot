FROM ghcr.io/astral-sh/uv:0.5.29 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple/

COPY . .

# manage.py лежит внутри shopbot/
WORKDIR /app/shopbot
