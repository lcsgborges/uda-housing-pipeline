#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-true}" != "false" ] && [ "${RUN_MIGRATIONS:-true}" != "0" ]; then
    echo "Running database migrations..."
    alembic upgrade head
fi

exec "$@"
