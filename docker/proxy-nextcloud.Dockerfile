# Nextcloud Proxy Dockerfile
# Lightweight SSH proxy for executing Nextcloud occ commands in Docker Swarm
#
# This proxy accepts SSH connections from Next_Prism and executes whitelisted
# Nextcloud commands via docker exec on the Nextcloud container.
#
# Author: Next_Prism Project
# License: MIT

FROM alpine:3.19

LABEL maintainer="LoopeyTheGreat"
LABEL description="Next_Prism Nextcloud Proxy - SSH gateway for Nextcloud commands"
LABEL service="nextcloud-proxy"

# Install required packages
RUN apk add --no-cache \
    # SSH server
    openssh-server \
    # Docker CLI (for docker exec)
    docker-cli \
    # Shell utilities
    bash \
    # Logging
    tini \
    && rm -rf /var/cache/apk/*

# Create proxy user (non-root)
RUN adduser -D -h /home/proxyuser -s /bin/bash proxyuser && \
    mkdir -p /home/proxyuser/.ssh && \
    chown -R proxyuser:proxyuser /home/proxyuser

# Configure SSH server
RUN mkdir -p /run/sshd && \
    # Generate host keys
    ssh-keygen -A && \
    # Configure sshd
    sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config && \
    sed -i 's/#PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#Port.*/Port 2222/' /etc/ssh/sshd_config && \
    sed -i 's/#PermitEmptyPasswords.*/PermitEmptyPasswords no/' /etc/ssh/sshd_config && \
    sed -i 's/#StrictModes.*/StrictModes yes/' /etc/ssh/sshd_config && \
    sed -i 's/#AllowTcpForwarding.*/AllowTcpForwarding no/' /etc/ssh/sshd_config && \
    sed -i 's/#X11Forwarding.*/X11Forwarding no/' /etc/ssh/sshd_config && \
    sed -i 's/#AllowAgentForwarding.*/AllowAgentForwarding no/' /etc/ssh/sshd_config && \
    # Set ClientAlive settings to detect dead connections
    echo "ClientAliveInterval 30" >> /etc/ssh/sshd_config && \
    echo "ClientAliveCountMax 3" >> /etc/ssh/sshd_config

# Copy command validation script
COPY scripts/validate_command.sh /usr/local/bin/validate_command.sh
RUN chmod +x /usr/local/bin/validate_command.sh

# Set up forced command for SSH (all connections run validation script)
RUN mkdir -p /home/proxyuser/.ssh && \
    echo 'command="/usr/local/bin/validate_command.sh nextcloud $SSH_ORIGINAL_COMMAND",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty' > /home/proxyuser/.ssh/authorized_keys_template

# Create entrypoint script
RUN cat > /docker-entrypoint.sh << 'EOF'
#!/bin/bash
set -e

echo "Starting Nextcloud Proxy..."

# Set target container name from environment
export NEXTCLOUD_CONTAINER="${NEXTCLOUD_CONTAINER:-nextcloud}"
echo "Target Nextcloud container: $NEXTCLOUD_CONTAINER"

# Setup authorized_keys from secret or environment
if [ -f /run/secrets/nextcloud_proxy_pubkey ]; then
    echo "Loading public key from Docker secret..."
    PUBKEY=$(cat /run/secrets/nextcloud_proxy_pubkey)
elif [ -n "$SSH_PUBKEY" ]; then
    echo "Loading public key from environment..."
    PUBKEY="$SSH_PUBKEY"
else
    echo "ERROR: No public key found in secrets or environment"
    exit 1
fi

# Set up authorized_keys with forced command
cat /home/proxyuser/.ssh/authorized_keys_template > /home/proxyuser/.ssh/authorized_keys
echo "$PUBKEY" >> /home/proxyuser/.ssh/authorized_keys
chmod 600 /home/proxyuser/.ssh/authorized_keys
chown proxyuser:proxyuser /home/proxyuser/.ssh/authorized_keys

echo "SSH authorized_keys configured"

# Start SSH server
echo "Starting SSH server on port 2222..."
exec /usr/sbin/sshd -D -e
EOF

RUN chmod +x /docker-entrypoint.sh

# Expose SSH port
EXPOSE 2222

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD nc -z localhost 2222 || exit 1

# Use tini as init system
ENTRYPOINT ["/sbin/tini", "--"]

# Run entrypoint
CMD ["/docker-entrypoint.sh"]
