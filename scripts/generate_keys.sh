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
echo "  1. Create Docker secrets from these keys:"
echo "     docker secret create nextcloud_proxy_key $KEY_DIR/nextcloud_proxy_ed25519"
echo "     docker secret create nextcloud_proxy_pubkey $KEY_DIR/nextcloud_proxy_ed25519.pub"
echo "     docker secret create photoprism_proxy_key $KEY_DIR/photoprism_proxy_ed25519"
echo "     docker secret create photoprism_proxy_pubkey $KEY_DIR/photoprism_proxy_ed25519.pub"
echo ""
echo "  2. Deploy the proxy services using the Swarm stack files"
echo ""
echo -e "${RED}IMPORTANT: Keep these private keys secure and never commit them to git!${NC}"
