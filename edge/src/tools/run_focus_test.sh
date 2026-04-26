#!/bin/bash
# Wrapper script for focus testing that sets up environment correctly
# Optimized for IMX708 Camera Module 3 LPR use case

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT" || exit 1

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Create results directory with proper permissions
RESULTS_DIR="$PROJECT_ROOT/edge/tests/results"
mkdir -p "$RESULTS_DIR"
# Ensure directory is writable by current user
chmod 755 "$RESULTS_DIR" 2>/dev/null || true

# Activate virtual environment if it exists
if [ -f "$PROJECT_ROOT/edge/installation/venv_hailo/bin/activate" ]; then
    source "$PROJECT_ROOT/edge/installation/venv_hailo/bin/activate"
elif [ -f "$PROJECT_ROOT/edge/venv_simulation/bin/activate" ]; then
    source "$PROJECT_ROOT/edge/venv_simulation/bin/activate"
fi

# Check if running with sudo (for service control)
if [ "$EUID" -eq 0 ]; then
    echo "Warning: Running as root. Results will be saved in project directory."
fi

# Inject default health-check tuning unless user overrides
EXTRA_ARGS=()
if [[ "$*" != *"--skip-health-check"* && "$*" != *"--health-check-duration"* ]]; then
    EXTRA_ARGS+=(--health-check-duration 4.0)
fi

# Run the test script with all arguments
python "$SCRIPT_DIR/test_focus_modes.py" "${EXTRA_ARGS[@]}" "$@"

