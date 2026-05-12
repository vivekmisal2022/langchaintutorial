# SAP BTP Kyma Deployment

This folder contains Kubernetes manifests for deploying the Super Agent application on SAP BTP Kyma.

## Architecture

```
                    ┌─────────────────────┐
                    │     API Gateway     │
                    │   (Kyma APIRule)    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │    SAP App Router   │
                    │   (XSUAA Auth)      │
                    │      :5000          │
                    └──────────┬──────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│    Frontend     │  │    Backend      │  │   Backend-MCP   │
│   (React/Vite)  │  │   (FastAPI)     │  │   (Node.js)     │
│      :80        │  │     :8000       │  │     :3001       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Prerequisites

- SAP BTP Kyma environment
- kubectl configured for your Kyma cluster
- Docker images built and pushed to a container registry
- SAP BTP Service Manager with XSUAA entitlements

## Quick Start

### 1. Build and Push Docker Images

```bash
# From the project root
docker build -t your-registry/super-agent-frontend:latest ./frontend
docker build -t your-registry/super-agent-backend:latest ./backend
docker build -t your-registry/super-agent-backend-mcp:latest ./backend-mcp

# Push to your registry
docker push your-registry/super-agent-frontend:latest
docker push your-registry/super-agent-backend:latest
docker push your-registry/super-agent-backend-mcp:latest
```

### 2. Update Image References

Edit `deployment.yaml` and replace `YOUR_REGISTRY` with your actual container registry:

```yaml
image: docker.io/YOUR_REGISTRY/super-agent-frontend:latest
image: docker.io/YOUR_REGISTRY/super-agent-backend:latest
image: docker.io/YOUR_REGISTRY/super-agent-backend-mcp:latest
```

### 3. Configure Secrets

Update the secrets in `deployment.yaml` with your base64-encoded values:

```bash
# Generate base64 values
echo -n 'your-client-id' | base64
echo -n 'your-client-secret' | base64
echo -n '{"clientid":"...","clientsecret":"..."}' | base64  # For AICORE_SERVICE_KEY
```

### 4. Update APIRule Host

Edit the APIRule to match your Kyma cluster domain:

```yaml
spec:
  host: super-agent  # Will become super-agent.<cluster-domain>
```

### 5. Deploy

```bash
kubectl apply -f deployment.yaml
```

### 6. Verify Deployment

```bash
# Check all resources
kubectl get all -n super-agent

# Watch pod status
kubectl get pods -n super-agent -w

# Check XSUAA service instance
kubectl get serviceinstances -n super-agent

# Check service binding
kubectl get servicebindings -n super-agent
```

## Resources Created

| Resource | Name | Description |
|----------|------|-------------|
| Namespace | super-agent | Isolated namespace with Istio injection |
| ServiceAccount | super-agent-xsuaa-sa | Service account for XSUAA |
| ServiceInstance | super-agent-xsuaa-instance | XSUAA service instance |
| ServiceBinding | super-agent-xsuaa-binding | XSUAA binding with secrets |
| ConfigMap | super-agent-config | Shared configuration |
| ConfigMap | approuter-destinations-configmap | App Router destinations |
| ConfigMap | approuter-xs-app-configmap | App Router routes (xs-app.json) |
| Secret | super-agent-secrets | SAP credentials |
| Deployment | approuter-deployment | SAP App Router |
| Deployment | frontend-deployment | React frontend |
| Deployment | backend-deployment | Python FastAPI backend |
| Deployment | backend-mcp-deployment | Node.js MCP server |
| Service | approuter-service | App Router service |
| Service | frontend-service | Frontend service |
| Service | backend-service | Backend service |
| Service | backend-mcp-service | MCP server service |
| DestinationRule | approuter-destrule | Session stickiness |
| VirtualService | *-virtualservice | Istio timeout configs |
| APIRule | super-agent-apirule | External access |

## Routing Configuration

The SAP App Router handles all routing via `xs-app.json`:

| Route | Destination | Target Service |
|-------|-------------|----------------|
| `/api/documents/*` | backend-mcp-app | Backend-MCP (document management) |
| `/api/*` | backend-app | Backend (chat, sessions, audio) |
| `/health` | backend-app | Health check (no auth) |
| `/*` | frontend-app | Frontend (static files) |

## Authentication

- All routes use XSUAA authentication except `/health`
- User info is forwarded via `forwardAuthToken: true`
- Session timeout: 480 minutes (8 hours)

## Configuration

### Environment Variables

Configuration is managed through:
- **ConfigMap `super-agent-config`**: Non-sensitive shared values
- **Secret `super-agent-secrets`**: Sensitive credentials (SAP AI Core, HANA, OData)

### Service Mode

Control service behavior via ConfigMap:
```yaml
MOCK_MODE: "false"      # Use real LLM service
AGENTIC_MODE: "true"    # Enable DeepAgent with MCP tools
```

## Troubleshooting

### Check pod logs
```bash
kubectl logs -f deployment/approuter-deployment -n super-agent
kubectl logs -f deployment/backend-deployment -n super-agent
kubectl logs -f deployment/backend-mcp-deployment -n super-agent
kubectl logs -f deployment/frontend-deployment -n super-agent
```

### Check pod status
```bash
kubectl describe pod -l app=backend-app -n super-agent
```

### Check XSUAA binding
```bash
kubectl get secret super-agent-xsuaa-binding-secret -n super-agent -o yaml
```

### Port forwarding for debugging
```bash
# Access approuter directly
kubectl port-forward svc/approuter-service 5000:5000 -n super-agent

# Access backend directly (bypass auth)
kubectl port-forward svc/backend-service 8000:8000 -n super-agent
```

### Common Issues

**XSUAA Service Instance not created:**
- Ensure SAP BTP Service Operator is installed in your Kyma cluster
- Check service instance status: `kubectl describe serviceinstance -n super-agent`

**SSE Streaming timeout:**
- VirtualServices configure 180-300s timeouts for long-running requests
- Check Istio sidecar logs if requests are being terminated

**Image pull errors:**
- Ensure images are pushed to the registry
- Check imagePullSecrets if using a private registry

### Delete and redeploy
```bash
kubectl delete -f deployment.yaml
kubectl apply -f deployment.yaml
```

## Scaling

Adjust replicas in each deployment as needed:

```bash
kubectl scale deployment backend-deployment --replicas=2 -n super-agent
```

## Security Notes

1. **Secrets**: Never commit actual secrets to version control. Use `kubectl create secret` or sealed-secrets.

2. **XSUAA**: The XSUAA instance is configured with a single `User` role. Assign this role to users in SAP BTP Cockpit.

3. **Network**: Istio sidecar injection is enabled for mTLS between services.

4. **CORS**: Backend CORS is configured to accept requests from internal services only.
