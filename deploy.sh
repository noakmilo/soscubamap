#!/usr/bin/env bash
set -euo pipefail

APP_USER="soscuba"
APP_DIR="/home/${APP_USER}/soscubamap"
SERVICE_NAME="soscuba"
CELERY_WORKER_SERVICE="${SERVICE_NAME}-celery-worker"
CELERY_BEAT_SERVICE="${SERVICE_NAME}-celery-beat"
FLASK_APP_PATH="${APP_DIR}/run.py"
MIGRATIONS_DIR="${APP_DIR}/migrations"

run_as_app_user() {
  if [[ $EUID -eq 0 ]]; then
    sudo -u "${APP_USER}" "$@"
  else
    "$@"
  fi
}

systemctl_cmd() {
  if [[ $EUID -eq 0 ]]; then
    systemctl "$@"
  else
    sudo systemctl "$@"
  fi
}

service_exists() {
  local service_name="$1"
  systemctl list-unit-files "${service_name}.service" --no-legend 2>/dev/null | grep -q "^${service_name}.service"
}

if [[ ! -d "${APP_DIR}" ]]; then
  echo "No existe el repo en ${APP_DIR}" >&2
  exit 1
fi

if [[ ! -x "${APP_DIR}/.venv/bin/flask" ]]; then
  echo "No existe .venv o Flask no esta instalado en ${APP_DIR}" >&2
  exit 1
fi

if [[ ! -f "${APP_DIR}/requirements.txt" ]]; then
  echo "No existe requirements.txt en ${APP_DIR}" >&2
  exit 1
fi

if [[ ! -d "${MIGRATIONS_DIR}" ]]; then
  echo "No existe el directorio de migraciones en ${MIGRATIONS_DIR}" >&2
  exit 1
fi

echo "[1/4] Sync git"
run_as_app_user git -C "${APP_DIR}" fetch origin main
run_as_app_user git -C "${APP_DIR}" reset --hard origin/main

echo "[2/4] Dependencias"
run_as_app_user "${APP_DIR}/.venv/bin/python" -m pip install -r "${APP_DIR}/requirements.txt"

echo "[3/4] Migraciones"
if [[ $EUID -eq 0 ]]; then
  sudo -u "${APP_USER}" bash -lc "cd '${APP_DIR}' && '${APP_DIR}/.venv/bin/flask' --app '${FLASK_APP_PATH}' db upgrade -d '${MIGRATIONS_DIR}'"
else
  (cd "${APP_DIR}" && "${APP_DIR}/.venv/bin/flask" --app "${FLASK_APP_PATH}" db upgrade -d "${MIGRATIONS_DIR}")
fi

echo "[4/4] Reinicio de servicio"
systemctl_cmd restart "${SERVICE_NAME}"

if service_exists "${CELERY_WORKER_SERVICE}"; then
  systemctl_cmd restart "${CELERY_WORKER_SERVICE}"
fi

if service_exists "${CELERY_BEAT_SERVICE}"; then
  systemctl_cmd restart "${CELERY_BEAT_SERVICE}"
fi

echo "Listo. Logs: sudo journalctl -u ${SERVICE_NAME} -f"
