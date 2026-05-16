# Scrubless — Project Spec & Build Plan

## What This Is

Scrubless is a semantic video search tool for creators. Upload a video, then find any moment by describing it in natural language. "Find the part where Tunde starts laughing at the restaurant" → jumps you right there.

## Why It Matters

- **Twelve Labs** proved enterprise video search ($107M raised) but has no consumer product
- **Opus Clip** ($79M) auto-picks clips FOR you — you can't search your own footage
- **Descript/Vizard** only search transcripts — if nobody said "sunset," you'll never find the sunset shot
- **The gap:** No tool lets creators search their own raw footage with natural language visual + audio understanding

## Architecture — Hybrid CLIP + Claude (Cost-Optimized)

Two-tier AI system that keeps indexing cheap and reserves expensive LLM calls for search-time enrichment.

### Why This Architecture

| Approach | Index cost (30-min video) | Search cost | Monthly at 10K users |
|----------|--------------------------|-------------|---------------------|
| Claude Vision for everything | ~$1.70 | ~$0.002 | ~$70,200 |
| **Hybrid CLIP + Claude** | **~$0.20** | **~$0.01-0.02** | **~$17,000** |

82% cost reduction. Margins go from 53% to 89%.

### How It Works

```
INDEXING (upload time — cheap, no LLM calls)
═══════════════════════════════════════════

  Video Upload
       │
       ▼
  ┌─────────┐     ┌──────────────┐     ┌────────────┐
  │ ffmpeg   │────▶│ Whisper API  │     │ CLIP       │
  │          │     │              │     │ Sidecar    │
  │ frames   │     │ transcribe   │     │ (Python)   │
  │ @5s      │     │ audio →      │     │            │
  │ + audio  │     │ timestamps   │     │ frames →   │
  └─────────┘     └──────────────┘     │ 768-dim    │
                                        │ vectors    │
                                        └────────────┘
                         │                     │
                         └──────────┬──────────┘
                                    ▼
                             ┌──────────────┐
                             │  ChromaDB    │
                             │              │
                             │  embeddings  │
                             │  + metadata  │
                             │  + transcript│
                             └──────────────┘


SEARCH (query time — selective Claude calls)
═══════════════════════════════════════════

  "find the part where they're eating outside"
       │
       ▼
  ┌────────────┐     ┌──────────────┐     ┌──────────────┐
  │ CLIP       │────▶│  ChromaDB    │────▶│ Claude       │
  │ Sidecar    │     │              │     │ Vision       │
  │            │     │ cosine       │     │              │
  │ query →    │     │ similarity   │     │ ONLY top 3-5 │
  │ 768-dim    │     │ → top 10     │     │ frames →     │
  │ vector     │     │ results      │     │ rich         │
  └────────────┘     └──────────────┘     │ descriptions │
                                           └──────────────┘
                                                  │
                                                  ▼
                                        [{timestamp, thumbnail,
                                          score, description,
                                          transcript_snippet}]
```

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Backend API** | Go (chi router) | Fast, good concurrency for video processing pipelines |
| **Video Processing** | ffmpeg (via Go os/exec) | Frame extraction, audio extraction, clip trimming |
| **Transcription** | OpenAI Whisper API | Word-level timestamps, multilingual, $0.006/min |
| **Frame Embeddings** | OpenCLIP ViT-B/32 (Python sidecar) | Free, local, 768-dim multimodal embeddings |
| **Search Enrichment** | Anthropic Claude API (claude-sonnet-4-20250514, vision) | Rich descriptions of matched frames at search time only |
| **Vector Search** | ChromaDB (Docker) | Cosine similarity over CLIP embeddings |
| **Frontend** | React + TypeScript + Vite + Tailwind | Video player + search UI + clip selector |
| **Infrastructure** | Terraform (AWS) | ECS Fargate, S3, CloudFront, ALB, ECR — deployed tonight |

## CLIP Sidecar Service (Python)

Lightweight FastAPI service wrapping OpenCLIP. Go backend communicates via HTTP.

### Endpoints
```
POST /embed/image   → {image_base64: str}    → {embedding: [float x 768]}
POST /embed/text    → {text: str}            → {embedding: [float x 768]}
POST /embed/batch   → {images: [str, ...]}   → {embeddings: [[float x 768], ...]}
GET  /health        → {status: "ok", model: "ViT-B-32"}
```

### Implementation (sidecar/server.py)
```python
import open_clip
import torch
from PIL import Image
from fastapi import FastAPI
from pydantic import BaseModel
import base64, io

app = FastAPI()
model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
tokenizer = open_clip.get_tokenizer("ViT-B-32")
model.eval()

class ImageRequest(BaseModel):
    image_base64: str

class TextRequest(BaseModel):
    text: str

class BatchRequest(BaseModel):
    images: list[str]

@app.post("/embed/image")
async def embed_image(req: ImageRequest):
    img_bytes = base64.b64decode(req.image_base64)
    img = preprocess(Image.open(io.BytesIO(img_bytes))).unsqueeze(0)
    with torch.no_grad():
        emb = model.encode_image(img)
        emb /= emb.norm(dim=-1, keepdim=True)
    return {"embedding": emb[0].tolist()}

@app.post("/embed/text")
async def embed_text(req: TextRequest):
    tokens = tokenizer([req.text])
    with torch.no_grad():
        emb = model.encode_text(tokens)
        emb /= emb.norm(dim=-1, keepdim=True)
    return {"embedding": emb[0].tolist()}

@app.post("/embed/batch")
async def embed_batch(req: BatchRequest):
    images = []
    for b64 in req.images:
        img_bytes = base64.b64decode(b64)
        images.append(preprocess(Image.open(io.BytesIO(img_bytes))))
    batch = torch.stack(images)
    with torch.no_grad():
        embs = model.encode_image(batch)
        embs /= embs.norm(dim=-1, keepdim=True)
    return {"embeddings": embs.tolist()}
```

### sidecar/requirements.txt
```
fastapi>=0.104.0
uvicorn>=0.24.0
open_clip_torch>=2.24.0
torch>=2.1.0
Pillow>=10.0.0
```

### sidecar/Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
EXPOSE 8100
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8100"]
```

## Go Project Structure

```
scrubless/
├── cmd/
│   └── server/
│       └── main.go              # Entry point, config loading, server startup
├── internal/
│   ├── api/
│   │   ├── handler.go           # HTTP handlers (upload, search, clip, status)
│   │   ├── router.go            # Route definitions (chi)
│   │   └── middleware.go        # CORS, logging, request ID
│   ├── pipeline/
│   │   ├── pipeline.go          # Orchestrates: ffmpeg → whisper → CLIP → index
│   │   ├── ffmpeg.go            # Frame extraction @5s, audio extraction, clip trim
│   │   ├── transcribe.go        # Whisper API client (word-level timestamps)
│   │   ├── embedder.go          # Embedder interface + CLIP sidecar implementation
│   │   └── index.go             # ChromaDB storage (embeddings + metadata)
│   ├── search/
│   │   ├── search.go            # Query → CLIP text embed → ChromaDB → ranked results
│   │   └── enrich.go            # Claude Vision: enrich top-N results with descriptions
│   ├── clip/
│   │   └── clip.go              # ffmpeg: extract subclip by start/end time
│   ├── models/
│   │   └── models.go            # Video, Segment, SearchResult, ProcessingStatus
│   └── config/
│       └── config.go            # Env var loading, defaults
├── sidecar/                     # Python CLIP embedding service (see above)
│   ├── server.py
│   ├── requirements.txt
│   └── Dockerfile
├── web/                         # React frontend
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── VideoUpload.tsx   # Drag-and-drop upload with progress
│   │   │   ├── ProcessingStatus.tsx # Poll /status, show progress bar
│   │   │   ├── SearchBar.tsx     # Text input + search button
│   │   │   ├── ResultsList.tsx   # Grid of results with thumbnails + scores
│   │   │   ├── VideoPlayer.tsx   # HTML5 video player, jumps to timestamp on click
│   │   │   └── ClipExport.tsx    # Select time range, export clip
│   │   └── hooks/
│   │       ├── useVideoSearch.ts # Search API hook
│   │       └── useProcessing.ts  # Upload + status polling hook
│   ├── package.json
│   └── vite.config.ts
├── storage/                     # Local file storage (dev only)
├── infra/                       # Terraform (AWS deployment)
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── vpc.tf
│   ├── ecr.tf
│   ├── ecs.tf
│   ├── alb.tf
│   ├── s3.tf
│   ├── cloudfront.tf
│   ├── iam.tf
│   └── efs.tf
├── go.mod
├── go.sum
├── Makefile
├── docker-compose.yml
├── Dockerfile                   # Go server
└── README.md
```

## Embedder Interface (Key Abstraction)

```go
// internal/pipeline/embedder.go

type Embedder interface {
    EmbedImage(ctx context.Context, imageData []byte) ([]float32, error)
    EmbedText(ctx context.Context, text string) ([]float32, error)
    EmbedImageBatch(ctx context.Context, images [][]byte) ([][]float32, error)
}

// CLIPEmbedder calls the Python sidecar over HTTP
type CLIPEmbedder struct {
    baseURL    string
    httpClient *http.Client
}

func NewCLIPEmbedder(baseURL string) *CLIPEmbedder { ... }
func (c *CLIPEmbedder) EmbedImage(ctx context.Context, imageData []byte) ([]float32, error) { ... }
func (c *CLIPEmbedder) EmbedText(ctx context.Context, text string) ([]float32, error) { ... }
func (c *CLIPEmbedder) EmbedImageBatch(ctx context.Context, images [][]byte) ([][]float32, error) { ... }
```

This interface lets us swap CLIP for a better model (SigLIP, Twelve Labs Marengo, etc.) later without touching the pipeline.

## API Endpoints

```
POST   /api/videos/upload          # Upload video file (multipart/form-data)
                                   # Returns {id: string, status: "processing"}

GET    /api/videos/{id}/status     # Poll processing progress
                                   # Returns {status: "processing"|"indexed"|"error",
                                   #          progress_pct: int, segments_indexed: int,
                                   #          error_message?: string}

POST   /api/videos/{id}/search     # Search within a video
                                   # Body: {query: string, limit?: int}
                                   # Returns [{timestamp_start, timestamp_end,
                                   #           thumbnail_url, score, description,
                                   #           transcript_snippet}]

POST   /api/videos/{id}/clip       # Export a clip
                                   # Body: {start: float, end: float}
                                   # Returns {clip_url: string, duration: float}

GET    /api/videos/{id}/segments   # List all indexed segments (debug/browse)
GET    /api/videos                 # List all uploaded videos
DELETE /api/videos/{id}            # Delete video + all indexed data
```

## docker-compose.yml

```yaml
version: "3.8"

services:
  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma/chroma

  clip-sidecar:
    build: ./sidecar
    ports:
      - "8100:8100"
    deploy:
      resources:
        limits:
          memory: 2G

  server:
    build: .
    ports:
      - "8080:8080"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - CHROMA_URL=http://chromadb:8000
      - CLIP_SIDECAR_URL=http://clip-sidecar:8100
      - STORAGE_PATH=/data/storage
      - PORT=8080
      - FRAME_INTERVAL=5
      - ENRICH_TOP_N=5
    volumes:
      - video_storage:/data/storage
    depends_on:
      - chromadb
      - clip-sidecar

volumes:
  chroma_data:
  video_storage:
```

## Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...       # Claude Vision (search-time enrichment only)
OPENAI_API_KEY=sk-...              # Whisper API (transcription)
CHROMA_URL=http://chromadb:8000    # ChromaDB endpoint (ECS service discovery in prod)
CLIP_SIDECAR_URL=http://clip-sidecar:8100  # CLIP embedding service
STORAGE_BACKEND=s3                 # "local" for dev, "s3" for prod
STORAGE_PATH=./storage             # Local file storage root (dev only)
AWS_S3_BUCKET=scrubless-storage     # S3 bucket for videos, frames, clips
AWS_REGION=us-east-1               # AWS region
PORT=8080                          # Go server port
FRAME_INTERVAL=5                   # Seconds between frame extractions (5 = cost-optimized)
MAX_VIDEO_DURATION=7200            # Max upload duration in seconds (2 hours)
ENRICH_TOP_N=5                     # Number of search results to enrich with Claude Vision
```

## ffmpeg Commands Reference

```bash
# Extract 1 frame every 5 seconds as JPEG (cost-optimized interval)
ffmpeg -i input.mp4 -vf "fps=1/5" -q:v 2 frames/frame_%04d.jpg

# Extract audio as 16kHz WAV for Whisper
ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 audio.wav

# Get video duration
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 input.mp4

# Trim clip (fast, no re-encode)
ffmpeg -i input.mp4 -ss 45.2 -to 58.7 -c copy clip_output.mp4

# Generate thumbnail from specific timestamp
ffmpeg -i input.mp4 -ss 45.2 -vframes 1 -q:v 2 thumbnail.jpg
```

## Claude Vision Enrichment Prompt

Used at search time to describe top matched frames:

```
Describe what's happening in this video frame in 1-2 sentences.
Focus on: who's visible and what they're doing, the setting/location,
the emotional mood or energy of the moment, and any notable objects or actions.
Be specific — this description will help a creator find this exact moment.
```

## MVP Scope — What to Build Tonight

### Phase 1: Infrastructure & Sidecar (first 1-2 hours)
1. CLIP sidecar: Python FastAPI + OpenCLIP ViT-B/32 + Dockerfile
2. docker-compose.yml: ChromaDB + CLIP sidecar
3. Verify: docker-compose up, hit /health, embed a test image
4. Go storage abstraction: interface that supports both local filesystem and S3

### Phase 2: Core pipeline (next 2-3 hours)
5. Go server scaffolding: chi router, config, CORS, file upload → S3
6. ffmpeg pipeline: frame extraction @5s + audio extraction
7. Whisper integration: transcribe audio → timestamped segments
8. CLIP indexing: batch-embed frames via sidecar → store in ChromaDB with metadata

### Phase 3: Search (next 1-2 hours)
9. Search endpoint: query → CLIP text embed → ChromaDB cosine search → top results
10. Claude Vision enrichment: top 5 results → rich descriptions
11. Return results with timestamps, thumbnails, scores, descriptions

### Phase 4: Frontend (next 1-2 hours)
12. Video upload with drag-and-drop
13. Processing status polling (progress bar)
14. Search bar + results grid with thumbnails
15. Video player that jumps to timestamp on result click
16. Basic clip export (select range, download)

### Phase 5: Terraform & Deploy (final 1-2 hours)
17. Terraform modules: VPC, ECR repos, ECS Fargate cluster + services (Go, CLIP sidecar, ChromaDB), S3 bucket, ALB, CloudFront for frontend
18. Dockerfiles: Go server, CLIP sidecar (already done), frontend (nginx)
19. Build images → push to ECR → deploy ECS services
20. Verify end-to-end on live URL
21. Point a domain if available (Route53 or external DNS)

## Terraform Structure

```
infra/
├── main.tf              # Provider, backend config (S3 state)
├── variables.tf         # Configurable vars (region, instance sizes, etc.)
├── outputs.tf           # ALB URL, CloudFront URL, S3 bucket name
├── vpc.tf               # VPC, subnets, security groups
├── ecr.tf               # ECR repos (go-server, clip-sidecar, chromadb)
├── ecs.tf               # ECS cluster, task definitions, services
│                        #   - go-server (Fargate, 0.5 vCPU, 1GB)
│                        #   - clip-sidecar (Fargate, 1 vCPU, 4GB for model)
│                        #   - chromadb (Fargate, 0.5 vCPU, 2GB + EFS volume)
├── alb.tf               # Application Load Balancer + target groups
├── s3.tf                # S3 bucket for video/frame/clip storage
├── cloudfront.tf        # CloudFront distribution for React frontend
├── iam.tf               # Task execution roles, S3 access policies
└── efs.tf               # EFS volume for ChromaDB persistence
```

### AWS Cost Estimate (MVP scale)
| Resource | Spec | Monthly cost |
|----------|------|-------------|
| ECS Fargate (Go server) | 0.5 vCPU, 1GB, always-on | ~$15 |
| ECS Fargate (CLIP sidecar) | 1 vCPU, 4GB, always-on | ~$55 |
| ECS Fargate (ChromaDB) | 0.5 vCPU, 2GB, always-on | ~$25 |
| S3 | 50GB stored + transfers | ~$3 |
| ALB | 1 ALB + LCUs | ~$20 |
| CloudFront | low traffic | ~$1 |
| EFS (ChromaDB data) | 10GB | ~$3 |
| **Total AWS infra** | | **~$122/month** |

Combined with API costs ($22 at MVP scale), total monthly burn is ~$144.

## NOT in V1
- Auto-captions / subtitles on clips
- Social media publishing / platform-specific export
- Batch upload / video library management
- User accounts / authentication
- Mobile app
- Custom domain with SSL (use CloudFront default URL tonight)
- Batch API integration (cost optimization lever 2 — add when needed)
- CI/CD pipeline (manual deploy tonight, GitHub Actions later)

## Build & Run Commands

```bash
# === LOCAL DEV ===

# Start all services locally
docker-compose up -d

# Or run individually for development:
docker run -p 8000:8000 chromadb/chroma
cd sidecar && pip install -r requirements.txt && uvicorn server:app --port 8100
cd scrubless && go run cmd/server/main.go
cd scrubless/web && npm install && npm run dev

# === CLOUD DEPLOY ===

# 1. Init Terraform
cd infra && terraform init

# 2. Build and push Docker images to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

docker build -t scrubless-server .
docker tag scrubless-server:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/scrubless-server:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/scrubless-server:latest

docker build -t scrubless-clip-sidecar ./sidecar
docker tag scrubless-clip-sidecar:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/scrubless-clip-sidecar:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/scrubless-clip-sidecar:latest

# 3. Build and deploy frontend to S3/CloudFront
cd web && npm run build
aws s3 sync dist/ s3://scrubless-frontend --delete

# 4. Deploy infra
cd infra && terraform apply

# 5. Verify
curl https://<alb-url>/api/videos
```

## Success Criteria for Tonight

Upload a real 30+ minute video **to the live cloud-hosted app** → wait for processing → type "find when someone is laughing outside" → get back the right timestamp with a thumbnail → click it → video plays from that exact moment → export clip.

Shareable URL that anyone can hit. Not localhost. Not ngrok. Real infra, Terraform-provisioned, on AWS.

If that works, this is real.

## Cost Model Summary

| Stage | Users | Videos/mo | Total cost | MRR | Margin |
|-------|-------|-----------|------------|-----|--------|
| MVP | 1 | 20 | $22 | $0 | — |
| Beta | 500 | 1,000 | $830 | $0 | — |
| Early paid | 2,000 | 8,000 | $3,600 | $30,000 | 88% |
| Growth | 10,000 | 40,000 | $17,000 | $150,000 | 89% |
| Scale | 50,000 | 200,000 | $83,000 | $750,000 | 89% |
