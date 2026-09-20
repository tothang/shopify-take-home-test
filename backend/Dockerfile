FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /service

RUN apt-get update \
    && apt-get install --yes --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-development.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt --requirement requirements-development.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "application.main:application", "--host", "0.0.0.0", "--port", "8000", "--reload"]
