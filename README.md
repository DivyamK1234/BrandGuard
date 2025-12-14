# BrandGuard - Audio Safety Verification Microservice

[![Deploy to Cloud Run](https://github.com/YOUR_ORG/brandguard/actions/workflows/deploy.yaml/badge.svg)](https://github.com/YOUR_ORG/brandguard/actions/workflows/deploy.yaml)

> **AI-powered audio content classification for brand safety in digital advertising.**  
> Built following DoubleVerify's AdDomain Verification architecture patterns.

![BrandGuard Dashboard](docs/screenshot.png)

## 🎯 Overview

BrandGuard is a production-grade microservice that analyzes audio content for brand safety classification. It uses **Google Cloud's Vertex AI (Gemini 3.0)** for intelligent content analysis and provides real-time classifications for ad-tech platforms.

### Key Features

- **AI-Powered Classification**: Gemini 3.0 Pro analyzes audio transcripts for brand safety
- **Ultra-Low Latency**: Cache-first architecture with <5ms cached lookups
- **Manual Overrides**: Admin console for instant classification overrides
- **Visual Analysis**: Waveform visualization with unsafe segment highlighting
- **Production Ready**: Docker, Cloud Run, GitHub Actions CI/CD

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Request                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Override   │→ │    Cache     │→ │      AI Engine        │  │
│  │  (Firestore) │  │   (Redis)    │  │  (Gemini + STT)       │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Lookup Priority (Cache-First, AI-Fallback)

1. **Override Check** → Firestore manual overrides (highest priority)
2. **Cache Check** → Redis with 24h TTL (<5ms target)
3. **AI Analysis** → Gemini 3.0 classification (fallback)

## 📁 Project Structure

```
BrandGuard/
├── backend/                  # FastAPI Backend
│   ├── logic/
│   │   ├── overrides.py     # Firestore override checks (ADVERIFY-UI-1)
│   │   ├── cache.py         # Redis caching (ADVERIFY-BE-1)
│   │   └── ai_engine.py     # Gemini AI classification (ADVERIFY-AI-1)
│   ├── models.py            # Pydantic data models
│   ├── config.py            # Configuration & prompts
│   ├── main.py              # FastAPI application
│   ├── Dockerfile           # Production container
│   └── requirements.txt     # Python dependencies
│
├── frontend/                 # Next.js Dashboard
│   ├── app/
│   │   ├── page.tsx         # Main dashboard
│   │   ├── layout.tsx       # Root layout
│   │   └── globals.css      # Tailwind styles
│   ├── components/
│   │   ├── AudioAnalyzer.tsx    # Waveform + analysis UI
│   │   └── AdminConsole.tsx     # Override management
│   ├── Dockerfile           # Production container
│   └── package.json         # Node dependencies
│
├── .github/
│   └── workflows/
│       └── deploy.yaml      # Cloud Run CI/CD (ADVERIFY-BE-3)
│
├── docker-compose.yaml      # Local development
└── .env.example             # Environment template
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Google Cloud Project with:
  - Firestore (Native mode)
  - Cloud Storage bucket
  - Speech-to-Text API enabled
  - Vertex AI API enabled
- Node.js 20+ (for frontend development)
- Python 3.11+ (for backend development)

### Local Development

1. **Clone and configure**
```bash
git clone https://github.com/YOUR_ORG/brandguard.git
cd brandguard
cp .env.example .env
# Edit .env with your GCP project details
```

2. **Authenticate with GCP**
```bash
gcloud auth application-default login
```

3. **Start services**
```bash
docker-compose up -d
```

4. **Access the dashboard**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Development Without Docker

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## 📡 API Reference

### Verify Audio
```http
POST /api/v1/verify_audio
Content-Type: multipart/form-data

audio_file: <file>
audio_id: optional_custom_id
client_policy: optional_policy_rules
```

**Response:**
```json
{
  "audio_id": "audio_12345",
  "brand_safety_score": "RISK_MEDIUM",
  "fraud_flag": false,
  "category_tags": ["news", "politics"],
  "source": "AI_GENERATED",
  "confidence_score": 0.87,
  "unsafe_segments": [
    {"start": 12.5, "end": 18.3, "reason": "controversial_topic"}
  ],
  "transcript_snippet": "...discussing the heated debate..."
}
```

### Override Management
```http
GET    /api/v1/admin/override          # List overrides
POST   /api/v1/admin/override          # Create override
PUT    /api/v1/admin/override/{id}     # Update override
DELETE /api/v1/admin/override/{id}     # Delete override
```

### Health Checks
```http
GET /health        # Full health status
GET /health/ready  # Kubernetes readiness probe
GET /health/live   # Kubernetes liveness probe
```

## 🔧 Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_CLOUD_PROJECT` | GCP Project ID | required |
| `GCS_BUCKET_NAME` | Audio storage bucket | required |
| `REDIS_HOST` | Redis hostname | localhost |
| `REDIS_PORT` | Redis port | 6379 |
| `CACHE_TTL_SECONDS` | Cache TTL (24h) | 86400 |
| `GEMINI_MODEL` | Vertex AI model | gemini-2.0-flash-001 |
| `VERTEX_AI_LOCATION` | Vertex AI region | us-central1 |

## 📊 Architecture Mapping

| AdDomain Story | BrandGuard Implementation |
|----------------|---------------------------|
| ADVERIFY-BE-1 | `logic/cache.py` - Redis caching with <20ms target |
| ADVERIFY-AI-1 | `logic/ai_engine.py` - Gemini classification |
| ADVERIFY-UI-1 | `logic/overrides.py` + Admin Console |
| ADVERIFY-BE-3 | `.github/workflows/deploy.yaml` |

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest tests/ -v --cov=.

# Frontend type check
cd frontend
npm run type-check
npm run lint
```

## 📜 License

Proprietary - DoubleVerify Interview Project

---

Built with ❤️ using FastAPI, Next.js, and Vertex AI
# trigger
