#!/usr/bin/env bash
set -e

ENV_FILE=".env"

# First run setup
if [ ! -f "$ENV_FILE" ]; then
  echo ""
  echo "  ╔══════════════════════════════════════╗"
  echo "  ║        Azumy —  Initial setup        ║"
  echo "  ╚══════════════════════════════════════╝"
  echo ""

  # Workspace
  read -rp "  Workspace path (where FITS files will be stored - absolute path)? " WORKSPACE
  WORKSPACE="${WORKSPACE:-./data}"
  WORKSPACE="${WORKSPACE/#\~/$HOME}"   # expand ~
  mkdir -p "$WORKSPACE"
  echo "  ✓ Workspace: $WORKSPACE"

  # IDR credentials
  echo ""
  echo "  — IDR credentials (easidr.esac.esa.int)"
  echo "    Leave blank to skip — SAS public access still works"
  read -rp "    Username? " IDR_USER
  if [ -n "$IDR_USER" ]; then
    read -rsp "    Password? " IDR_PASS
    echo ""
    echo "  ✓ IDR credentials saved."
  fi

  # DSS credentials
  echo ""
  echo "  — DSS credentials (eas-dps-rest-ops.esac.esa.int)"
  echo "    Leave blank to skip"
  read -rp "    Username? " DSS_USER
  if [ -n "$DSS_USER" ]; then
    read -rsp "    Password? " DSS_PASS
    echo ""
    echo "  ✓ DSS credentials saved."
  fi

  # Write .env
  cat > "$ENV_FILE" << ENVEOF
WORKSPACE=$WORKSPACE
IDR_USER=${IDR_USER:-}
IDR_PASS=${IDR_PASS:-}
DSS_USER=${DSS_USER:-}
DSS_PASS=${DSS_PASS:-}
ENVEOF

  echo ""
  echo "  ✓ Configuration saved to .env"
fi

# Docker compose
echo ""
echo "  Starting Azumy..."
echo ""

docker compose --env-file "$ENV_FILE" up --build -d

echo ""
echo "  ✓ Azumy is running at http://localhost:8000"
echo ""
echo "  To stop:      docker compose down"
echo "  To view logs: docker compose logs -f"
echo "  To reconfigure: rm .env && ./run.sh"
echo ""
