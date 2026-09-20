COMPOSE := docker compose

.PHONY: help setup up down restart logs backend-test frontend-test test lint format webhook backend-shell frontend-shell clean

help:
	@echo "Available commands:"
	@echo "  make setup           Create the .env file from .env.example"
	@echo "  make up              Build and start the backend and the frontend"
	@echo "  make down            Stop everything"
	@echo "  make restart         Restart both services"
	@echo "  make logs            Follow the logs of both services"
	@echo "  make test            Run the backend and the frontend test suites"
	@echo "  make backend-test    Run the backend test suite"
	@echo "  make frontend-test   Run the frontend test suite"
	@echo "  make lint            Check the backend code style and the frontend types"
	@echo "  make format          Apply the backend code style"
	@echo "  make webhook         Send a signed products/update webhook to the backend"
	@echo "  make backend-shell   Open a shell inside the backend container"
	@echo "  make frontend-shell  Open a shell inside the frontend container"
	@echo "  make clean           Remove containers and volumes"

setup: .env
	@echo "Environment file ready. Run: make up"

.env:
	cp .env.example .env

up: .env
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs --follow

backend-test:
	$(COMPOSE) run --rm backend pytest -v

frontend-test:
	$(COMPOSE) run --rm --no-deps frontend sh -c "npm install --no-audit --no-fund --silent && npm run test"

test:
	@failures=0; \
	$(MAKE) backend-test || failures=1; \
	$(MAKE) frontend-test || failures=1; \
	if [ $$failures -ne 0 ]; then echo "Some tests failed."; exit 1; fi

lint:
	$(COMPOSE) run --rm backend ruff check .
	$(COMPOSE) run --rm --no-deps frontend sh -c "npm install --no-audit --no-fund --silent && npm run typecheck"

format:
	$(COMPOSE) run --rm backend ruff format .
	$(COMPOSE) run --rm backend ruff check --fix .

webhook:
	$(COMPOSE) exec backend python -m scripts.send_product_update_webhook $(ARGUMENTS)

backend-shell:
	$(COMPOSE) exec backend bash

frontend-shell:
	$(COMPOSE) exec frontend bash

clean:
	$(COMPOSE) down --volumes --remove-orphans
