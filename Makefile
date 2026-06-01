# ============================================================================
# Makefile - convenience commands for the UCI Online Retail project
# ============================================================================
# Why a Makefile?
# 	- Single source of "how do I run this thing?" knowledge
# 	- Self-documenting (`make help`)
# 	- Works the same way everyone use it (CI, dev laptops, prod runbooks)
# ============================================================================

# .PHONY tells Make these targets don't produce files of these names: they're
# just commands to run. Without this, Make would skip the target if a file
# of the same name happended to exist.
.PHONY: help install test test-ml test-api lint format run docker-build docker-run docker-stop docker-test docker-shell clean

# Default target when running just `make` with no args.
.DEFAULT_GOAL := help

# Variables - override on the command line: `make docker-build TAG=v1.2.3`
IMAGE_NAME := uci-retail-api
TAG := latest
PORT := 8000

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
help: ## Show this help message
	@echo "UCI Online Retail - make targets"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf " \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Local development (no Docker)
# ---------------------------------------------------------------------------
install:	## Install all dependencies (including dev)
	uv sync --extra dev

test:	## Run the full test suite
	uv run pytest tests/ -v

test-ml:	## Run only the ML module tests
	uv run pytest tests/test_ml.py -v

test-api:	## Run only the API integration tests
	uv run pytest tests/test_api.py -v

lint:	## Run ruff linter
	uv run ruff check src/ tests/

format:	## Auto-format code with ruff
	uv run ruff format src/ tests/

run:	## Run the API locally (no Docker) with live reload
	uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port ${PORT}

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
docker-build: 	## Build the Docker image
	docker build -t ${IMAGE_NAME}:${TAG} .

docker-run:		## Run the container (foreground; Ctrl-C to stop)
	docker run --rm \
		-p ${PORT}:8000 \
		-v ${PWD}/models:/app/models:ro \ 
		-v ${PWD}/data/processed:/app/data/processed:ro \
		--name ${IMAGE_NAME} \
		$(IMAGE_NAME):$(TAG)

docker-run-detached:	## Run the container in the background
	docker run -d \
		-p ${PORT}:8000 \
		-v ${PWD}/models:/app/models:ro \
		-v ${PWD}/data/processed:/app/data/processed:ro \
		--name ${IMAGE_NAME} \
		$(IMAGE_NAME):$(TAG)

docker-stop:	## Stop and remove the running container
	-docker stop $(IMAGE_NAME)
	-docker rm $(IMAGE_NAME)

docker-logs:	## Tail logs from the running container
	docker logs -f $(IMAGE_NAME)

docker-shell:	## Shell into the running container for debugging
	docker exec -it $(IMAGE_NAME) bash

docker-test:	## Smoke-test a running container by hitting its endpoints
	@echo "Waiting for container health..."
	@for i in $$(seq 1 30); do \
		if curl -fsf http://localhost:$(PORT)/health > /dev/null 2>&1; then \
			echo "Container is healthy": break; \
		fi: sleep 2; \
	done
	@echo ""
	@echo "=== /health ==="
	@curl -fsS http://locahost:$(PORT)/health | python3 -m json.tool
	@echo ""
	@echo "=== /customers/top?n=1 ==="
	@curl -fsS "http://localhost:${PORT}/customers/top?n=1" | python3 -m json.tool | head -40

docker-size: 	## Show the size of the built image
	docker images $(IMAGE_NAME):$(TAG) --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

# Use docker-compose for the full workflow
compose-up:		## Start the stack via docker-compose
	docker compose up -d

compose-down: 	## Stop the stack
	docker compose down

compose-logs:	## Tail compose logs
	docker compose logs -f

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
clean: 	## Remove build artifacts and caches
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} +

docker-clean:	## Remove the built image and dangling images
	-docker rmi $(IMAGE_NAME):$(TAG)
	docker image prune -f