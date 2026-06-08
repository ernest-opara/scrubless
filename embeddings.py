"""CLIP model + ChromaDB collection + the three Claude calls (frame describe,
video summary, single embedding helpers). Importing this module loads CLIP."""
import base64
import json

import chromadb
import open_clip
import torch
from PIL import Image

from config import ANTHROPIC_API_KEY, STORAGE

print("[scrubless] loading OpenCLIP ViT-B-32 …")
clip_model, _, clip_preprocess = open_clip.create_model_and_transforms(
    "ViT-B-32", pretrained="laion2b_s34b_b79k"
)
clip_tokenizer = open_clip.get_tokenizer("ViT-B-32")
clip_model.eval()
print("[scrubless] CLIP ready")

chroma = chromadb.PersistentClient(path=str(STORAGE / "chroma"))
segments = chroma.get_or_create_collection(
    "segments", metadata={"hnsw:space": "cosine"}
)


def embed_image(path):
    """Return the CLIP embedding of an image file as a list of floats."""
    image = clip_preprocess(Image.open(path).convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        vec = clip_model.encode_image(image)
        vec /= vec.norm(dim=-1, keepdim=True)
    return vec[0].tolist()


def embed_text(text):
    """Return the CLIP embedding of a text query as a list of floats."""
    tokens = clip_tokenizer([text])
    with torch.no_grad():
        vec = clip_model.encode_text(tokens)
        vec /= vec.norm(dim=-1, keepdim=True)
    return vec[0].tolist()


def describe_frame(frame_path):
    """Return a 1-2 sentence Claude Vision description of a frame, or ''."""
    if not ANTHROPIC_API_KEY:
        return ""
    from anthropic import Anthropic

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    with open(frame_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode()
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": data,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Describe what's happening in this frame in 1-2 sentences.",
                        },
                    ],
                }
            ],
        )
        return "".join(b.text for b in msg.content if b.type == "text").strip()
    except Exception as exc:  # noqa: BLE001 — enrichment is best-effort
        print("[scrubless] enrich failed:", exc)
        return ""


def summarize_video(transcript):
    """Return {"summary", "chapters"} from a transcript via Claude, or {}.

    Best-effort: needs an Anthropic key and a transcript (so visual-only videos
    just get no chapters).
    """
    if not ANTHROPIC_API_KEY or not transcript:
        return {}
    lines = []
    for t in transcript:
        txt = (t.get("text") or "").strip()
        if txt:
            lines.append("[%ds] %s" % (int(t["start"]), txt))
    if not lines:
        return {}
    body = "\n".join(lines)[:12000]  # cap input tokens
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt = (
            "Below is a timestamped transcript of a video.\n\n"
            + body
            + '\n\nReturn ONLY a JSON object: {"summary": "<2-3 sentence overview>", '
            '"chapters": [{"start": <seconds int>, "title": "<short title>"}]} '
            "with 4-8 chapters in chronological order. No markdown, just JSON."
        )
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        out = "".join(b.text for b in msg.content if b.type == "text")
        i, j = out.find("{"), out.rfind("}")
        if i < 0 or j <= i:
            return {}
        data = json.loads(out[i : j + 1])
        chapters = []
        for c in data.get("chapters", []):
            try:
                chapters.append({"start": int(c["start"]), "title": str(c["title"])[:120]})
            except Exception:  # noqa: BLE001 — skip a malformed chapter
                continue
        return {"summary": str(data.get("summary", ""))[:1500], "chapters": chapters}
    except Exception as exc:  # noqa: BLE001
        print("[scrubless] summarize failed:", exc)
        return {}
