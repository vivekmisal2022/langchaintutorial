#!/bin/bash
#
# Build and push Docker images for the Super Agent application
#
# Usage:
#   ./build_and_push.sh          # Build and push all images
#   ./build_and_push.sh build    # Build only (no push)
#   ./build_and_push.sh push     # Push only (assumes images exist)
#

set -e

# Configuration
REGISTRY="docker.io"
NAMESPACE="gunter04"
VERSION="0.2"

# Image names
BACKEND_IMAGE="${REGISTRY}/${NAMESPACE}/super-agent-backend:${VERSION}"
BACKEND_MCP_IMAGE="${REGISTRY}/${NAMESPACE}/super-agent-backend-mcp:${VERSION}"
FRONTEND_IMAGE="${REGISTRY}/${NAMESPACE}/super-agent-frontend:${VERSION}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

build_images() {
    log_info "Building Docker images with version ${VERSION}..."

    # Build backend
    log_info "Building backend image: ${BACKEND_IMAGE}"
    docker build -t "${BACKEND_IMAGE}" ./backend

    # Build backend-mcp
    log_info "Building backend-mcp image: ${BACKEND_MCP_IMAGE}"
    docker build -t "${BACKEND_MCP_IMAGE}" ./backend-mcp

    # Build frontend
    log_info "Building frontend image: ${FRONTEND_IMAGE}"
    docker build -t "${FRONTEND_IMAGE}" ./frontend

    log_info "All images built successfully!"
}

push_images() {
    log_info "Pushing Docker images to ${REGISTRY}..."

    # Push backend
    log_info "Pushing backend image: ${BACKEND_IMAGE}"
    docker push "${BACKEND_IMAGE}"

    # Push backend-mcp
    log_info "Pushing backend-mcp image: ${BACKEND_MCP_IMAGE}"
    docker push "${BACKEND_MCP_IMAGE}"

    # Push frontend
    log_info "Pushing frontend image: ${FRONTEND_IMAGE}"
    docker push "${FRONTEND_IMAGE}"

    log_info "All images pushed successfully!"
}

show_summary() {
    echo ""
    log_info "Image Summary:"
    echo "  Backend:     ${BACKEND_IMAGE}"
    echo "  Backend-MCP: ${BACKEND_MCP_IMAGE}"
    echo "  Frontend:    ${FRONTEND_IMAGE}"
    echo ""
}

# Main script
case "${1:-all}" in
    build)
        build_images
        show_summary
        ;;
    push)
        push_images
        show_summary
        ;;
    all)
        build_images
        push_images
        show_summary
        ;;
    *)
        echo "Usage: $0 [build|push|all]"
        echo ""
        echo "Commands:"
        echo "  build  - Build all Docker images"
        echo "  push   - Push all Docker images to registry"
        echo "  all    - Build and push all images (default)"
        exit 1
        ;;
esac
