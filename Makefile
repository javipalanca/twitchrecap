# Variables
IMAGE_NAME = llmbot
CONTAINER_NAME = llmbot_container
DOCKER_FILE = Dockerfile

# Build the Docker image
build:
	@echo "Building Docker image..."
	docker build -t $(IMAGE_NAME) -f $(DOCKER_FILE) .

# Run the container
run:
	@echo "Running container..."
	docker run -d --name $(CONTAINER_NAME) -p 5555:5555 \
		--env-file .env \
		$(IMAGE_NAME)

# Stop and remove the container
stop:
	@echo "Stopping container..."
	-docker stop $(CONTAINER_NAME)
	@echo "Removing container..."
	-docker rm $(CONTAINER_NAME)

# Restart the container (stop, remove, build and run)
restart: stop build run

# Show container logs
logs:
	docker logs -f $(CONTAINER_NAME)

# Execute bash inside container
shell:
	docker exec -it $(CONTAINER_NAME) bash

# Build and run the container
up: build run

# Clean everything (stop and remove container, remove image)
clean: stop
	@echo "Removing image..."
	-docker rmi $(IMAGE_NAME)

# Show container status
status:
	@echo "Container status:"
	@docker ps -a | grep $(CONTAINER_NAME) || echo "Container not found"

# Help command
help:
	@echo "Available commands:"
	@echo "  make build     - Build the Docker image"
	@echo "  make run       - Run the container"
	@echo "  make stop      - Stop and remove the container"
	@echo "  make restart   - Restart the container"
	@echo "  make logs      - Show container logs"
	@echo "  make shell     - Execute bash inside container"
	@echo "  make up        - Build and run the container"
	@echo "  make clean     - Clean everything"
	@echo "  make status    - Show container status"
	@echo "  make help      - Show this help message"

.PHONY: build run stop restart logs shell up clean status help