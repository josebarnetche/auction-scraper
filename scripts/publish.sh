#!/bin/bash
# Publish static site to here.now

set -e

SITE_DIR="${1:-site}"

if [ ! -d "$SITE_DIR" ]; then
    echo "Error: Directory '$SITE_DIR' not found"
    exit 1
fi

echo "Publishing $SITE_DIR to here.now..."

# Check if here CLI is installed
if ! command -v here &> /dev/null; then
    echo "Installing here.now CLI..."
    npm install -g @here/cli 2>/dev/null || {
        echo "Warning: Could not install here CLI globally"
        echo "Trying npx..."
        npx @here/cli publish "$SITE_DIR"
        exit $?
    }
fi

# Publish
here publish "$SITE_DIR"

echo "Done!"
