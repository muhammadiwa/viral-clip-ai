# Production Deployment Guide

This guide provides step-by-step instructions for deploying Viral Clip AI to production environments.

## Prerequisites

- Docker and Docker Compose
- Kubernetes cluster (1.21+)
- kubectl configured
- Container registry access (GitHub Container Registry recommended)
- Domain name and SSL certificates

## Quick Start

### 1. Environment Setup

```bash
# Copy environment template
cp .env.template .env

# Edit environment variables
nano .env
```

### 2. Docker Compose Deployment (Development/Testing)

```bash
# Start all services
make up

# Check logs
make logs

# Stop services
make down
```

### 3. Kubernetes Production Deployment

```bash
# Build and push images
make build-all
make push-all

# Deploy to Kubernetes
make k8s-deploy

# Check status
make k8s-status
```

## Detailed Configuration

### Environment Variables

Key environment variables that must be configured:

#### Database Configuration
```env
POSTGRES_USER=viralclip
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=viralclip
```

#### Object Storage (MinIO/S3)
```env
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=your_secure_password
S3_BUCKET=viral-clip-ai
```

#### Security
```env
SECRET_KEY=your-super-secret-key-here
WORKER_SERVICE_TOKEN=your-worker-service-token
```

#### External Services
```env
MIDTRANS_SERVER_KEY=your-midtrans-server-key
MIDTRANS_CLIENT_KEY=your-midtrans-client-key
MIDTRANS_IS_PRODUCTION=true
```

### Kubernetes Configuration

#### Required Secrets

Create Kubernetes secrets before deployment:

```bash
# Database credentials
kubectl create secret generic viral-clip-secrets \
  --from-literal=POSTGRES_PASSWORD=your_secure_password \
  --from-literal=MINIO_ROOT_PASSWORD=your_secure_password \
  --from-literal=SECRET_KEY=your-super-secret-key \
  --from-literal=WORKER_SERVICE_TOKEN=your-worker-token \
  --from-literal=MIDTRANS_SERVER_KEY=your-midtrans-key \
  -n viral-clip-ai
```

#### SSL/TLS Configuration

Update ingress configuration in `infra/k8s/ui-deployment.yaml`:

```yaml
spec:
  tls:
    - hosts:
        - yourdomain.com  # Replace with your domain
      secretName: viral-clip-ai-tls
  rules:
    - host: yourdomain.com  # Replace with your domain
```

## Production Checklist

### Security
- [ ] All default passwords changed
- [ ] SSL/TLS certificates configured
- [ ] Network policies applied
- [ ] Secrets properly configured
- [ ] CORS origins restricted

### Monitoring
- [ ] Prometheus metrics enabled
- [ ] Health checks configured
- [ ] Logging aggregation setup
- [ ] Alerting configured

### Scalability
- [ ] Resource limits configured
- [ ] Horizontal Pod Autoscalers deployed
- [ ] Pod Disruption Budgets applied
- [ ] Load balancing configured

### Backup & Recovery
- [ ] Database backup strategy
- [ ] Object storage backup
- [ ] Disaster recovery plan
- [ ] Regular backup testing

### Performance
- [ ] Resource requests optimized
- [ ] Caching configured
- [ ] CDN setup (if needed)
- [ ] Database performance tuned

## Monitoring & Maintenance

### Health Checks

```bash
# Check application health
make monitor-health

# View metrics
make monitor-metrics

# View logs
make monitor-logs
```

### Scaling

```bash
# Scale up for high traffic
make prod-scale

# Manual scaling
kubectl scale deployment/api --replicas=10 -n viral-clip-ai
```

### Updates & Rollbacks

```bash
# Deploy new version
IMAGE_TAG=v1.2.0 make prod-deploy

# Rollback if needed
make prod-rollback
```

### Database Maintenance

```bash
# Backup database
make backup-db

# Restore database
BACKUP_FILE=backup_20241020_120000.sql make restore-db
```

## Troubleshooting

### Common Issues

1. **Pods not starting**
   ```bash
   kubectl describe pod <pod-name> -n viral-clip-ai
   kubectl logs <pod-name> -n viral-clip-ai
   ```

2. **Service connectivity issues**
   ```bash
   kubectl get svc -n viral-clip-ai
   kubectl get endpoints -n viral-clip-ai
   ```

3. **Resource constraints**
   ```bash
   kubectl top pods -n viral-clip-ai
   kubectl describe nodes
   ```

### Performance Tuning

1. **Database Performance**
   - Monitor connection pool usage
   - Optimize query performance
   - Consider read replicas for high load

2. **Worker Performance**
   - Adjust Celery concurrency settings
   - Monitor queue lengths
   - Scale workers based on workload

3. **Storage Performance**
   - Use SSD storage for databases
   - Configure MinIO with multiple drives
   - Implement proper caching strategies

## Security Considerations

### Network Security
- Use NetworkPolicies to restrict pod communication
- Configure ingress with proper SSL termination
- Implement proper firewall rules

### Data Security
- Encrypt data at rest
- Use strong passwords and secrets
- Regular security updates
- Implement proper access controls

### API Security
- Rate limiting configured
- Input validation
- Authentication and authorization
- CORS properly configured

## Support

For deployment issues or questions:
1. Check the logs using `make monitor-logs`
2. Review the troubleshooting section
3. Create an issue in the repository
4. Contact the development team

## Version History

- v1.0.0 - Initial production release
- v1.1.0 - Added UI Kubernetes deployment
- v1.2.0 - Enhanced monitoring and scaling