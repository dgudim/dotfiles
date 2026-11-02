#!/bin/sh
# Re-download the llama.cpp models from Hugging Face
set -eu

cd /mnt/sata_500/llama.cpp

for url in \
  https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q5_K_M.gguf \
  https://huggingface.co/acon96/Home-3B-v3-GGUF/resolve/main/Home-3B-v3.q5_k_m.gguf \
  https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF/resolve/main/LFM2.5-1.2B-Instruct-Q6_K.gguf \
  https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF/resolve/main/LFM2.5-1.2B-Instruct-Q4_K_M.gguf
do
  file=$(basename "$url")
  [ -f "$file" ] && { echo "exists $file"; continue; }
  curl -fL -C - -o "$file.part" "$url"
  mv "$file.part" "$file"
done

