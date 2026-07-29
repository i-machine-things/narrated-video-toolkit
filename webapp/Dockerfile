FROM debian:bookworm-slim

# Debian, not Alpine - musl libc can't reliably run the glibc-targeted ML
# wheels (torch/onnxruntime) this app depends on. Learned that the hard way.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-noto-core \
        python3 \
        python3-pip \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --break-system-packages --no-cache-dir \
        torch torchaudio torchcodec --index-url https://download.pytorch.org/whl/cpu

COPY webapp/requirements.txt /app/requirements.txt
RUN pip install --break-system-packages --no-cache-dir -r /app/requirements.txt

COPY app/ /app/

ENV DATA_DIR=/data
VOLUME ["/data", "/root/.cache/huggingface"]

EXPOSE 8080
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
