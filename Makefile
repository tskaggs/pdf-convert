.PHONY: help build up down logs restart clean test

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build the Docker image
	docker-compose build

up: ## Start the service
	docker-compose up -d

down: ## Stop the service
	docker-compose down

logs: ## View service logs
	docker-compose logs -f

restart: ## Restart the service
	docker-compose restart

clean: ## Remove containers and volumes
	docker-compose down -v

test: ## Test the API (requires service to be running)
	curl -X GET http://localhost:8000/ || echo "Service not running. Start with: make up"

