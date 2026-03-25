#!/bin/sh
set -e

# Initialize /root/.netrc from environment variables
rm -f /root/.netrc
touch /root/.netrc
chmod 600 /root/.netrc

if [ -n "$IDR_USER" ] && [ -n "$IDR_PASS" ]; then
  printf "machine easidr.esac.esa.int\nlogin %s\npassword %s\n" \
    "$IDR_USER" "$IDR_PASS" >> /root/.netrc
fi

if [ -n "$DSS_USER" ] && [ -n "$DSS_PASS" ]; then
  printf "machine eas-dps-rest-ops.esac.esa.int\nlogin %s\npassword %s\n" \
    "$DSS_USER" "$DSS_PASS" >> /root/.netrc
fi

exec uv run uvicorn main:app --host 0.0.0.0 --port 8000