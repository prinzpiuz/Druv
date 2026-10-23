#!/bin/bash
# Renders every compose project without touching a server: the root project
# (with its includes), never-down.yml and public/. Run by pre-commit and CI.
#
# .env files are gitignored, so a fresh clone (or CI) has none, and every
# `env_file: .env` would fail. A missing .env is filled from its .env.sample.
# Existing .env files are never overwritten.
set -euo pipefail

RED='\033[0;31m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
NC='\033[0m'

error_log() {
    echo -e "${RED}$1${NC}"
}

warning_log() {
    echo -e "${CYAN}$1${NC}"
}

success_log() {
    echo -e "${GREEN}$1${NC}"
}

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

fill_missing_env_files() {
    local sample env_file
    while IFS= read -r sample; do
        env_file="${sample%.sample}"
        if [ ! -f "$env_file" ]; then
            cp "$sample" "$env_file"
            warning_log "Created $env_file from $sample (placeholder values)."
        fi
    done < <(git ls-files '.env.sample' '*/.env.sample')
}

# $1: label, $2: project directory, remaining: extra compose args.
validate_project() {
    local label=$1 dir=$2
    shift 2
    # COMPOSE_ENV_FILES paths resolve against the working directory, so each
    # project is rendered from its own directory, as down_and_up.sh and the
    # deploy workflow do.
    if (cd "$dir" && COMPOSE_ENV_FILES=.env,version.env docker compose "$@" config --quiet); then
        success_log "OK: $label"
    else
        error_log "FAILED: $label (docker compose $* config, in $dir)"
        FAILED=1
    fi
}

FAILED=0
fill_missing_env_files
validate_project "root project (docker-compose.yml + includes)" . --file docker-compose.yml
validate_project "never-down.yml" . --file never-down.yml
validate_project "public/ (VPS)" public --file docker-compose.yml

if [ "$FAILED" -ne 0 ]; then
    error_log "One or more compose projects failed to render."
    exit 1
fi
success_log "All compose projects render."
