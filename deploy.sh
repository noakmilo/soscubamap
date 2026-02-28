#!/usr/bin/env bash
set -euo pipefail

APP_USER="soscuba"
APP_DIR="/home/${APP_USER}/soscubamap"
SERVICE_NAME="soscuba"

run_as_app_user() {
  if [[ $EUID -eq 0 ]]; then
    sudo -u "${APP_USER}" "$@"
  else
    "$@"
  fi
}

if [[ ! -d "${APP_DIR}" ]]; then
  echo "No existe el repo en ${APP_DIR}" >&2
  exit 1
fi

if [[ ! -x "${APP_DIR}/.venv/bin/flask" ]]; then
  echo "No existe .venv o Flask no esta instalado en ${APP_DIR}" >&2
  exit 1
fi

echo "[1/3] Git pull"
run_as_app_user git -C "${APP_DIR}" pull

echo "[2/3] Migraciones"
run_as_app_user "${APP_DIR}/.venv/bin/flask" --app run.py db upgrade

echo "[3/3] Reinicio de servicio"
if [[ $EUID -eq 0 ]]; then
  systemctl restart "${SERVICE_NAME}"
else
  sudo systemctl restart "${SERVICE_NAME}"
fi

echo "Listo. Logs: sudo journalctl -u ${SERVICE_NAME} -f"
