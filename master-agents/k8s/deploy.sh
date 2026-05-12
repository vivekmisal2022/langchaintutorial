#!/bin/bash
# Super Agent - Kyma Deployment Script
# This script deploys to a specific cluster WITHOUT changing the default context

set -e

# Configuration
TARGET_CONTEXT="garden-kyma--a549aaa-external"
NAMESPACE="super-agent"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=============================================="
echo "  Super Agent - Kyma Deployment"
echo "=============================================="
echo ""

# Show context info (but don't change it)
CURRENT_CONTEXT=$(kubectl config current-context 2>/dev/null || echo "")
echo -e "Your default context: ${BLUE}$CURRENT_CONTEXT${NC}"
echo -e "Deployment target:    ${GREEN}$TARGET_CONTEXT${NC}"
echo ""
echo -e "${YELLOW}Note: This script uses --context flag and will NOT change your default context${NC}"
echo ""

# Verify target context exists
if ! kubectl config get-contexts "$TARGET_CONTEXT" &>/dev/null; then
    echo -e "${RED}ERROR: Target context '$TARGET_CONTEXT' not found${NC}"
    echo ""
    echo "Available contexts:"
    kubectl config get-contexts -o name
    exit 1
fi

# Verify cluster connectivity to TARGET context
echo "Verifying connectivity to $TARGET_CONTEXT..."
if ! kubectl --context="$TARGET_CONTEXT" cluster-info &>/dev/null; then
    echo -e "${RED}ERROR: Cannot connect to cluster $TARGET_CONTEXT${NC}"
    echo "Please check your kubeconfig and network connection."
    exit 1
fi
echo -e "${GREEN}✓ Cluster connection OK${NC}"
echo ""

# Parse command line arguments
ACTION="${1:-apply}"

# Helper function to run kubectl with target context
kctl() {
    kubectl --context="$TARGET_CONTEXT" "$@"
}

case "$ACTION" in
    apply|deploy)
        echo "Deploying to namespace: $NAMESPACE (context: $TARGET_CONTEXT)"
        echo ""
        # Apply secret first (if exists)
        if [ -f "$SCRIPT_DIR/secret.yaml" ]; then
            echo "Applying secrets..."
            kctl apply -f "$SCRIPT_DIR/secret.yaml"
        else
            echo -e "${YELLOW}Warning: secret.yaml not found. Copy secret.template.yaml to secret.yaml and fill in values.${NC}"
        fi
        echo ""
        echo "Applying deployment..."
        kctl apply -f "$SCRIPT_DIR/deployment.yaml"
        echo ""
        echo -e "${GREEN}✓ Deployment complete${NC}"
        echo ""
        echo "To check status:"
        echo "  $0 status"
        ;;
    delete|remove|undeploy)
        echo -e "${YELLOW}WARNING: This will delete all resources in namespace $NAMESPACE${NC}"
        echo -e "Target cluster: ${RED}$TARGET_CONTEXT${NC}"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kctl delete -f "$SCRIPT_DIR/deployment.yaml" --ignore-not-found
            if [ -f "$SCRIPT_DIR/secret.yaml" ]; then
                kctl delete -f "$SCRIPT_DIR/secret.yaml" --ignore-not-found
            fi
            echo -e "${GREEN}✓ Resources deleted${NC}"
        else
            echo "Deletion cancelled."
        fi
        ;;
    secret|secrets)
        echo "Applying secrets to namespace: $NAMESPACE"
        if [ -f "$SCRIPT_DIR/secret.yaml" ]; then
            kctl apply -f "$SCRIPT_DIR/secret.yaml"
            echo -e "${GREEN}✓ Secrets applied${NC}"
        else
            echo -e "${RED}ERROR: secret.yaml not found${NC}"
            echo "Copy secret.template.yaml to secret.yaml and fill in values."
            exit 1
        fi
        ;;
    status)
        echo "Checking deployment status in namespace: $NAMESPACE"
        echo ""
        echo "=== Pods ==="
        kctl get pods -n $NAMESPACE 2>/dev/null || echo "Namespace not found or no pods"
        echo ""
        echo "=== Services ==="
        kctl get svc -n $NAMESPACE 2>/dev/null || echo "No services found"
        echo ""
        echo "=== Deployments ==="
        kctl get deployments -n $NAMESPACE 2>/dev/null || echo "No deployments found"
        echo ""
        echo "=== Service Instances (XSUAA) ==="
        kctl get serviceinstances -n $NAMESPACE 2>/dev/null || echo "No service instances found"
        ;;
    logs)
        COMPONENT="${2:-backend}"
        echo "Showing logs for: $COMPONENT (context: $TARGET_CONTEXT)"
        kctl logs -f "deployment/${COMPONENT}-deployment" -n $NAMESPACE
        ;;
    restart)
        COMPONENT="${2:-all}"
        if [ "$COMPONENT" == "all" ]; then
            echo "Restarting all deployments..."
            kctl rollout restart deployment -n $NAMESPACE
        else
            echo "Restarting $COMPONENT..."
            kctl rollout restart "deployment/${COMPONENT}-deployment" -n $NAMESPACE
        fi
        echo -e "${GREEN}✓ Restart triggered${NC}"
        ;;
    describe)
        COMPONENT="${2:-pods}"
        echo "Describing $COMPONENT in namespace: $NAMESPACE"
        kctl describe "$COMPONENT" -n $NAMESPACE
        ;;
    *)
        echo "Usage: $0 {apply|delete|status|logs|restart|describe|secret} [component]"
        echo ""
        echo "Commands:"
        echo "  apply|deploy    Deploy all resources to Kyma (includes secrets)"
        echo "  delete|remove   Delete all resources from Kyma"
        echo "  status          Show deployment status"
        echo "  secret          Apply only the secrets (secret.yaml)"
        echo "  logs [name]     Show logs (default: backend)"
        echo "                  Options: approuter, frontend, backend, backend-mcp"
        echo "  restart [name]  Restart deployment (default: all)"
        echo "  describe [res]  Describe resources (default: pods)"
        echo ""
        echo "Examples:"
        echo "  $0 apply                # Deploy everything"
        echo "  $0 secret               # Apply secrets only"
        echo "  $0 status               # Check status"
        echo "  $0 logs backend         # View backend logs"
        echo "  $0 restart frontend     # Restart frontend only"
        echo "  $0 describe pods        # Describe all pods"
        echo ""
        echo "Target cluster: $TARGET_CONTEXT"
        echo "Note: Your default kubectl context will NOT be changed"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}Your default context is still: $(kubectl config current-context)${NC}"
