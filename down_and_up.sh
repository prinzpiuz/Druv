#!/bin/bash

echo "$(date)"

COMPOSE_DIR="/home/druv/druv_setup"

cd "$COMPOSE_DIR" || { echo "Error: Could not change to directory $COMPOSE_DIR"; exit 1; }

echo "Stopping Docker Compose services..."

docker compose down

sleep 5

echo "Starting Docker Compose services..."

docker network create --subnet=172.18.0.0/24 arr

docker-compose --env-file=.env up -d --remove-orphans --build --force-recreate

echo "Docker Compose services down and restarted."
