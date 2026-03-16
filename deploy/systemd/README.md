# Systemd units for protest analysis worker

Copy the service unit to `/etc/systemd/system/` and enable it:

```bash
sudo cp deploy/systemd/soscuba-protest-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now soscuba-protest-worker
```

Verify status and logs:

```bash
sudo systemctl status soscuba-protest-worker
sudo journalctl -u soscuba-protest-worker -f
```

Important:
- Keep `PROTEST_SCHEDULER_IN_WEB=0` for the web service.
- Keep `PROTEST_SCHEDULER_ENABLED=1` for this worker service.
- The execution interval is taken from DB setting `protest.frontend_refresh_seconds`.
