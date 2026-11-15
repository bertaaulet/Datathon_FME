#!/usr/bin/env bash
# Vision experiment: a second llama-server with the same Qwen model and its projector
# (--mmproj), on VISION_PORT, so predict.py can send the problem image (PREDICT_VISION).
# The official server (math-llm, 8081) is not touched.
#
#   ./board/07_vision.sh download          # the projector, 205 MB, checked with SHA256
#   ./board/07_vision.sh start             # start it by hand (stops at reboot)
#   ./board/07_vision.sh status            # is it up, does it see images, RAM
#   ./board/07_vision.sh stop
#   ./board/07_vision.sh install-service   # ONLY if the team adopts it for the last call
#   ./board/07_vision.sh remove-service
source "$(dirname "$0")/common.sh"

MMPROJ_PATH="$MODELS_DIR/$MMPROJ_FILE"
PID_FILE="$HOME/math-vision.pid"
LOG_FILE="$HOME/math-vision.log"
MIN_FREE_MB=900   # the weights are shared with math-llm (mmap); the projector and the context are not

available_mb() { free -m | awk 'NR==2 {print $7}'; }

ram() { free -m | awk 'NR==2 {printf "  RAM: %d MB used, %d MB available\n", $3, $7}'; }

check_vision() {
  local props
  props="$(curl -sf "http://127.0.0.1:$VISION_PORT/props" || true)"
  [[ "$props" == *'"vision":true'* ]]
}

download() {
  step "Projector $MMPROJ_FILE"
  if [ -f "$MMPROJ_PATH" ] && echo "$MMPROJ_SHA256  $MMPROJ_PATH" | sha256sum --check --status; then
    ok "already downloaded and verified"; return
  fi
  local url="https://huggingface.co/$LLM_REPO/resolve/$LLM_REVISION/$MMPROJ_FILE"
  wget --quiet --show-progress --continue -O "$MMPROJ_PATH.part" "$url"
  if echo "$MMPROJ_SHA256  $MMPROJ_PATH.part" | sha256sum --check --status; then
    mv "$MMPROJ_PATH.part" "$MMPROJ_PATH"; ok "verified: $(du -h "$MMPROJ_PATH" | cut -f1)"
  else
    rm -f "$MMPROJ_PATH.part"; die "$MMPROJ_FILE doesn't match its SHA256. Run download again."
  fi
}

start() {
  [ -x "$LLAMA_SERVER" ] || die "llama-server not found ($LLAMA_SERVER)"
  [ -f "$LLM_PATH" ] || die "model not found: $LLM_PATH"
  [ -f "$MMPROJ_PATH" ] || die "projector not found. Run: ./board/07_vision.sh download"
  if curl -sf "http://127.0.0.1:$VISION_PORT/health" >/dev/null 2>&1; then
    ok "already running on 127.0.0.1:$VISION_PORT"; ram; return
  fi
  local free_mb; free_mb="$(available_mb)"
  [ "$free_mb" -ge "$MIN_FREE_MB" ] || die "only $free_mb MB available (need $MIN_FREE_MB). Stop the tutor first: sudo systemctl stop math-tutor"
  step "Starting the vision server on 127.0.0.1:$VISION_PORT ($free_mb MB available before)"
  nohup "$LLAMA_SERVER" -m "$LLM_PATH" --mmproj "$MMPROJ_PATH" \
    --image-max-tokens "$VISION_IMAGE_TOKENS" \
    --host 127.0.0.1 --port "$VISION_PORT" --threads "$LLM_THREADS" --ctx-size "$LLM_CTX" \
    --parallel 1 --cache-ram 0 --ctx-checkpoints 2 \
    --jinja --reasoning off --reasoning-budget 0 >"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  wait_for_health "$VISION_PORT" 180 || die "it didn't start. See: tail -50 $LOG_FILE"
  check_vision || die "it started but doesn't say it sees images. See: tail -50 $LOG_FILE"
  ok "vision server ready (PID $(cat "$PID_FILE")), log in $LOG_FILE"
  ram
}

stop() {
  if [ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null; then
    rm -f "$PID_FILE"; ok "stopped"
  else
    rm -f "$PID_FILE"
    systemctl is-active --quiet math-vision 2>/dev/null && warn "it runs as a service: ./board/07_vision.sh remove-service" \
      || ok "it wasn't running"
  fi
  ram
}

status() {
  if curl -sf "http://127.0.0.1:$VISION_PORT/health" >/dev/null 2>&1; then
    check_vision && ok "up on $VISION_PORT and sees images" || fail "up on $VISION_PORT but WITHOUT vision"
  else
    warn "not running on $VISION_PORT"
  fi
  [ -f "$MMPROJ_PATH" ] && ok "projector: $MMPROJ_PATH" || warn "projector not downloaded"
  grep -E '^PREDICT_VISION=' "$REPO_DIR/config.env" | sed 's/^/  config.env: /'
  ram
}

install_service() {
  [ -f "$MMPROJ_PATH" ] || die "projector not found. Run: ./board/07_vision.sh download"
  stop >/dev/null || true
  step "Installing math-vision.service (starts at boot)"
  sed -e "s|@USER@|$USER|g" -e "s|@LLAMA_SERVER@|$LLAMA_SERVER|g" -e "s|@LLM_PATH@|$LLM_PATH|g" \
      -e "s|@MMPROJ_PATH@|$MMPROJ_PATH|g" -e "s|@VISION_PORT@|$VISION_PORT|g" \
      -e "s|@VISION_IMAGE_TOKENS@|$VISION_IMAGE_TOKENS|g" \
      -e "s|@LLM_THREADS@|$LLM_THREADS|g" -e "s|@LLM_CTX@|$LLM_CTX|g" \
      "$REPO_DIR/board/systemd/math-vision.service" | sudo tee /etc/systemd/system/math-vision.service >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable --now math-vision
  wait_for_health "$VISION_PORT" 180 || die "it didn't start. See: journalctl -u math-vision -n 50"
  check_vision || die "it doesn't say it sees images. See: journalctl -u math-vision -n 50"
  ok "math-vision running and enabled at boot"
  ram
}

remove_service() {
  sudo systemctl disable --now math-vision 2>/dev/null || true
  sudo rm -f /etc/systemd/system/math-vision.service
  sudo systemctl daemon-reload
  ok "math-vision removed"
  ram
}

case "${1:-status}" in
  download) download ;;
  start) start ;;
  stop) stop ;;
  status) status ;;
  install-service) install_service ;;
  remove-service) remove_service ;;
  *) die "unknown command: $1 (download, start, status, stop, install-service, remove-service)" ;;
esac
