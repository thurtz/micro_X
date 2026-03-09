#!/bin/bash

# Portability-focused wrapper for micro_X in Docker.
# Supports Host Breakout (chroot) and host-gateway AI connectivity.

# Determine the project root (where the Dockerfile is)
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# Get current branch name for dynamic container and image naming
BRANCH_NAME=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "none")
TIMESTAMP=$(date +%s)
SAFE_BRANCH=$(echo "$BRANCH_NAME" | tr '/' '_')

# Image name is branch-specific to avoid conflicts between clones
IMAGE_NAME="micro_x:${SAFE_BRANCH}"

if [ "$BRANCH_NAME" == "main" ]; then
    CONTAINER_NAME="micro_x_$TIMESTAMP"
    IMAGE_NAME="micro_x:latest"
else
    CONTAINER_NAME="micro_x_${SAFE_BRANCH}_$TIMESTAMP"
fi

# 1. Detect Host TTY Group (for tmux permissions)
TTY_GID=$(stat -c '%g' /dev/tty 2>/dev/null || echo "5")

# 2. Build the image (always runs, Docker uses cache if no changes)
build_image() {
    echo "Checking/Building Docker image: $IMAGE_NAME"
    if grep -q "desktop.exe" ~/.docker/config.json 2>/dev/null; then
        mv ~/.docker/config.json ~/.docker/config.json.bak
        docker build -t "$IMAGE_NAME" "$PROJECT_ROOT"
        mv ~/.docker/config.json.bak ~/.docker/config.json
    else
        docker build -t "$IMAGE_NAME" "$PROJECT_ROOT"
    fi
}

build_image

# 3. Configure AI Connection
OLLAMA_HOST_IP="host.docker.internal"

echo "🚀 Launching micro_X in Debian container (Host Access Mode)..."
echo "📍 Mapping host path: $PROJECT_ROOT"

# 4. Run the container
# We map host root to /host for breakout commands.
# We pass HOST_PROJECT_ROOT so micro_X knows its real path on the host.
docker run -it --rm \
    --name "$CONTAINER_NAME" \
    --privileged \
    --group-add "$TTY_GID" \
    -e TERM="$TERM" \
    --device /dev/tty:/dev/tty \
    -v "$HOME:$HOME" \
    -v "$PROJECT_ROOT:$PROJECT_ROOT" \
    -v "$PROJECT_ROOT/logs:$PROJECT_ROOT/logs" \
    -v "/:/host" \
    -v "/app/.venv" \
    -v ~/.ssh:/root/.ssh:ro \
    -v ~/.gitconfig:/root/.gitconfig:ro \
    -v ~/.config/gh:/root/.config/gh:ro \
    --workdir "$PROJECT_ROOT" \
    -e OLLAMA_HOST="http://$OLLAMA_HOST_IP:11434" \
    -e DOCKER_BREAKOUT="true" \
    -e HOST_PROJECT_ROOT="$PROJECT_ROOT" \
    --add-host=host.docker.internal:host-gateway \
    "$IMAGE_NAME" "$@"
