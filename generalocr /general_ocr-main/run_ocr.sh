#!/usr/bin/env bash
# Start the local llama.cpp server (Surya 2.5 recognition) and run the DocumentOCR pipeline.
# Usage: ./run_ocr.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="/home/metadeep-one/projects/documentocr/datasets/surya_gguf"
CONTAINER="surya-llama"
PORT="8080"
IMAGE="ghcr.io/ggml-org/llama.cpp:server-cuda"
MODEL_FILE="surya-2.5-Q8_0.gguf"
MMPROJ_FILE="surya-2.5-mmproj.gguf"
ALIAS="datalab-to/surya-ocr-2.5"

for f in "$MODEL_FILE" "$MMPROJ_FILE"; do
  if [ ! -s "$MODELS_DIR/$f" ]; then
    echo "ERROR: missing model file $MODELS_DIR/$f" >&2
    exit 1
  fi
done

if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "[1/2] llama.cpp server already running ($CONTAINER)"
else
  echo "[1/2] starting llama.cpp server ($CONTAINER) on 127.0.0.1:$PORT"
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  docker run -d --name "$CONTAINER" \
    --gpus all \
    -p "127.0.0.1:${PORT}:8080" \
    -v "$MODELS_DIR":/models:ro \
    "$IMAGE" \
    -m "/models/$MODEL_FILE" \
    --mmproj "/models/$MMPROJ_FILE" \
    -ngl 99 \
    --host 0.0.0.0 --port 8080 \
    --parallel 1 --ctx-size 16384 \
    --image-min-tokens 1024 \
    --alias "$ALIAS" \
    --jinja --special >/dev/null

  echo "      waiting for /health ..."
  for _ in $(seq 1 150); do
    if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
      echo "      server healthy"
      break
    fi
    sleep 2
  done
  if ! curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "ERROR: server did not become healthy; last logs:" >&2
    docker logs --tail 40 "$CONTAINER" >&2 || true
    exit 1
  fi
fi

echo "[2/2] running pipeline: python main.py"
cd "$HERE"
exec ./venv_general_ocr/bin/python main.py
