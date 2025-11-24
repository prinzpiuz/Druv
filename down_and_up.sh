#!/bin/bash

RED='\033[0;31m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
NC='\033[0m'
COMPOSE_DIR=/home/druv/druv_setup
NETWORK_NAME=${NETWORK_NAME}
NETWORK_SUBNET=${NETWORK_SUBNET}

error_log() {
    echo -e "${RED}$1${NC}"
}

warning_log() {
    echo -e "${CYAN}$1${NC}"
}

success_log() {
    echo -e "${GREEN}$1${NC}"
}

setup_environment() {

    if ! source "$COMPOSE_DIR/.env"; then
        error_log "Error: Could not source .env file" >&2
        exit 1
    fi
    if ! cd "$COMPOSE_DIR"; then
        error_log "Error: Could not change to directory $COMPOSE_DIR" >&2
        exit 1
    fi
    success_log "Switched to directory: $COMPOSE_DIR"
    success_log "Environment variables loaded from .env file."
    if [ -x "./logo.sh" ]; then
        ./logo.sh
    else
        warning_log "Warning: logo.sh not found or not executable."
    fi

}

docker_down() {
    success_log "Stopping Docker Compose services..."

    if ! docker compose down --remove-orphans; then
        error_log "Failed to stop services" >&2
        docker_kill
        if ! docker compose down --remove-orphans; then
            error_log "Retry failed: Could not stop services" >&2
            exit 1
        fi
    fi

    success_log "Services stopped successfully."
}

prune_and_network_setup() {
    success_log "--- Full Rebuild Initiated ---"

    success_log "Pruning entire Docker system (-a -f)..."
    if ! docker system prune -a -f; then
        warning_log "Warning: Docker system prune failed, but continuing with service restart." >&2
    fi

    success_log "Creating/ensuring network '$NETWORK_NAME' with subnet '$NETWORK_SUBNET'..."
    if ! docker network create --subnet="$NETWORK_SUBNET" "$NETWORK_NAME"; then
        warning_log "Warning: Failed to create/ensure network '$NETWORK_NAME'. Compose will use defaults." >&2
    fi
}

docker_kill() {
    success_log "Killing all running Docker containers..."

    if ! docker kill $(docker ps -q); then
        warning_log "Warning: Failed to kill some or all containers." >&2
    fi

    success_log "All running Docker containers have been killed."
}

docker_up() {
    success_log "Starting Docker Compose services with rebuild and force-recreate..."

    if ! docker compose --env-file ./.env up -d --remove-orphans --build --force-recreate; then
        warning_log "Failed to start services" >&2
        docker_kill
        if ! docker compose --env-file ./.env up  -d --remove-orphans --build --force-recreate; then
            error_log "Retry failed: Could not start services" >&2
            exit 1
        fi
        exit 1
    fi

    success_log "Docker Compose services down and successfully restarted."
}


check_config() {
    if ! docker compose config > /dev/null; then
        error_log "Error In Compose File" >&2
        exit 1
    fi
}

no_down_restart() {
    success_log "Stoping & Re-Starting Never Down, Always Up Routine..."
    success_log "$(date): Stoping service management routine."
    if ! docker compose --file never-down.yml --env-file ./.env down; then
        error_log "Failed Stopping Never Down Services" >&2
        exit 1
    fi
    success_log "Stopped All Never Down Services Successfully."
    success_log "$(date): Starting service management routine."
    if ! docker compose --file never-down.yml --env-file ./.env up  -d --remove-orphans --build --force-recreate; then
        error_log "Failed Starting Never Down Services" >&2
        exit 1
    fi
    success_log "Started All Never Down Services Successfully."
}



main() {
    success_log "$(date): Starting service management routine."
    setup_environment
    if [ "$1" == "--never-down-restart" ]; then
        no_down_restart
        exit 0
    fi
    check_config
    docker_down
    sleep 5
    if [ "$1" == "--all" ]; then
        prune_and_network_setup
        no_down_restart
    fi
    docker_up
}


main "$@"
