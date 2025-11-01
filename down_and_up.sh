#!/bin/bash

echo "$(date)"

COMPOSE_DIR="/home/druv/druv_setup"

cd "$COMPOSE_DIR" || { echo "Error: Could not change to directory $COMPOSE_DIR"; exit 1; }

echo "Stopping Docker Compose services..."

docker compose down

sleep 5

echo "Starting Docker Compose services..."

if [ "$1" == "--all" ]; then
    echo "Rebuilding all services..."
    docker system prune -a -f
    docker network create --subnet=172.18.0.0/24 homelab
fi


docker compose up -d --remove-orphans --build --force-recreate

echo "Docker Compose services down and restarted."
