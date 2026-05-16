"""Scrubless CLIP sidecar.

Lightweight FastAPI service wrapping OpenCLIP ViT-B/32. The Go backend calls
this over HTTP to turn frames and query text into 768-dim embeddings.
"""

import base64
import io
import logging

import open_clip
import torch
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("clip-sidecar")

MODEL_NAME = "ViT-B-32"
PRETRAINED = "laion2b_s34b_b79k"
EMBED_DIM = 512  # ViT-B-32 produces 512-dim embeddings — ~3x faster than ViT-L/14

app = FastAPI(title="Scrubless CLIP Sidecar")

device = "cuda" if torch.cuda.is_available() else "cpu"
log.info("loading %s (%s) on %s", MODEL_NAME, PRETRAINED, device)
model, _, preprocess = open_clip.create_model_and_transforms(
    MODEL_NAME, pretrained=PRETRAINED
)
tokenizer = open_clip.get_tokenizer(MODEL_NAME)
model.eval()
model.to(device)
log.info("model ready")


class ImageRequest(BaseModel):
    image_base64: str


class TextRequest(BaseModel):
    text: str


class BatchRequest(BaseModel):
    images: list[str]


def _decode(b64: str) -> Image.Image:
    try:
        raw = base64.b64decode(b64)
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"invalid image: {exc}") from exc


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME, "dim": EMBED_DIM, "device": device}


@app.post("/embed/image")
async def embed_image(req: ImageRequest):
    img = preprocess(_decode(req.image_base64)).unsqueeze(0).to(device)
    with torch.no_grad():
        emb = model.encode_image(img)
        emb /= emb.norm(dim=-1, keepdim=True)
    return {"embedding": emb[0].cpu().tolist()}


@app.post("/embed/text")
async def embed_text(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is empty")
    tokens = tokenizer([req.text]).to(device)
    with torch.no_grad():
        emb = model.encode_text(tokens)
        emb /= emb.norm(dim=-1, keepdim=True)
    return {"embedding": emb[0].cpu().tolist()}


@app.post("/embed/batch")
async def embed_batch(req: BatchRequest):
    if not req.images:
        raise HTTPException(status_code=400, detail="images list is empty")
    tensors = [preprocess(_decode(b64)) for b64 in req.images]
    batch = torch.stack(tensors).to(device)
    with torch.no_grad():
        embs = model.encode_image(batch)
        embs /= embs.norm(dim=-1, keepdim=True)
    return {"embeddings": embs.cpu().tolist()}
