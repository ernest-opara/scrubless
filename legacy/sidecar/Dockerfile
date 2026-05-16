FROM python:3.11-slim

WORKDIR /app

# Install CPU-only torch first so the layer caches independently of app code.
COPY requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

COPY server.py .

# Pre-download the ViT-B-32 weights into the image so container startup
# doesn't block on a download. open_clip caches under /root/.cache.
RUN python -c "import open_clip; open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')"

EXPOSE 8100

# Healthcheck mirrors the GET /health endpoint. Long start-period covers
# loading the large model into memory on boot.
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8100"]
