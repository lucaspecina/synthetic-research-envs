#!/bin/bash
# Serve a model with vLLM (OpenAI-compatible API).
#
# Run this on a machine with a GPU (H100, A100, etc.) or in WSL2.
#
# Usage:
#   # First time setup:
#   bash scripts/serve_model.sh --setup
#
#   # Serve Qwen3-8B (default for thesis benchmarks):
#   bash scripts/serve_model.sh
#
#   # Serve a different model:
#   bash scripts/serve_model.sh --model Qwen/Qwen2.5-1.5B-Instruct
#
#   # Serve on a different port:
#   bash scripts/serve_model.sh --port 8080
#
# After starting, the model is available at:
#   http://localhost:8000/v1  (OpenAI-compatible Chat Completions API)
#
# Run benchmarks against it:
#   python scripts/run_benchmark.py --benchmark qrdata --model qwen3-8b \
#       --backend vllm --base-url http://localhost:8000/v1 --api-key none \
#       --with-tools --subset dev
#
# Test with:
#   curl http://localhost:8000/v1/models

set -e

MODEL="${MODEL:-Qwen/Qwen3-8B}"
PORT="${PORT:-8000}"
GPU_MEM_UTILIZATION="${GPU_MEM_UTILIZATION:-0.90}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-16384}"
VENV_DIR="$HOME/.venvs/vllm"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --setup)    SETUP=1; shift ;;
        --model)    MODEL="$2"; shift 2 ;;
        --port)     PORT="$2"; shift 2 ;;
        --gpu-mem)  GPU_MEM_UTILIZATION="$2"; shift 2 ;;
        --max-len)  MAX_MODEL_LEN="$2"; shift 2 ;;
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
echo "Max model length: $MAX_MODEL_LEN"
echo ""
echo "API will be available at: http://localhost:$PORT/v1"
echo "Press Ctrl+C to stop."
echo ""

python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --port "$PORT" \
    --gpu-memory-utilization "$GPU_MEM_UTILIZATION" \
    --max-model-len "$MAX_MODEL_LEN" \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    --trust-remote-code
