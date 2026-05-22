#!/bin/bash
# Run arXiv daily paper recommendation with GLM API
# Usage: source .env (or export env vars), then bash run_glm.sh

# Load .env if exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Validate required env vars
for var in GLM_API_KEY SMTP_SERVER SMTP_SENDER SMTP_RECEIVER SMTP_PASSWORD; do
    if [ -z "${!var}" ]; then
        echo "Error: $var is not set. Please set it in .env or export it."
        exit 1
    fi
done

python main.py \
  --categories cs.AI cs.CL cs.LG cs.IR \
  --provider OpenAI \
  --model "${GLM_MODEL:-glm-4.5-air}" \
  --base_url "https://open.bigmodel.cn/api/paas/v4/" \
  --api_key "$GLM_API_KEY" \
  --smtp_server "$SMTP_SERVER" \
  --smtp_port "${SMTP_PORT:-465}" \
  --sender "$SMTP_SENDER" \
  --receiver "$SMTP_RECEIVER" \
  --sender_password "$SMTP_PASSWORD" \
  --temperature 0.3 \
  --num_workers 4 \
  --title "Daily arXiv Papers" \
  --save
