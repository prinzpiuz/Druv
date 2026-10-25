#!/bin/bash

RED='\033[0;31m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
NC='\033[0m'
COMPOSE_DIR=/home/druv/druv_setup
NETWORK_NAME=${NETWORK_NAME}
NETWORK_SUBNET=${NETWORK_SUBNET}
# Set by start_vpn / docker_up; main exits non-zero if either stayed unhappy.
VPN_HEALTHY=1
STACK_FAILED=0

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
    if [ ! -f "$COMPOSE_DIR/version.env" ]; then
        error_log "Error: version.env not found in $COMPOSE_DIR (holds pinned image tags)" >&2
        exit 1
    fi
    # Compose reads .env automatically but not version.env; this covers both for
    # every compose call below. Do not add --env-file, it overrides this.
    export COMPOSE_ENV_FILES=".env,version.env"
    success_log "Image versions loaded from version.env."
    if [ -x "./logo.sh" ]; then
        ./logo.sh
    else
        warning_log "Warning: logo.sh not found or not executable."
    fi

}

docker_down() {
    success_log "Stopping Docker Compose services..."

    if ! docker compose --file docker-compose.yml down --remove-orphans; then
        error_log "Failed to stop services" >&2
        docker_kill
        if ! docker compose down --remove-orphans; then
            error_log "Retry failed: Could not stop services" >&2
            exit 1
        fi
    fi

    success_log "Services stopped successfully."
}

network_setup() {
    success_log "--- Full Rebuild Initiated ---"

    if docker network inspect "$NETWORK_NAME" > /dev/null 2>&1; then
        success_log "Network '$NETWORK_NAME' already exists."
        return 0
    fi
    success_log "Creating network '$NETWORK_NAME' with subnet '$NETWORK_SUBNET'..."
    if ! docker network create --subnet="$NETWORK_SUBNET" "$NETWORK_NAME"; then
        warning_log "Warning: Failed to create network '$NETWORK_NAME'. Compose will use defaults." >&2
    fi
}

# Runs after every stack is up, so only images no container uses (old versions
# after a bump) are removed. Pruning before `up` deleted all ~23 GB of images,
# because docker_down had removed every container, and forced a full re-pull.
prune_unused_images() {
    if [ "$VPN_HEALTHY" -eq 0 ] || [ "$STACK_FAILED" -eq 1 ]; then
        warning_log "Skipping image prune: a service that failed to start may have no container, and its image would be deleted." >&2
        return 0
    fi
    success_log "Removing images not used by any container..."
    if ! docker image prune -a -f; then
        warning_log "Warning: Docker image prune failed." >&2
    fi
}

docker_kill() {
    success_log "Killing all running Docker containers..."

    if ! docker kill $(docker ps -q); then
        warning_log "Warning: Failed to kill some or all containers." >&2
    fi

    success_log "All running Docker containers have been killed."
}

report_failed_services() {
    local failed
    failed=$(docker compose ps -a --format '{{.Service}}\t{{.State}}\t{{.Status}}' \
        | grep -v $'\trunning\t')

    if [ -n "$failed" ]; then
        warning_log "Services not running:" >&2
        echo "$failed" >&2
    fi
}

start_vpn() {
    # Eight services depend on gluetun, three of them through its network
    # namespace. Start it alone and wait, so a slow tunnel does not abort the
    # whole stack, and its own log lands here instead of a bare
    # "dependency failed to start". A dead VPN must not block the rest of the
    # homelab, so this only warns; the eight dependents stay down on their own.
    success_log "Starting gluetun and waiting for a healthy tunnel..."

    if ! docker compose up -d --wait --wait-timeout 180 gluetun; then
        VPN_HEALTHY=0
        error_log "gluetun did not become healthy within 180s." >&2
        error_log "Its dependents will stay down. Last 50 log lines:" >&2
        docker logs --tail 50 gluetun >&2
        return 0
    fi

    VPN_HEALTHY=1
    success_log "gluetun is healthy."
}

docker_up() {
    success_log "Starting Docker Compose services with rebuild..."

    # No --force-recreate here: docker_down already removed every container, and
    # forcing it would recreate the gluetun container start_vpn just waited for.
    if ! docker compose up -d --remove-orphans --build; then
        warning_log "Some services failed to start, retrying once..." >&2
        # Deliberately no docker_kill here: one unhealthy dependency used to
        # take down every container on the host, including unrelated stacks.
        if ! docker compose up -d --remove-orphans --build; then
            error_log "Retry failed: some services are still not running" >&2
            report_failed_services
            STACK_FAILED=1
            return 0
        fi
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
    if ! docker compose --file never-down.yml down; then
        error_log "Failed Stopping Never Down Services" >&2
        exit 1
    fi
    success_log "Stopped All Never Down Services Successfully."
    success_log "$(date): Starting service management routine."
    if ! docker compose --file never-down.yml up  -d --remove-orphans --build --force-recreate; then
        error_log "Failed Starting Never Down Services" >&2
        exit 1
    fi
    success_log "Started All Never Down Services Successfully."
}

help() {
    echo "Usage: $0 [--all | --never-down-restart]"
    echo ""
    echo "Options:"
    echo "  --all                    Create the network if missing, then remove unused images once all services are up."
    echo "  --never-down-restart     Restart only the services defined in never-down.yml without taking down other services."
    exit 1
}

main() {
    setup_environment
    if [ "$1" == "--help" ]; then
        help
    fi
    success_log "$(date): Starting service management routine."
    if [ "$1" == "--never-down-restart" ]; then
        no_down_restart
        exit 0
    fi
    check_config
    docker_down
    sleep 5
    if [ "$1" == "--all" ]; then
        network_setup
    fi
    start_vpn
    docker_up
    # Runs even when the VPN or a service failed, so the never-down stack and
    # everything unrelated to gluetun still comes back up.
    no_down_restart
    if [ "$1" == "--all" ]; then
        prune_unused_images
    fi

    if [ "$VPN_HEALTHY" -eq 0 ]; then
        error_log "Finished with gluetun unhealthy: its eight dependents are down." >&2
        exit 1
    fi
    if [ "$STACK_FAILED" -eq 1 ]; then
        error_log "Finished with one or more services not running." >&2
        exit 1
    fi
    success_log "All stacks are up."
}


main "$@"
