"""Offline retrieval evaluation for Scrubless.

Reproduces the product's indexing + search math (same CLIP weights, same frame
sampling, same transcript windowing, cosine over L2-normalised vectors) in a
standalone script with its own cache, then scores several ranking conditions
against a hand-labelled query set.

    .venv/bin/python eval/run_eval.py --selftest      # metric unit checks
    .venv/bin/python eval/run_eval.py index           # frames + audio + Whisper + CLIP (cached)
    .venv/bin/python eval/run_eval.py sheets          # contact sheets for labelling
    .venv/bin/python eval/run_eval.py score           # run all conditions, write results/

Nothing here touches the product's ChromaDB under storage/.
"""
import argparse
import json
import math
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
WORK = HERE / "work"
RESULTS = HERE / "results"

VIDEOS = {
    "tos": {
        "file": "tears_of_steel.mov",
        "title": "Tears of Steel (Blender Foundation, 2012)",
        "license": "CC BY 3.0",
        "url": "https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov",
    },
    "bbb": {
        "file": "big_buck_bunny.mp4",
        "title": "Big Buck Bunny (Blender Foundation, 2008)",
        "license": "CC BY 3.0",
        "url": "https://archive.org/download/BigBuckBunny_124/Content/big_buck_bunny_720p_surround.mp4",
    },
    "nasa": {
        "file": "nasa_kazakhstan.mp4",
        "title": "Dan Goes to Kazakhstan (NASA Johnson, 2016)",
        "license": "CC0 / public domain",
        "url": "https://archive.org/download/TheSpaceProgram/Dan%20Goes%20to%20Kazakhstan_ArchiveOrg.mp4",
    },
}
INTERVALS = (5, 2)  # seconds; 5 is the shipped default, 2 is the ablation
TOLERANCE = 5.0  # seconds of slack around a ground-truth interval
TOP_K = 10  # the product returns 10 results


# --------------------------------------------------------------------------
# Metrics (pure functions; covered by --selftest)
# --------------------------------------------------------------------------
def is_hit(t, intervals, tol=TOLERANCE):
    """A returned timestamp t hits if it lies within tol of any [s, e]."""
    return any(s - tol <= t <= e + tol for s, e in intervals)


def first_hit_rank(timestamps, intervals, tol=TOLERANCE):
    """1-based rank of the first hit in a ranked list, or None."""
    for i, t in enumerate(timestamps, 1):
        if is_hit(t, intervals, tol):
            return i
    return None


def summarize(ranks):
    """Recall@1/5/10 and MRR from a list of first-hit ranks (None = miss)."""
    n = len(ranks)
    if n == 0:
        return {"n": 0, "r1": 0.0, "r5": 0.0, "r10": 0.0, "mrr": 0.0}
    return {
        "n": n,
        "r1": sum(1 for r in ranks if r is not None and r <= 1) / n,
        "r5": sum(1 for r in ranks if r is not None and r <= 5) / n,
        "r10": sum(1 for r in ranks if r is not None and r <= 10) / n,
        "mrr": sum(1.0 / r for r in ranks if r is not None) / n,
    }


def rrf(rankings, k=60):
    """Reciprocal-rank fusion of several ranked id lists -> fused ranked ids."""
    score = Counter()
    for ranking in rankings:
        for rank, item in enumerate(ranking, 1):
            score[item] += 1.0 / (k + rank)
    return [item for item, _ in score.most_common()]


# --------------------------------------------------------------------------
# BM25 (small, dependency-free)
# --------------------------------------------------------------------------
_TOKEN = re.compile(r"[a-z0-9']+")


def tokenize(text):
    return _TOKEN.findall(text.lower())


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = [tokenize(d) for d in docs]
        self.k1, self.b = k1, b
        self.n = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / max(self.n, 1)
        self.df = Counter()
        for d in self.docs:
            self.df.update(set(d))
        self.tf = [Counter(d) for d in self.docs]

    def idf(self, term):
        df = self.df.get(term, 0)
        return math.log((self.n - df + 0.5) / (df + 0.5) + 1.0)

    def max_score(self, query):
        """Score of a document of average length containing every query term
        exactly once (tf=1, dl=avgdl => per-term score == idf). Used as the
        coverage normaliser: score/max_score ~ idf-weighted fraction of the
        query's terms present in the window."""
        return sum(self.idf(t) for t in tokenize(query))

    def score(self, query):
        q = tokenize(query)
        out = []
        for tf, d in zip(self.tf, self.docs):
            dl = len(d)
            s = 0.0
            for term in q:
                f = tf.get(term, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                s += self.idf(term) * f * (self.k1 + 1) / denom
            out.append(s)
        return out


# --------------------------------------------------------------------------
# Indexing (mirrors indexing.py; cached under eval/work/)
# --------------------------------------------------------------------------
def run(cmd):
    subprocess.run(cmd, check=True)


def extract_frames(source, frames_dir, interval):
    frames_dir.mkdir(parents=True, exist_ok=True)
    if not any(frames_dir.glob("frame_*.jpg")):
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
             "-vf", "fps=1/%d" % interval, "-q:v", "2", str(frames_dir / "frame_%04d.jpg")])
    return sorted(frames_dir.glob("frame_*.jpg"))


def extract_audio(source, audio_path):
    if not audio_path.exists():
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
             "-vn", "-acodec", "libmp3lame", "-ar", "16000", "-ac", "1", "-b:a", "48k",
             str(audio_path)])


def transcribe(audio_path, cache):
    if cache.exists():
        return json.loads(cache.read_text())
    from dotenv import load_dotenv
    import os
    load_dotenv(ROOT / ".env")
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    t0 = time.time()
    with open(audio_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            model="whisper-1", file=f, response_format="verbose_json")
    segs = [{"start": s.start, "end": s.end, "text": s.text or ""} for s in (resp.segments or [])]
    cache.write_text(json.dumps({"seconds": time.time() - t0, "segments": segs}, indent=1))
    return json.loads(cache.read_text())


def transcript_for_window(transcript, start, end):
    parts = [t["text"].strip() for t in transcript
             if t["start"] < end and t["end"] > start and t["text"].strip()]
    return " ".join(parts)


_clip = None


def clip():
    """Load OpenCLIP ViT-B/32 once (same weights as embeddings.py)."""
    global _clip
    if _clip is None:
        import open_clip
        import torch
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k")
        model.eval()
        _clip = (model, preprocess, open_clip.get_tokenizer("ViT-B-32"), torch)
    return _clip


def embed_images(paths):
    import numpy as np
    from PIL import Image
    model, preprocess, _, torch = clip()
    out = []
    with torch.no_grad():
        for i in range(0, len(paths), 32):
            batch = torch.stack([preprocess(Image.open(p).convert("RGB")) for p in paths[i:i + 32]])
            v = model.encode_image(batch)
            v /= v.norm(dim=-1, keepdim=True)
            out.append(v.numpy())
    return np.concatenate(out)


def embed_texts(texts):
    import numpy as np
    model, _, tok, torch = clip()
    out = []
    with torch.no_grad():
        for i in range(0, len(texts), 64):
            v = model.encode_text(tok(texts[i:i + 64]))
            v /= v.norm(dim=-1, keepdim=True)
            out.append(v.numpy())
    return np.concatenate(out)


def index_video(vid, interval, need_text=True):
    """Return dict(timestamps, image_vecs, texts, text_vecs, timings).

    Visual and transcript halves are cached separately so frames + CLIP can run
    before an OPENAI_API_KEY is available; need_text=False skips the transcript.
    """
    import numpy as np
    meta = VIDEOS[vid]
    source = DATA / meta["file"]
    wdir = WORK / vid
    wdir.mkdir(parents=True, exist_ok=True)
    vis_cache = wdir / ("visual_%ds.npz" % interval)
    txt_cache = wdir / ("text_%ds.npz" % interval)
    timings_path = wdir / ("timings_%ds.json" % interval)
    timings = json.loads(timings_path.read_text()) if timings_path.exists() else {}

    if not vis_cache.exists():
        t0 = time.time()
        frames = extract_frames(source, wdir / ("frames_%ds" % interval), interval)
        timings["ffmpeg_frames_s"] = time.time() - t0
        t0 = time.time()
        image_vecs = embed_images(frames)
        timings["clip_image_s"] = time.time() - t0
        timings["n_frames"] = len(frames)
        timings["duration_s"] = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(source)]))
        from PIL import Image
        pixel_std = np.array([np.asarray(Image.open(f).convert("L")).std() for f in frames])
        np.savez(vis_cache, timestamps=np.array([i * interval for i in range(len(frames))], dtype=float),
                 image_vecs=image_vecs, pixel_std=pixel_std)
        timings_path.write_text(json.dumps(timings, indent=1))
    z = np.load(vis_cache)
    if "pixel_std" not in z.files:  # older cache: compute the mask now
        from PIL import Image
        frames = sorted((wdir / ("frames_%ds" % interval)).glob("frame_*.jpg"))
        pixel_std = np.array([np.asarray(Image.open(f).convert("L")).std() for f in frames])
        np.savez(vis_cache, timestamps=z["timestamps"], image_vecs=z["image_vecs"], pixel_std=pixel_std)
        z = np.load(vis_cache)
    out = {"timestamps": z["timestamps"], "image_vecs": z["image_vecs"], "pixel_std": z["pixel_std"],
           "timings": timings}

    if need_text and not txt_cache.exists():
        t0 = time.time()
        extract_audio(source, wdir / "audio.mp3")
        timings["ffmpeg_audio_s"] = time.time() - t0
        tr = transcribe(wdir / "audio.mp3", wdir / "transcript.json")
        timings["whisper_s"] = tr["seconds"]
        texts = [transcript_for_window(tr["segments"], t, t + interval) for t in out["timestamps"]]
        t0 = time.time()
        text_vecs = embed_texts([t if t else " " for t in texts])
        timings["clip_text_s"] = time.time() - t0
        np.savez(txt_cache, texts=np.array(texts, dtype=object), text_vecs=text_vecs)
        timings_path.write_text(json.dumps(timings, indent=1))
    if txt_cache.exists():
        z = np.load(txt_cache, allow_pickle=True)
        out["texts"], out["text_vecs"] = list(z["texts"]), z["text_vecs"]
    return out


# --------------------------------------------------------------------------
# Contact sheets for ground-truth labelling
# --------------------------------------------------------------------------
def make_sheets(vid, interval=5, cols=6, rows=5, tile_w=320):
    """Tile the frames into timestamped contact sheets (cols*rows per sheet)."""
    from PIL import Image, ImageDraw, ImageFont
    wdir = WORK / vid
    frames = sorted((wdir / ("frames_%ds" % interval)).glob("frame_*.jpg"))
    out = wdir / "sheets"
    out.mkdir(exist_ok=True)
    per = cols * rows
    w0, h0 = Image.open(frames[0]).size
    tile_h = round(h0 * tile_w / w0)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except OSError:
        font = ImageFont.load_default()
    for s in range(0, len(frames), per):
        chunk = frames[s:s + per]
        sheet = Image.new("RGB", (cols * tile_w, rows * tile_h), "black")
        draw = ImageDraw.Draw(sheet)
        for j, path in enumerate(chunk):
            t = (s + j) * interval
            x, y = (j % cols) * tile_w, (j // cols) * tile_h
            sheet.paste(Image.open(path).convert("RGB").resize((tile_w, tile_h)), (x, y))
            label = "%d:%02d" % (t // 60, t % 60)
            draw.rectangle([x, y, x + 64, y + 26], fill=(0, 0, 0))
            draw.text((x + 4, y + 2), label, fill=(255, 230, 0), font=font)
        sheet.save(out / ("sheet_%02d.jpg" % (s // per)), quality=85)
    print(vid, "->", out, len(list(out.glob("*.jpg"))), "sheets")


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
BLANK_STD = 5.0  # grey-level std below which a frame is treated as blank


def rank_visual(idx, qvec, drop_blank=False):
    import numpy as np
    sims = idx["image_vecs"] @ qvec
    if drop_blank:
        sims = np.where(idx["pixel_std"] < BLANK_STD, -np.inf, sims)
    return list(np.argsort(-sims))


def rank_text_clip(idx, qvec):
    import numpy as np
    has_text = np.array([bool(t) for t in idx["texts"]])
    sims = idx["text_vecs"] @ qvec
    sims = np.where(has_text, sims, -np.inf)
    order = [i for i in np.argsort(-sims) if has_text[i]]
    return order


def temporal_nms(order, timestamps, window):
    """Drop any result within `window` seconds of a higher-ranked result."""
    kept = []
    for i in order:
        if all(abs(timestamps[i] - timestamps[j]) > window for j in kept):
            kept.append(i)
    return kept


def rank_combsum_cov(idx, bm25, qvec, query, alpha, drop_blank=False):
    """As rank_combsum, but BM25 is normalised by its query-dependent upper
    bound (query coverage) instead of its observed maximum, so a weak partial
    match stays weak instead of being inflated to 1.0."""
    import numpy as np
    vis = idx["image_vecs"] @ qvec
    vis = (vis - vis.min()) / (vis.max() - vis.min() + 1e-9)
    bm = np.array(bm25.score(query)) / max(bm25.max_score(query), 1e-9)
    fused = alpha * vis + (1 - alpha) * bm
    if drop_blank:
        fused = np.where(idx["pixel_std"] < BLANK_STD, -np.inf, fused)
    return list(np.argsort(-fused))


def rank_combsum(idx, bm25, qvec, query, alpha):
    """Convex combination of min-max-normalised cosine and BM25 scores.

    BM25 is normalised by its own maximum for the query, so it contributes
    nothing when the transcript has no lexical match and dominates when it has
    a strong one; alpha weights the visual channel.
    """
    import numpy as np
    vis = idx["image_vecs"] @ qvec
    vis = (vis - vis.min()) / (vis.max() - vis.min() + 1e-9)
    bm = np.array(bm25.score(query))
    bm = bm / bm.max() if bm.max() > 0 else bm
    return list(np.argsort(-(alpha * vis + (1 - alpha) * bm)))


def rank_bm25(bm25, query):
    import numpy as np
    scores = np.array(bm25.score(query))
    order = [int(i) for i in np.argsort(-scores) if scores[i] > 0]
    return order


def score(queries_path=HERE / "queries.json", need_text=True):
    import numpy as np
    queries = json.loads(queries_path.read_text())
    RESULTS.mkdir(exist_ok=True)

    indices = {(v, i): index_video(v, i, need_text=need_text) for v in VIDEOS for i in INTERVALS}
    have_text = all("texts" in idx for idx in indices.values())
    bm25s = {k: BM25([t or "" for t in idx["texts"]]) for k, idx in indices.items()} if have_text else {}

    # Query embeddings once (also measures text-encode latency).
    qvecs = embed_texts([q["query"] for q in queries])
    embed_texts(["warm up"])
    lat = []
    for q in queries[:20]:
        t0 = time.perf_counter()
        embed_texts([q["query"]])
        lat.append((time.perf_counter() - t0) * 1000)
    embed_latency_ms = float(np.median(lat))

    conditions = {
        "visual_5s": ("visual", 5),
        "visual_2s": ("visual", 2),
        "transcript_clip_5s": ("text_clip", 5),
        "transcript_bm25_5s": ("bm25", 5),
        "hybrid_rrf_5s": ("hybrid", 5),
        "hybrid_rrf_2s": ("hybrid", 2),
        "visual_2s_nms5": ("visual_nms", 2),
        "hybrid_combsum_5s": ("combsum", 5),
        "hybrid_combsum_2s_nms5": ("combsum_nms", 2),
        "hybrid_coverage_5s": ("coverage", 5),
        "hybrid_coverage_2s_nms5": ("coverage_nms", 2),
        "visual_5s_noblank": ("visual_noblank", 5),
        "hybrid_coverage_5s_noblank": ("coverage_noblank", 5),
    }
    ALPHA = 0.5
    if not have_text:
        conditions = {c: v for c, v in conditions.items() if v[0] in ("visual", "visual_nms", "visual_noblank")}
    per_query = []
    search_latency = []
    for q, qvec in zip(queries, qvecs):
        row = {"id": q["id"], "video": q["video"], "type": q["type"], "query": q["query"],
               "paraphrase": q.get("paraphrase", False)}
        for cname, (kind, interval) in conditions.items():
            idx = indices[(q["video"], interval)]
            t0 = time.perf_counter()
            if kind == "visual":
                order = rank_visual(idx, qvec)
            elif kind == "text_clip":
                order = rank_text_clip(idx, qvec)
            elif kind == "bm25":
                order = rank_bm25(bm25s[(q["video"], interval)], q["query"])
            elif kind == "visual_nms":
                order = temporal_nms(rank_visual(idx, qvec), idx["timestamps"], 5)
            elif kind == "combsum":
                order = rank_combsum(idx, bm25s[(q["video"], interval)], qvec, q["query"], ALPHA)
            elif kind == "visual_noblank":
                order = rank_visual(idx, qvec, drop_blank=True)
            elif kind == "coverage_noblank":
                order = rank_combsum_cov(idx, bm25s[(q["video"], interval)], qvec, q["query"], ALPHA, drop_blank=True)
            elif kind == "coverage":
                order = rank_combsum_cov(idx, bm25s[(q["video"], interval)], qvec, q["query"], ALPHA)
            elif kind == "coverage_nms":
                order = temporal_nms(rank_combsum_cov(idx, bm25s[(q["video"], interval)], qvec, q["query"], ALPHA),
                                     idx["timestamps"], 5)
            elif kind == "combsum_nms":
                order = temporal_nms(rank_combsum(idx, bm25s[(q["video"], interval)], qvec, q["query"], ALPHA),
                                     idx["timestamps"], 5)
            else:
                order = rrf([rank_visual(idx, qvec)[:50],
                             rank_bm25(bm25s[(q["video"], interval)], q["query"])[:50]])
            dt = (time.perf_counter() - t0) * 1000
            if cname == "visual_5s":
                search_latency.append(dt)
            ts = [float(idx["timestamps"][i]) for i in order[:TOP_K]]
            row[cname] = {"rank": first_hit_rank(ts, q["gt"]), "top": ts[:5]}
        per_query.append(row)

    def agg(filter_fn):
        out = {}
        for cname in conditions:
            ranks = [r[cname]["rank"] for r in per_query if filter_fn(r)]
            out[cname] = summarize(ranks)
        return out

    sweep = {}
    if have_text:
        for fname, fn in (("combsum", rank_combsum), ("coverage", rank_combsum_cov)):
            for alpha in (0.3, 0.4, 0.5, 0.6, 0.7):
                ranks = {"all": [], "visual": [], "spoken": []}
                for q, qvec in zip(queries, qvecs):
                    idx = indices[(q["video"], 5)]
                    order = fn(idx, bm25s[(q["video"], 5)], qvec, q["query"], alpha)
                    r = first_hit_rank([float(idx["timestamps"][i]) for i in order[:TOP_K]], q["gt"])
                    ranks["all"].append(r)
                    ranks[q["type"]].append(r)
                sweep["%s a=%s" % (fname, alpha)] = {k: summarize(v) for k, v in ranks.items()}

    lovo = {}
    if have_text:
        alphas = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
        per = {}  # (video, alpha) -> list of ranks
        for q, qvec in zip(queries, qvecs):
            idx = indices[(q["video"], 5)]
            for alpha in alphas:
                order = rank_combsum_cov(idx, bm25s[(q["video"], 5)], qvec, q["query"], alpha)
                per.setdefault((q["video"], alpha), []).append(
                    first_hit_rank([float(idx["timestamps"][i]) for i in order[:TOP_K]], q["gt"]))
        held_ranks = []
        for held in VIDEOS:
            best = max(alphas, key=lambda a: summarize(
                [r for v in VIDEOS if v != held for r in per[(v, a)]])["mrr"])
            lovo[held] = {"alpha": best, **summarize(per[(held, best)])}
            held_ranks += per[(held, best)]
        lovo["pooled"] = summarize(held_ranks)

    summary = {
        "alpha_sweep_combsum_5s": sweep,
        "lovo_coverage_5s": lovo,
        "all": agg(lambda r: True),
        "by_type": {t: agg(lambda r, t=t: r["type"] == t) for t in sorted({q["type"] for q in queries})}
        | {"spoken/verbatim": agg(lambda r: r["type"] == "spoken" and not r.get("paraphrase")),
           "spoken/paraphrase": agg(lambda r: r["type"] == "spoken" and r.get("paraphrase"))},
        "by_video": {v: agg(lambda r, v=v: r["video"] == v) for v in VIDEOS},
        "latency_ms": {
            "query_embed_p50": embed_latency_ms,
            "visual_rank_p50": float(np.median(search_latency)),
        },
        "indexing": {"%s_%ds" % (v, i): idx["timings"] for (v, i), idx in indices.items()},
        "tolerance_s": TOLERANCE,
        "n_queries": len(queries),
    }
    (RESULTS / "per_query.json").write_text(json.dumps(per_query, indent=1))
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=1))
    print(render_tables(summary))
    (RESULTS / "summary.md").write_text(render_tables(summary))


def render_tables(summary):
    def table(title, block):
        lines = ["### " + title, "", "| condition | n | R@1 | R@5 | R@10 | MRR |", "|---|---|---|---|---|---|"]
        for c, m in block.items():
            lines.append("| %s | %d | %.2f | %.2f | %.2f | %.3f |" % (c, m["n"], m["r1"], m["r5"], m["r10"], m["mrr"]))
        return "\n".join(lines) + "\n"
    out = [table("All queries", summary["all"])]
    for t, b in summary["by_type"].items():
        out.append(table("Query type: " + t, b))
    for v, b in summary["by_video"].items():
        out.append(table("Video: " + v, b))
    if summary.get("alpha_sweep_combsum_5s"):
        out.append("### Fusion alpha sweep (5 s index)\n\n| fusion / alpha | all R@1 | all MRR | visual R@1 | spoken R@1 |\n|---|---|---|---|---|")
        for a, b in summary["alpha_sweep_combsum_5s"].items():
            out.append("| %s | %.2f | %.3f | %.2f | %.2f |" % (a, b["all"]["r1"], b["all"]["mrr"], b["visual"]["r1"], b["spoken"]["r1"]))
        out.append("")
    if summary.get("lovo_coverage_5s"):
        out.append("### Leave-one-video-out alpha selection (coverage fusion, 5 s)\n\n| held-out | alpha chosen on others | n | R@1 | R@5 | R@10 | MRR |\n|---|---|---|---|---|---|---|")
        for v, m in summary["lovo_coverage_5s"].items():
            out.append("| %s | %s | %d | %.2f | %.2f | %.2f | %.3f |" % (v, m.get("alpha", "-"), m["n"], m["r1"], m["r5"], m["r10"], m["mrr"]))
        out.append("")
    out.append("Latency: " + json.dumps(summary["latency_ms"]))
    out.append("Indexing: " + json.dumps(summary["indexing"], indent=1))
    return "\n".join(out)


# --------------------------------------------------------------------------
def selftest():
    assert is_hit(10, [[8, 12]]) and is_hit(4, [[8, 12]]) and not is_hit(2, [[8, 12]])
    assert first_hit_rank([0, 20, 10], [[9, 11]]) == 3
    assert first_hit_rank([0, 50], [[9, 11]]) is None
    s = summarize([1, None, 3, 7])
    assert s == {"n": 4, "r1": 0.25, "r5": 0.5, "r10": 0.75, "mrr": (1 + 1 / 3 + 1 / 7) / 4}
    assert rrf([["a", "b", "c"], ["c", "a"]])[0] == "a"
    bm = BM25(["the rabbit sleeps", "a rocket launch", "rocket launch window"])
    assert rank_bm25(bm, "launch window")[0] == 2
    assert rank_bm25(bm, "penguin") == []
    print("selftest ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="score", choices=["index", "sheets", "score"])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--video", choices=list(VIDEOS), default=None)
    ap.add_argument("--no-text", action="store_true", help="index frames only (no Whisper)")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        sys.exit(0)
    vids = [a.video] if a.video else list(VIDEOS)
    if a.cmd == "index":
        for v in vids:
            for i in INTERVALS:
                idx = index_video(v, i, need_text=not a.no_text)
                print(v, i, "frames:", int(idx["timings"]["n_frames"]), idx["timings"])
    elif a.cmd == "sheets":
        for v in vids:
            make_sheets(v)
    else:
        score(need_text=not a.no_text)
