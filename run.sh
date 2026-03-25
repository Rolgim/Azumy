#!/usr/bin/env bash
set -e

ENV_FILE=".env"
NETRC_FILE="secrets/netrc"

# First setup: ask for workspace and credentials

if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║         Azulweb — First setup        ║"
    echo "  ╚══════════════════════════════════════╝"
    echo ""

    # Workspace
    read -rp "  Workspace path (where FITS files will be stored)? " WORKSPACE
    WORKSPACE="${WORKSPACE:-./data}"
    # create workspace if it doesn't exist
    mkdir -p "$WORKSPACE"

    echo "WORKSPACE=$WORKSPACE" > "$ENV_FILE"
    echo "  ✓ Workspace: $WORKSPACE"
fi

# Credentials EAS/IDR
if [ ! -f "$NETRC_FILE" ]; then
  mkdir -p secrets
  touch "$NETRC_FILE"
  chmod 600 "$NETRC_FILE"
 
  echo ""
  echo "  Data provider credentials"
  echo "  (leave blank to skip — SAS public access still works)"
  echo ""
 
  # IDR
  echo "  — IDR (easidr.esac.esa.int)"
  read -rp "    Username (email)? " IDR_USER
  if [ -n "$IDR_USER" ]; then
    read -rsp "    Password? " IDR_PASS
    echo ""
    cat >> "$NETRC_FILE" << NETRC
machine easidr.esac.esa.int
login $IDR_USER
password $IDR_PASS
NETRC
    echo "  ✓ IDR credentials saved."
  else
    echo "  ✓ IDR skipped."
  fi
 
  echo ""
 
  # DSS
  echo "  — DSS (eas-dps-rest-ops.esac.esa.int)"
  read -rp "    Username (email)? " DSS_USER
  if [ -n "$DSS_USER" ]; then
    read -rsp "    Password? " DSS_PASS
    echo ""
    cat >> "$NETRC_FILE" << NETRC
machine eas-dps-rest-ops.esac.esa.int
login $DSS_USER
password $DSS_PASS
NETRC
    echo "  ✓ DSS credentials saved."
  else
    echo "  ✓ DSS skipped."
  fi
fi

# Start docker compose 

echo ""
echo "  Starting Azulweb..."
echo ""

# Load .env
export $(grep -v '^#' "$ENV_FILE" | xargs)

docker compose up --build -d

echo ""
echo "  ✓ Azulweb is running at http://localhost:8000"
echo ""
echo "  To stop:   docker compose down"
echo "  To logs:   docker compose logs -f"
echo ""