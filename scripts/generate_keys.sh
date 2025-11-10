#!/bin/bash
# Generate SSH keypairs for Docker Swarm proxy services
#
# This script generates ED25519 SSH keypairs for secure communication
# between Next_Prism and the Swarm proxy services.
#
# Usage: ./generate_keys.sh
#
# Author: Next_Prism Project
# License: MIT

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Key directory
KEY_DIR="./secrets/ssh-keys"

echo -e "${GREEN}Next_Prism SSH Keypair Generator${NC}"
echo "=================================="
echo ""

# Create key directory
echo "Creating key directory..."
mkdir -p "$KEY_DIR"
chmod 700 "$KEY_DIR"

# Generate Nextcloud proxy keypair
echo -e "${YELLOW}Generating Nextcloud proxy keypair...${NC}"
ssh-keygen -t ed25519 -f "$KEY_DIR/nextcloud_proxy_ed25519" -N "" -C "next-prism-nextcloud-proxy"
chmod 600 "$KEY_DIR/nextcloud_proxy_ed25519"
chmod 644 "$KEY_DIR/nextcloud_proxy_ed25519.pub"
echo -e "${GREEN}✓ Nextcloud proxy keypair generated${NC}"

# Generate PhotoPrism proxy keypair
echo -e "${YELLOW}Generating PhotoPrism proxy keypair...${NC}"
ssh-keygen -t ed25519 -f "$KEY_DIR/photoprism_proxy_ed25519" -N "" -C "next-prism-photoprism-proxy"
chmod 600 "$KEY_DIR/photoprism_proxy_ed25519"
chmod 644 "$KEY_DIR/photoprism_proxy_ed25519.pub"
echo -e "${GREEN}✓ PhotoPrism proxy keypair generated${NC}"

echo ""
echo -e "${GREEN}Key generation complete!${NC}"
echo ""
echo "Generated keys:"
echo "  Nextcloud: $KEY_DIR/nextcloud_proxy_ed25519"
echo "  PhotoPrism: $KEY_DIR/photoprism_proxy_ed25519"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "1. Create Docker Swarm secrets from these keys:"
echo ""
echo "   For Nextcloud proxy:"
echo "   $ docker secret create nextcloud_proxy_privkey $KEY_DIR/nextcloud_proxy_ed25519"
echo "   $ docker secret create nextcloud_proxy_pubkey $KEY_DIR/nextcloud_proxy_ed25519.pub"
echo ""
echo "   For PhotoPrism proxy:"
echo "   $ docker secret create photoprism_proxy_privkey $KEY_DIR/photoprism_proxy_ed25519"
echo "   $ docker secret create photoprism_proxy_pubkey $KEY_DIR/photoprism_proxy_ed25519.pub"
echo ""
echo "2. Copy private keys to Next_Prism container secrets:"
echo "   $ cp $KEY_DIR/nextcloud_proxy_ed25519 /path/to/nextprism/secrets/"
echo "   $ cp $KEY_DIR/photoprism_proxy_ed25519 /path/to/nextprism/secrets/"
echo ""
echo "3. Deploy proxy services to Swarm:"
echo "   $ docker stack deploy -c compose/nextcloud-proxy.yaml nextprism-nc-proxy"
echo "   $ docker stack deploy -c compose/photoprism-proxy.yaml nextprism-pp-proxy"
echo ""
echo "4. Update config.yaml with Swarm mode enabled:"
echo "   docker:"
echo "     swarm_mode: true"
echo ""
echo -e "${RED}IMPORTANT: Keep private keys secure and never commit to git!${NC}"
echo -e "${RED}           Add secrets/ directory to .gitignore${NC}"

# Optionally create secrets automatically if in Swarm mode
if docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null | grep -q 'active'; then
    echo ""
    echo -e "${YELLOW}Detected active Swarm node. Create secrets now? (y/N)${NC}"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo ""
        echo "Creating Docker secrets..."
        
        # Check if secrets already exist
        if docker secret ls --format '{{.Name}}' | grep -q 'nextcloud_proxy_privkey'; then
            echo -e "${YELLOW}Warning: nextcloud_proxy_privkey already exists, skipping...${NC}"
        else
            docker secret create nextcloud_proxy_privkey "$KEY_DIR/nextcloud_proxy_ed25519"
            echo -e "${GREEN}✓ Created nextcloud_proxy_privkey${NC}"
        fi
        
        if docker secret ls --format '{{.Name}}' | grep -q 'nextcloud_proxy_pubkey'; then
            echo -e "${YELLOW}Warning: nextcloud_proxy_pubkey already exists, skipping...${NC}"
        else
            docker secret create nextcloud_proxy_pubkey "$KEY_DIR/nextcloud_proxy_ed25519.pub"
            echo -e "${GREEN}✓ Created nextcloud_proxy_pubkey${NC}"
        fi
        
        if docker secret ls --format '{{.Name}}' | grep -q 'photoprism_proxy_privkey'; then
            echo -e "${YELLOW}Warning: photoprism_proxy_privkey already exists, skipping...${NC}"
        else
            docker secret create photoprism_proxy_privkey "$KEY_DIR/photoprism_proxy_ed25519"
            echo -e "${GREEN}✓ Created photoprism_proxy_privkey${NC}"
        fi
        
        if docker secret ls --format '{{.Name}}' | grep -q 'photoprism_proxy_pubkey'; then
            echo -e "${YELLOW}Warning: photoprism_proxy_pubkey already exists, skipping...${NC}"
        else
            docker secret create photoprism_proxy_pubkey "$KEY_DIR/photoprism_proxy_ed25519.pub"
            echo -e "${GREEN}✓ Created photoprism_proxy_pubkey${NC}"
        fi
        
        echo ""
        echo -e "${GREEN}Docker secrets created successfully!${NC}"
        echo ""
        echo "Verify secrets:"
        echo "  $ docker secret ls"
    fi
fi
