#!/bin/bash
# Docker entrypoint script for Ship container
# This script runs as root to fix workspace permissions, then starts the application

set -e

# Fix workspace permissions for shipyard user
# This is needed when /workspace is a mounted volume with root ownership
if [ -d /workspace ]; then
    chown -R shipyard:shipyard /workspace 2>/dev/null || true
    chmod 755 /workspace 2>/dev/null || true
fi

# Execute the main command
exec "$@"
