# Docker Swarm Proxy Architecture Design

## Overview

The proxy architecture enables Next_Prism to execute commands on Nextcloud and PhotoPrism containers in Docker Swarm environments where direct `docker exec` isn't available from the main application container.

## Problem Statement

In Docker Swarm mode:
- Tasks (container instances) can run on different nodes
- Direct `docker exec` requires access to the specific node where the container runs
- Docker socket access from containers is limited for security
- Service-to-service communication needs to cross node boundaries

## Solution: SSH Proxy Services

We deploy lightweight proxy containers that:
1. Run on the same node/network as their target service
2. Accept SSH connections with keypair authentication
3. Execute whitelisted commands on the target container
4. Return results to the Next_Prism application

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Swarm Cluster                    │
│                                                               │
│  ┌──────────────┐                                            │
│  │  Next_Prism  │                                            │
│  │  Application │                                            │
│  └──────┬───────┘                                            │
│         │ SSH (port 2222)                                    │
│         │                                                    │
│    ┌────┴─────────────────────────────┐                     │
│    │                                   │                     │
│    ▼                                   ▼                     │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │ Nextcloud Proxy  │         │PhotoPrism Proxy  │          │
│  │   (SSH Server)   │         │   (SSH Server)   │          │
│  └────────┬─────────┘         └────────┬─────────┘          │
│           │ docker exec                │ docker exec        │
│           ▼                            ▼                     │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │    Nextcloud     │         │   PhotoPrism     │          │
│  │    Container     │         │    Container     │          │
│  └──────────────────┘         └──────────────────┘          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Security Model

### Authentication
- **ED25519 SSH keypairs** for authentication (no passwords)
- Private keys stored as Docker secrets
- Public keys baked into proxy images or mounted as secrets
- Separate keypair for each proxy service

### Authorization
- **Command whitelisting**: Only specific commands are allowed
- Command validation before execution
- No shell access (restricted to specific executables)
- Audit logging of all command executions

### Network Isolation
- Proxies only accessible on overlay network
- No external port exposure required
- Communication confined to Swarm internal network

## Component Design

### 1. Proxy Container Requirements

**Base Image:** Alpine Linux (minimal footprint)
**Components:**
- OpenSSH server (dropbear or openssh-server)
- Docker CLI (for docker exec)
- Bash/sh for command execution
- Command validation script

**Configuration:**
- SSH port: 2222 (non-standard for clarity)
- Root login disabled
- Password authentication disabled
- Pubkey authentication only
- Restricted shell with command validation

### 2. Command Whitelisting

**Nextcloud Proxy Allowed Commands:**
```
php occ files:scan [options]
php occ memories:index [options]
php occ status
```

**PhotoPrism Proxy Allowed Commands:**
```
photoprism index [options]
photoprism import [options]
photoprism status
```

**Validation Logic:**
1. Parse incoming SSH command
2. Check against whitelist patterns
3. Validate arguments (no command injection)
4. Execute if valid, reject otherwise
5. Return stdout/stderr to caller

### 3. SSH Connection Management

**Connection Pooling:**
- Maintain persistent SSH connections
- Reuse connections for multiple commands
- Automatic reconnection on failure
- Connection timeout and keepalive

**Error Handling:**
- Retry logic with exponential backoff
- Fallback to direct exec if proxy unavailable
- Clear error messages for debugging
- Health checks for proxy availability

### 4. Service Discovery

**Discovery Methods:**
1. **Docker DNS**: Use service names (e.g., `nextcloud-proxy`)
2. **Docker API**: Query Swarm services
3. **Environment Variables**: Explicit configuration
4. **Health Checks**: Verify proxy accessibility before use

**Discovery Flow:**
```
1. Check if Swarm mode is active
2. Look for proxy service via Docker API
3. Resolve service DNS name
4. Test SSH connectivity
5. Cache successful connection info
6. Use proxy for subsequent commands
```

## Implementation Components

### Files to Create

1. **docker/proxy-nextcloud.Dockerfile**
   - Alpine base with OpenSSH
   - Docker CLI installation
   - Command validation script
   - SSH configuration
   - Public key setup

2. **docker/proxy-photoprism.Dockerfile**
   - Similar to Nextcloud proxy
   - PhotoPrism-specific whitelist

3. **src/docker_interface/ssh_proxy.py**
   - Paramiko SSH client wrapper
   - Connection pool management
   - Command execution over SSH
   - Error handling and retries

4. **src/docker_interface/proxy_discovery.py**
   - Service discovery logic
   - Health checking
   - Proxy availability detection

5. **compose/nextcloud-proxy.yaml**
   - Swarm service definition
   - Placement constraints
   - Secret bindings
   - Network configuration

6. **compose/photoprism-proxy.yaml**
   - Similar to Nextcloud proxy stack

7. **scripts/validate_command.sh**
   - Shell script for command whitelisting
   - Used by both proxy containers

## Deployment Process

### 1. Generate SSH Keypairs
```bash
./scripts/generate_keys.sh
```
Creates:
- `secrets/ssh-keys/nextcloud_proxy_ed25519`
- `secrets/ssh-keys/nextcloud_proxy_ed25519.pub`
- `secrets/ssh-keys/photoprism_proxy_ed25519`
- `secrets/ssh-keys/photoprism_proxy_ed25519.pub`

### 2. Create Docker Secrets
```bash
docker secret create nextcloud_proxy_privkey secrets/ssh-keys/nextcloud_proxy_ed25519
docker secret create nextcloud_proxy_pubkey secrets/ssh-keys/nextcloud_proxy_ed25519.pub
docker secret create photoprism_proxy_privkey secrets/ssh-keys/photoprism_proxy_ed25519
docker secret create photoprism_proxy_pubkey secrets/ssh-keys/photoprism_proxy_ed25519.pub
```

### 3. Deploy Proxy Services
```bash
docker stack deploy -c compose/nextcloud-proxy.yaml nextcloud-proxy
docker stack deploy -c compose/photoprism-proxy.yaml photoprism-proxy
```

### 4. Deploy Main Application
```bash
docker stack deploy -c compose/swarm-stack.yaml next-prism
```

## Configuration

### Environment Variables

**Next_Prism Application:**
```yaml
SWARM_MODE: "true"  # Or auto-detect
NEXTCLOUD_PROXY_SERVICE: "nextcloud-proxy"
PHOTOPRISM_PROXY_SERVICE: "photoprism-proxy"
PROXY_SSH_PORT: "2222"
```

### Secrets

Secrets are mounted at:
- `/run/secrets/nextcloud_proxy_privkey`
- `/run/secrets/photoprism_proxy_privkey`

## Health Checks

### Proxy Health Check
- SSH connection test every 30 seconds
- Verify command execution capability
- Automatic failover if unhealthy

### Monitoring
- Log all SSH connection attempts
- Track command execution times
- Alert on connection failures
- Statistics in web UI

## Error Handling

### Connection Failures
1. Retry with exponential backoff (1s, 2s, 4s)
2. After 3 retries, check if Swarm mode is still active
3. If not, fall back to direct exec
4. Log warnings for investigation

### Command Failures
1. Return error to caller immediately
2. Log full error output
3. Don't retry command failures (could be intentional)
4. Surface errors in web UI

## Performance Considerations

### Connection Overhead
- SSH handshake: ~100-200ms
- Command execution: depends on command
- Connection reuse eliminates repeated handshakes

### Optimization Strategies
- Keep connections alive between commands
- Connection pool with multiple connections
- Batch commands when possible
- Async command execution for non-blocking

## Security Considerations

### Threat Model

**Threats Mitigated:**
- Unauthorized command execution (keypair auth)
- Command injection (whitelist validation)
- Lateral movement (network isolation)
- Key exposure (Docker secrets)

**Remaining Risks:**
- Compromised proxy container (mitigated by command whitelist)
- Docker socket access (inherent to design)
- Container escape (Docker security boundary)

### Security Checklist
- ✅ No password authentication
- ✅ Command whitelisting enforced
- ✅ Keys stored as Docker secrets
- ✅ No root SSH login
- ✅ Minimal container surface area
- ✅ Audit logging enabled
- ✅ Network segmentation (overlay network)

## Testing Strategy

### Unit Tests
- Command validation logic
- SSH connection handling
- Service discovery

### Integration Tests
- End-to-end SSH command execution
- Proxy failover scenarios
- Command whitelist enforcement

### Manual Tests
- Deploy in Swarm environment
- Execute commands through proxies
- Verify logging and monitoring
- Test failure scenarios

## Maintenance

### Key Rotation
1. Generate new keypairs
2. Update secrets
3. Restart proxy services
4. Update Next_Prism configuration
5. Verify connectivity

### Updating Proxy Images
1. Update Dockerfile
2. Build new image
3. Push to registry
4. Update stack file with new image
5. `docker service update` for rolling update

## Future Enhancements

- [ ] Multiple proxy instances for high availability
- [ ] Load balancing across proxy instances
- [ ] Certificate-based authentication (mutual TLS)
- [ ] WebSocket support for streaming output
- [ ] Proxy metrics export (Prometheus)
- [ ] Automated key rotation
- [ ] Support for additional services beyond Nextcloud/PhotoPrism

## References

- Docker Swarm documentation: https://docs.docker.com/engine/swarm/
- Paramiko SSH library: https://www.paramiko.org/
- OpenSSH configuration: https://www.openssh.com/manual.html
- Docker secrets: https://docs.docker.com/engine/swarm/secrets/
