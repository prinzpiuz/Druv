#!/bin/bash

source .env

COMPOSE_DIR=${COMPOSE_DIR}
NETWORK_NAME=${NETWORK_NAME}
NETWORK_SUBNET=${NETWORK_SUBNET}


setup_environment() {
    if [ -x "./logo.sh" ]; then
        ./logo.sh
    else
        echo "Warning: logo.sh not found or not executable."
    fi

    echo "$(date): Starting service management routine."

    if ! cd "$COMPOSE_DIR"; then
        echo "Error: Could not change to directory $COMPOSE_DIR" >&2
        exit 1
    fi
    echo "Switched to directory: $COMPOSE_DIR"
}

docker_down() {
    echo "Stopping Docker Compose services..."

    if ! docker compose down --remove-orphans; then
        echo "Failed to stop services" >&2
        exit 1
    fi

    echo "Services stopped successfully."
    sleep 5
}

prune_and_network_setup() {
    echo "--- Full Rebuild Initiated ---"

    echo "Pruning entire Docker system (-a -f)..."
    if ! docker system prune -a -f; then
        echo "Warning: Docker system prune failed, but continuing with service restart." >&2
    fi

    echo "Creating/ensuring network '$NETWORK_NAME' with subnet '$NETWORK_SUBNET'..."
    if ! docker network create --subnet="$NETWORK_SUBNET" "$NETWORK_NAME"; then
        echo "Warning: Failed to create/ensure network '$NETWORK_NAME'. Compose will use defaults." >&2
    fi
}

docker_kill() {
    echo "Killing all running Docker containers..."

    if ! docker kill $(docker ps -q); then
        echo "Warning: Failed to kill some or all containers." >&2
    fi

    echo "All running Docker containers have been killed."
}

docker_up() {
    echo "Starting Docker Compose services with rebuild and force-recreate..."

    if ! docker compose up -d --remove-orphans --build --force-recreate; then
        echo "Failed to start services" >&2
        echo "Killing all running Docker containers and retrying..."
        docker_kill
        if ! docker compose up -d --remove-orphans --build --force-recreate; then
            echo "Retry failed: Could not start services" >&2
            exit 1
        fi
        exit 1
    fi

    echo "Docker Compose services down and successfully restarted."
}



main() {
    setup_environment

    if [ "$1" == "--all" ]; then
        prune_and_network_setup
    fi

    docker_down

    docker_up
}


main "$@"
