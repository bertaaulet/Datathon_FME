#!/usr/bin/env bash
# Run the tutor web app (app/server.py) as a systemd service, so it starts at
# boot after the two model servers. Needs sudo. Run it again after you change
# TUTOR_PORT in config.env.
#
# By default the tutor listens on 127.0.0.1 only. If the App Lab LED app runs in
# a container and can't reach it there, install it with:
#   TUTOR_HOST=0.0.0.0 ./board/06_install_tutor_service.sh
source "$(dirname "$0")/common.sh"

TUTOR_PORT="${TUTOR_PORT:-8090}"
TUTOR_HOST="${TUTOR_HOST:-127.0.0.1}"

[ -f "$REPO_DIR/app/server.py" ] || die "app/server.py not found in $REPO_DIR."
systemctl is-enabled --quiet math-llm 2>/dev/null || warn "math-llm is not installed yet. Run ./board/04_install_services.sh first."

pid="$(pgrep -f -- "app/server.py" | head -1 || true)"
service_pid="$(systemctl show -p MainPID --value math-tutor 2>/dev/null || true)"
if [ -n "$pid" ] && [ "$pid" != "$service_pid" ]; then
  die "a tutor you started by hand (PID $pid) is running. Stop it with: kill $pid"
fi

step "Installing math-tutor.service (listening on $TUTOR_HOST:$TUTOR_PORT)"
sed -e "s|@USER@|$USER|g" -e "s|@REPO_DIR@|$REPO_DIR|g" \
    -e "s|@TUTOR_HOST@|$TUTOR_HOST|g" -e "s|@TUTOR_PORT@|$TUTOR_PORT|g" \
    "$REPO_DIR/board/systemd/math-tutor.service" | sudo tee /etc/systemd/system/math-tutor.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable math-tutor
sudo systemctl restart math-tutor

step "Waiting for the tutor"
for _ in $(seq 30); do
  if curl -sf "http://127.0.0.1:$TUTOR_PORT/" >/dev/null 2>&1; then
    ok "tutor ready on $TUTOR_HOST:$TUTOR_PORT"
    free -m | awk 'NR==2 {printf "  RAM: %d MB used, %d MB available\n", $3, $7}'
    exit 0
  fi
  sleep 1
done
die "the tutor didn't answer. See: journalctl -u math-tutor -n 50"
