.DEFAULT_GOAL := help

QDRANT_URL ?= http://127.0.0.1:6333
QDRANT_COLLECTION ?= health_guidance

.PHONY: help install qdrant-up qdrant-ready qdrant-index qdrant-down frontend backend dev

help:
	@printf '%s\n' \
		'First run: make install' \
		'Start all: make dev (indexes Qdrant if missing)' \
		'Frontend only: make frontend' \
		'Backend only: make backend' \
		'Stop Qdrant: make qdrant-down'

install:
	npm install
	uv sync --dev

qdrant-up:
	npm run qdrant:up

qdrant-ready: qdrant-up
	@if curl -fsS "$(QDRANT_URL)/collections/$(QDRANT_COLLECTION)" >/dev/null; then \
		echo "Qdrant collection '$(QDRANT_COLLECTION)' is ready."; \
	else \
		echo "Creating Qdrant collection '$(QDRANT_COLLECTION)'..."; \
		npm run qdrant:index; \
	fi

qdrant-index: qdrant-up
	npm run qdrant:index

qdrant-down:
	npm run qdrant:down

frontend:
	npm run dev

backend:
	npm run dev:api

dev: qdrant-ready
	$(MAKE) --no-print-directory -j2 backend frontend
