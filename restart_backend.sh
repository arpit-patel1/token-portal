#!/bin/bash

# --- Colors ---
COLOR_RESET='\033[0m'
COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[0;33m'
COLOR_BLUE='\033[0;34m'
COLOR_CYAN='\033[0;36m'

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PROJECT_ROOT="$SCRIPT_DIR" # Assumes script is in project root
BACKEND_DIR="$PROJECT_ROOT/backend"
# Correctly referencing the docker-compose file name
DOCKER_COMPOSE_BASENAME="docker-compose-db.yml"
DOCKER_COMPOSE_FILE_PATH="$BACKEND_DIR/$DOCKER_COMPOSE_BASENAME"
PG_CONTAINER_NAME="token_portal_postgres_db"
BACKEND_HOST="0.0.0.0"
BACKEND_PORT="9971" # Port for the FastAPI backend
CONDA_ENV_NAME="token-portal-backend"

echo -e "${COLOR_BLUE}--- Token Portal Backend Restart Script ---${COLOR_RESET}"
echo -e "${COLOR_CYAN}Project Root:${COLOR_RESET} $PROJECT_ROOT"
echo -e "${COLOR_CYAN}Backend Directory:${COLOR_RESET} $BACKEND_DIR"
echo -e "${COLOR_CYAN}Docker Compose File:${COLOR_RESET} $DOCKER_COMPOSE_FILE_PATH"
echo -e "${COLOR_CYAN}PostgreSQL Container Name:${COLOR_RESET} $PG_CONTAINER_NAME"
echo -e "${COLOR_CYAN}FastAPI Backend Port:${COLOR_RESET} $BACKEND_PORT"
echo -e "${COLOR_CYAN}Target Conda Env:${COLOR_RESET} $CONDA_ENV_NAME"
echo -e "${COLOR_BLUE}-------------------------------------------${COLOR_RESET}"

# --- Conda Activation ---
echo ""
echo -e "${COLOR_BLUE}[Conda] Attempting to activate Conda environment: '$CONDA_ENV_NAME'...${COLOR_RESET}"
if command -v conda &>/dev/null; then
    CONDA_BASE_PATH=$(conda info --base)
    echo -e "${COLOR_CYAN}[Conda] Found Conda base at: $CONDA_BASE_PATH${COLOR_RESET}"
    CONDA_SH_PATH="$CONDA_BASE_PATH/etc/profile.d/conda.sh"

    if [ -f "$CONDA_SH_PATH" ]; then
        echo -e "${COLOR_CYAN}[Conda] Sourcing Conda script: $CONDA_SH_PATH${COLOR_RESET}"
        # shellcheck source=/dev/null
        source "$CONDA_SH_PATH"
        
        echo -e "${COLOR_CYAN}[Conda] Activating environment: $CONDA_ENV_NAME...${COLOR_RESET}"
        conda activate "$CONDA_ENV_NAME"
        
        CURRENT_CONDA_ENV_NAME=$(basename "$CONDA_PREFIX")
        if [ "$CURRENT_CONDA_ENV_NAME" = "$CONDA_ENV_NAME" ]; then
            echo -e "${COLOR_GREEN}[Conda] Successfully activated environment: '$CONDA_ENV_NAME'.${COLOR_RESET}"
            echo -e "${COLOR_CYAN}[Conda] Python executable: $(which python)${COLOR_RESET}"
        else
            echo -e "${COLOR_RED}[Conda] ERROR: Failed to activate environment '$CONDA_ENV_NAME'.${COLOR_RESET}"
            echo -e "${COLOR_YELLOW}[Conda] Current environment is: '$CURRENT_CONDA_ENV_NAME'. Please ensure '$CONDA_ENV_NAME' exists and try activating it manually before running this script.${COLOR_RESET}"
            # We might choose to exit here if Conda activation is critical
            # exit 1 
        fi
    else
        echo -e "${COLOR_RED}[Conda] ERROR: Conda script '$CONDA_SH_PATH' not found. Cannot activate environment automatically.${COLOR_RESET}"
        echo -e "${COLOR_YELLOW}[Conda] Please ensure your Conda environment '$CONDA_ENV_NAME' is active manually.${COLOR_RESET}"
    fi
else
    echo -e "${COLOR_RED}[Conda] ERROR: 'conda' command not found. Cannot activate environment automatically.${COLOR_RESET}"
    echo -e "${COLOR_YELLOW}[Conda] Please ensure your Conda environment '$CONDA_ENV_NAME' is active manually or Conda is in your PATH.${COLOR_RESET}"
fi
# --- End Conda Activation ---

# 1. Ensure PostgreSQL Docker container is running
echo ""
echo -e "${COLOR_BLUE}[DB] Checking PostgreSQL container '$PG_CONTAINER_NAME' status...${COLOR_RESET}"
if ! docker ps --filter "name=$PG_CONTAINER_NAME" --filter "status=running" --format "{{.Names}}" | grep -q "$PG_CONTAINER_NAME"; then
    echo -e "${COLOR_YELLOW}[DB] Container '$PG_CONTAINER_NAME' is not running. Attempting to start it...${COLOR_RESET}"
    if [ -f "$DOCKER_COMPOSE_FILE_PATH" ]; then
        # Run docker-compose from the BACKEND_DIR context
        echo -e "${COLOR_CYAN}[DB] Executing: (cd \"$BACKEND_DIR\" && docker-compose -f \"$DOCKER_COMPOSE_BASENAME\" up -d)${COLOR_RESET}"
        (cd "$BACKEND_DIR" && docker-compose -f "$DOCKER_COMPOSE_BASENAME" up -d)
        if [ $? -eq 0 ]; then
            echo -e "${COLOR_GREEN}[DB] Docker compose 'up -d' command successful.${COLOR_RESET}"
            echo -e "${COLOR_YELLOW}[DB] Waiting a few seconds for PostgreSQL to initialize...${COLOR_RESET}"
            sleep 10 # Give DB time to start
        else
            echo -e "${COLOR_RED}[DB] ERROR: Docker compose 'up -d' command failed.${COLOR_RESET}"
            # exit 1 # Commenting out exit so script can try to start backend anyway if DB was already running from elsewhere
        fi
    else
        echo -e "${COLOR_RED}[DB] ERROR: Docker compose file '$DOCKER_COMPOSE_FILE_PATH' not found. Cannot start database.${COLOR_RESET}"
        # exit 1
    fi
else
    echo -e "${COLOR_GREEN}[DB] Container '$PG_CONTAINER_NAME' is already running.${COLOR_RESET}"
fi

# 2. Ensure backend port is free
echo ""
echo -e "${COLOR_BLUE}[Backend] Checking if port $BACKEND_PORT for FastAPI is in use...${COLOR_RESET}"
# Using lsof for macOS (darwin). For other OS, this command might differ.
PID_ON_PORT=$(lsof -t -iTCP:"$BACKEND_PORT" -sTCP:LISTEN)

if [ -n "$PID_ON_PORT" ]; then
    echo -e "${COLOR_YELLOW}[Backend] Port $BACKEND_PORT is occupied by PID $PID_ON_PORT. Attempting to kill...${COLOR_RESET}"
    kill -9 "$PID_ON_PORT"
    if [ $? -eq 0 ]; then
        echo -e "${COLOR_GREEN}[Backend] Successfully killed process $PID_ON_PORT.${COLOR_RESET}"
        sleep 2 # Give a moment for the port to be fully released
    else
        echo -e "${COLOR_RED}[Backend] WARNING: Failed to kill process $PID_ON_PORT. Port $BACKEND_PORT might still be in use.${COLOR_RESET}"
    fi
else
    echo -e "${COLOR_GREEN}[Backend] Port $BACKEND_PORT for FastAPI is free.${COLOR_RESET}"
fi

# 3. Start the FastAPI backend server
echo ""
echo -e "${COLOR_CYAN}[Backend] Navigating to backend directory: $BACKEND_DIR${COLOR_RESET}"
cd "$BACKEND_DIR" || { echo -e "${COLOR_RED}[Backend] ERROR: Could not navigate to backend directory '$BACKEND_DIR'.${COLOR_RESET}"; exit 1; }

echo ""
echo -e "${COLOR_BLUE}[Backend] Launching Uvicorn: uvicorn app.main:app --host $BACKEND_HOST --port $BACKEND_PORT --reload${COLOR_RESET}"

uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload

echo ""
echo -e "${COLOR_BLUE}[Backend] Uvicorn server process has been started by the script.${COLOR_RESET}"
echo -e "${COLOR_CYAN}          If it launched successfully, access it at http://$BACKEND_HOST:$BACKEND_PORT${COLOR_RESET}"
echo -e "${COLOR_CYAN}          (or http://localhost:$BACKEND_PORT from your browser).${COLOR_RESET}"
echo -e "${COLOR_CYAN}          Press Ctrl+C in this terminal to stop Uvicorn and the script.${COLOR_RESET}"
echo -e "${COLOR_BLUE}-------------------------------------------${COLOR_RESET}" 