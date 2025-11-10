#!/bin/bash
# Command Validation Script for Next_Prism Proxies
#
# This script validates and executes commands from SSH connections,
# implementing a strict whitelist to prevent unauthorized operations.
#
# Usage: validate_command.sh <service_type> <command> [args...]
#   service_type: "nextcloud" or "photoprism"
#   command: The command to validate and execute
#
# Author: Next_Prism Project
# License: MIT

set -e

# Configuration
SERVICE_TYPE="${1:-}"
shift || true
COMMAND_LINE="$*"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

# Error function
error() {
    log "ERROR: $*"
    exit 1
}

# Validate service type
if [[ -z "$SERVICE_TYPE" ]]; then
    error "Service type not specified"
fi

if [[ "$SERVICE_TYPE" != "nextcloud" && "$SERVICE_TYPE" != "photoprism" ]]; then
    error "Invalid service type: $SERVICE_TYPE (must be 'nextcloud' or 'photoprism')"
fi

# Validate command line is not empty
if [[ -z "$COMMAND_LINE" ]]; then
    error "No command specified"
fi

log "Validating command for $SERVICE_TYPE: $COMMAND_LINE"

# Parse command into array
read -ra CMD_ARRAY <<< "$COMMAND_LINE"

# Command validation functions
validate_nextcloud_command() {
    local cmd="${CMD_ARRAY[0]}"
    local subcmd="${CMD_ARRAY[1]:-}"
    local action="${CMD_ARRAY[2]:-}"
    
    # Must start with 'php'
    if [[ "$cmd" != "php" ]]; then
        error "Nextcloud commands must start with 'php'"
    fi
    
    # Must be 'occ'
    if [[ "$subcmd" != "occ" ]]; then
        error "Nextcloud commands must use 'occ'"
    fi
    
    # Validate allowed occ commands
    case "$action" in
        "files:scan"|"memories:index"|"status")
            log "Command validated: $action"
            return 0
            ;;
        *)
            error "Unauthorized occ command: $action"
            ;;
    esac
}

validate_photoprism_command() {
    local cmd="${CMD_ARRAY[0]}"
    local action="${CMD_ARRAY[1]:-}"
    
    # Must start with 'photoprism'
    if [[ "$cmd" != "photoprism" ]]; then
        error "PhotoPrism commands must start with 'photoprism'"
    fi
    
    # Validate allowed photoprism commands
    case "$action" in
        "index"|"import"|"status")
            log "Command validated: $action"
            return 0
            ;;
        *)
            error "Unauthorized photoprism command: $action"
            ;;
    esac
}

# Sanitize arguments to prevent injection
sanitize_args() {
    local args=("$@")
    
    for arg in "${args[@]}"; do
        # Check for dangerous characters
        if [[ "$arg" =~ [\;\|\&\$\`] ]]; then
            error "Dangerous characters detected in arguments"
        fi
    done
}

# Validate based on service type
if [[ "$SERVICE_TYPE" == "nextcloud" ]]; then
    validate_nextcloud_command
elif [[ "$SERVICE_TYPE" == "photoprism" ]]; then
    validate_photoprism_command
fi

# Sanitize all arguments
sanitize_args "${CMD_ARRAY[@]}"

# Get target container name from environment
if [[ "$SERVICE_TYPE" == "nextcloud" ]]; then
    TARGET_CONTAINER="${NEXTCLOUD_CONTAINER:-nextcloud}"
elif [[ "$SERVICE_TYPE" == "photoprism" ]]; then
    TARGET_CONTAINER="${PHOTOPRISM_CONTAINER:-photoprism}"
fi

log "Executing in container: $TARGET_CONTAINER"

# Execute the command via docker exec
# We use 'docker exec' to run commands in the target container
if ! docker exec "$TARGET_CONTAINER" $COMMAND_LINE; then
    error "Command execution failed"
fi

log "Command completed successfully"
exit 0
