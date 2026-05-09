#!/bin/bash
# Pre-start script for aicamera_lpr service
# This script ensures database schema is up to date before starting the service

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "🔧 Running pre-start checks for aicamera_lpr..."

# Change to project directory
cd "$PROJECT_ROOT"

# Check if database schema update script exists
if [[ -f "edge/scripts/update_database_schema.py" ]]; then
    echo "📋 Updating database schema..."
    
    # Run database schema update
    if python edge/scripts/update_database_schema.py; then
        echo "✅ Database schema updated successfully"
    else
        echo "❌ Database schema update failed"
        echo "⚠️  Service will start but may have WebSocket logging issues"
    fi
else
    echo "⚠️  Database schema update script not found"
    echo "📋 Expected location: edge/scripts/update_database_schema.py"
fi

# Check if .env.production exists in edge/installation
if [[ ! -f "edge/installation/.env.production" ]]; then
    echo "⚠️  .env.production file not found in edge/installation/"
    echo "📋 Please run the installation script first: ./install.sh"
fi

# Check if required directories exist
for dir in logs db captured_images; do
    if [[ ! -d "$dir" ]]; then
        echo "📁 Creating directory: $dir"
        mkdir -p "$dir"
    fi
done

echo "✅ Pre-start checks completed"
