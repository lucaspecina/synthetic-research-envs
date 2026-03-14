#!/bin/bash
# Serve a model with vLLM (OpenAI-compatible API).
#
# Run this in WSL2 (or native Linux with GPU).
#
# Usage:
#   # First time setup:
#   bash scripts/serve_model.sh --setup
#
#   # Serve Qwen 0.5B (default, fits in 12GB VRAM):
#   bash scripts/serve_model.sh
#
#   # Serve a different model:
#   bash scripts/serve_model.sh --model Qwen/Qwen2.5-1.5B-Instruct
#
#   # Serve on a different port:
#   bash scripts/serve_model.sh --port 8080
#
# After starting, the model is available at:
#   http://localhost:8000/v1  (OpenAI-compatible API)
#
# Test with:
#   curl http://localhost:8000/v1/models

set -e

MODEL="${MODEL:-Qwen/Qwen2.5-0.5B-Instruct}"
PORT="${PORT:-8000}"
GPU_MEM_UTILIZATION="${GPU_MEM_UTILIZATION:-0.85}"
VENV_DIR="$HOME/.venvs/vllm"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --setup)    SETUP=1; shift ;;
        --model)    MODEL="$2"; shift 2 ;;
        --port)     PORT="$2"; shift 2 ;;
        --gpu-mem)  GPU_MEM_UTILIZATION="$2"; shift 2 ;;
        *)          echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# --- Setup (first time) ---
if [[ -n "$SETUP" ]]; then
    echo "=== Setting up vLLM environment ==="

    # Create venv
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"

    # Install vLLM
    pip install --upgrade pip
    pip install vllm

    echo ""
    echo "=== Setup complete ==="
    echo "Run again without --setup to start the server."
    exit 0
fi

# --- Start server ---
if [[ ! -d "$VENV_DIR" ]]; then
    echo "vLLM not installed. Run: bash scripts/serve_model.sh --setup"
    exit 1
fi

source "$VENV_DIR/bin/activate"

echo "=== Starting vLLM server ==="
echo "Model: $MODEL"
echo "Port: $PORT"
echo "GPU memory utilization: $GPU_MEM_UTILIZATION"
echo ""
echo "API will be available at: http://localhost:$PORT/v1"
echo "Press Ctrl+C to stop."
echo ""

python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --port "$PORT" \
    --gpu-memory-utilization "$GPU_MEM_UTILIZATION" \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    --max-model-len 4096 \
    --trust-remote-code
