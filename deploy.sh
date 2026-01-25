#!/bin/bash
# Kubernetes Deployment Script for Algo Trading Bot
# Usage: ./deploy.sh [environment] [action]
# Examples:
#   ./deploy.sh dev apply
#   ./deploy.sh prod delete
#   ./deploy.sh staging status

set -e

ENVIRONMENT=${1:-dev}
ACTION=${2:-apply}
NAMESPACE="algo-trading"
REGISTRY="docker.io"  # Change to your registry
IMAGE_NAME="algo-trading-bot"
IMAGE_TAG="${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S)"

echo "========================================="
echo "Algo Trading Bot Kubernetes Deployment"
echo "========================================="
echo "Environment: $ENVIRONMENT"
echo "Action: $ACTION"
echo "Namespace: $NAMESPACE"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"
    
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl not found. Please install kubectl.${NC}"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ docker not found. Please install docker.${NC}"
        exit 1
    fi
    
    # Check cluster access
    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}❌ Cannot connect to Kubernetes cluster. Run: kubectl config use-context <context>${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Prerequisites OK${NC}"
}

# Build Docker image
build_image() {
    echo ""
    echo -e "${YELLOW}Building Docker image: $REGISTRY/$IMAGE_NAME:$IMAGE_TAG${NC}"
    
    docker build -t "$REGISTRY/$IMAGE_NAME:$IMAGE_TAG" \
                 -t "$REGISTRY/$IMAGE_NAME:$ENVIRONMENT-latest" \
                 --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
                 --build-arg VCS_REF="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
                 .
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Image built successfully${NC}"
    else
        echo -e "${RED}❌ Image build failed${NC}"
        exit 1
    fi
}

# Push Docker image
push_image() {
    echo ""
    echo -e "${YELLOW}Pushing image to registry...${NC}"
    
    docker push "$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    docker push "$REGISTRY/$IMAGE_NAME:$ENVIRONMENT-latest"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Image pushed successfully${NC}"
    else
        echo -e "${RED}❌ Image push failed${NC}"
        exit 1
    fi
}

# Create namespace
create_namespace() {
    echo ""
    echo -e "${YELLOW}Creating namespace: $NAMESPACE${NC}"
    
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    
    echo -e "${GREEN}✓ Namespace ready${NC}"
}

# Apply environment-specific configurations
apply_configs() {
    echo ""
    echo -e "${YELLOW}Applying $ENVIRONMENT configurations...${NC}"
    
    # Update image references in manifest
    sed "s|algo-trading-bot:latest|$REGISTRY/$IMAGE_NAME:$IMAGE_TAG|g" k8s-deployment.yaml > k8s-deployment-$ENVIRONMENT.yaml
    
    # Apply with environment-specific overrides
    case $ENVIRONMENT in
        dev)
            kubectl set env deployment/algo-trading-bot \
                    ENVIRONMENT=development \
                    LOG_LEVEL=DEBUG \
                    --namespace="$NAMESPACE"
            ;;
        staging)
            kubectl set env deployment/algo-trading-bot \
                    ENVIRONMENT=staging \
                    LOG_LEVEL=INFO \
                    --namespace="$NAMESPACE"
            ;;
        prod)
            kubectl set env deployment/algo-trading-bot \
                    ENVIRONMENT=production \
                    LOG_LEVEL=WARN \
                    --namespace="$NAMESPACE"
            # Enable pod disruption budget
            kubectl patch pdb algo-trading-bot-pdb \
                    --namespace="$NAMESPACE" \
                    -p '{"spec":{"minAvailable":2}}'
            ;;
    esac
}

# Deploy manifests
deploy() {
    echo ""
    echo -e "${YELLOW}Deploying to Kubernetes...${NC}"
    
    kubectl apply -f k8s-deployment.yaml --namespace="$NAMESPACE"
    
    echo -e "${GREEN}✓ Resources deployed${NC}"
}

# Roll out deployment
rollout() {
    echo ""
    echo -e "${YELLOW}Rolling out deployment...${NC}"
    
    kubectl set image deployment/algo-trading-bot \
            algo-trading-bot="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG" \
            --namespace="$NAMESPACE" \
            --record
    
    # Wait for rollout to complete
    kubectl rollout status deployment/algo-trading-bot \
            --namespace="$NAMESPACE" \
            --timeout=5m
    
    echo -e "${GREEN}✓ Rollout completed${NC}"
}

# Check deployment status
check_status() {
    echo ""
    echo -e "${YELLOW}Deployment Status:${NC}"
    
    kubectl get deployments -n "$NAMESPACE" -o wide
    
    echo ""
    echo -e "${YELLOW}Pod Status:${NC}"
    kubectl get pods -n "$NAMESPACE" -o wide
    
    echo ""
    echo -e "${YELLOW}Services:${NC}"
    kubectl get services -n "$NAMESPACE" -o wide
    
    echo ""
    echo -e "${YELLOW}StatefulSets (Redis, PostgreSQL):${NC}"
    kubectl get statefulsets -n "$NAMESPACE" -o wide
    
    echo ""
    echo -e "${YELLOW}Recent Events:${NC}"
    kubectl get events -n "$NAMESPACE" --sort-by='.lastTimestamp' | tail -10
}

# View logs
view_logs() {
    echo ""
    echo -e "${YELLOW}Latest logs from algo-trading-bot:${NC}"
    
    # Get the most recent pod
    POD=$(kubectl get pods -n "$NAMESPACE" -l app=algo-trading-bot -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$POD" ]; then
        echo -e "${RED}❌ No pods found${NC}"
        return
    fi
    
    kubectl logs -f "$POD" -n "$NAMESPACE" --tail=100
}

# Port forward for local access
port_forward() {
    echo ""
    echo -e "${YELLOW}Port forwarding to local machine...${NC}"
    echo -e "${YELLOW}API: http://localhost:8000${NC}"
    echo -e "${YELLOW}WebSocket: ws://localhost:8001${NC}"
    echo -e "${YELLOW}Metrics: http://localhost:9090${NC}"
    
    kubectl port-forward -n "$NAMESPACE" \
            svc/algo-trading-bot-api 8000:8000 8001:8001 &
    
    kubectl port-forward -n "$NAMESPACE" \
            svc/algo-trading-bot-metrics 9090:9090 &
    
    echo -e "${GREEN}✓ Port forwarding active (Press Ctrl+C to stop)${NC}"
    wait
}

# Delete deployment
delete() {
    echo ""
    echo -e "${RED}⚠️  Deleting all resources from namespace: $NAMESPACE${NC}"
    read -p "Are you sure? (yes/no): " -r
    
    if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        kubectl delete namespace "$NAMESPACE"
        echo -e "${GREEN}✓ Namespace deleted${NC}"
    else
        echo "Deletion cancelled"
    fi
}

# Main execution
main() {
    case $ACTION in
        build)
            check_prerequisites
            build_image
            ;;
        push)
            check_prerequisites
            build_image
            push_image
            ;;
        deploy)
            check_prerequisites
            create_namespace
            deploy
            apply_configs
            rollout
            check_status
            ;;
        apply)
            check_prerequisites
            create_namespace
            deploy
            ;;
        rollout)
            check_prerequisites
            rollout
            ;;
        status)
            check_prerequisites
            check_status
            ;;
        logs)
            check_prerequisites
            view_logs
            ;;
        port-forward)
            check_prerequisites
            port_forward
            ;;
        delete)
            check_prerequisites
            delete
            ;;
        *)
            echo -e "${YELLOW}Usage: $0 [environment] [action]${NC}"
            echo ""
            echo "Environments: dev, staging, prod"
            echo ""
            echo "Actions:"
            echo "  build         - Build Docker image"
            echo "  push          - Build and push image to registry"
            echo "  deploy        - Full deployment (build -> apply -> rollout)"
            echo "  apply         - Apply manifests to cluster"
            echo "  rollout       - Rollout new deployment"
            echo "  status        - Check deployment status"
            echo "  logs          - View pod logs"
            echo "  port-forward  - Port forward services locally"
            echo "  delete        - Delete namespace and all resources"
            echo ""
            echo "Examples:"
            echo "  $0 dev apply"
            echo "  $0 prod deploy"
            echo "  $0 staging logs"
            exit 1
            ;;
    esac
}

main
