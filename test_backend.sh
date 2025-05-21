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
PROJECT_ROOT="$SCRIPT_DIR"
BACKEND_DIR="$PROJECT_ROOT/backend"
CONDA_ENV_NAME="token-portal-backend"

echo -e "${COLOR_BLUE}--- Token Portal Backend Test Script ---${COLOR_RESET}"
echo -e "${COLOR_CYAN}Project Root:${COLOR_RESET} $PROJECT_ROOT"
echo -e "${COLOR_CYAN}Backend Directory:${COLOR_RESET} $BACKEND_DIR"
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
            # Optionally exit if Conda activation is critical
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

# Navigate to backend directory
echo ""
echo -e "${COLOR_CYAN}[Tests] Navigating to backend directory: $BACKEND_DIR${COLOR_RESET}"
cd "$BACKEND_DIR" || { echo -e "${COLOR_RED}[Tests] ERROR: Could not navigate to backend directory '$BACKEND_DIR'.${COLOR_RESET}"; exit 1; }

# Run Pytest
echo ""
echo -e "${COLOR_BLUE}[Tests] Running Pytest with PYTHONPATH set...${COLOR_RESET}"
echo -e "${COLOR_CYAN}[Tests] Command: PYTHONPATH=. pytest -v${COLOR_RESET}"
PYTHONPATH=. pytest -v

TEST_EXIT_CODE=$?

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${COLOR_GREEN}[Tests] All tests passed!${COLOR_RESET}"
else
    echo -e "${COLOR_RED}[Tests] Some tests failed. Exit code: $TEST_EXIT_CODE${COLOR_RESET}"
fi

echo -e "${COLOR_BLUE}-------------------------------------------${COLOR_RESET}"
exit $TEST_EXIT_CODE 