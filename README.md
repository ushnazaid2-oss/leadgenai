# LeadGenAI — Hybrid AI Outreach Agent System

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![Celery](https://img.shields.io/badge/Celery-5.4-brightgreen.svg)](https://celeryproject.org)
[![Redis](https://img.shields.io/badge/Redis-7-red.svg)](https://redis.io)

A **production-ready**, modular AI-powered outreach automation platform with:
- 📧 **Email Automation** — SMTP/SendGrid with open & click tracking
- 💬 **WhatsApp Automation** — Meta Cloud API template broadcasting
- 📞 **AI Voice Calling** — Twilio + GPT-4 conversational agent
- 📊 **Unified CRM Dashboard** — Premium red & black UI with pipeline analytics

---

## Architecture

```
FastAPI Backend (Async)
    ├── Auth (JWT + bcrypt)
    ├── Lead Management (CSV Import + CRUD)
    ├── Email Module   ──► Celery Worker (email queue)
    ├── WhatsApp Module ─► Celery Worker (whatsapp queue)
    ├── Voice Agent    ──► Celery Worker (calls queue)
    └── Analytics      ──► Celery Worker (analytics queue)
                              ↓
                         Redis (Broker + Results)
                              ↓
                    SQLite / PostgreSQL (Persistence)
```

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
# 1. Clone and enter the project
cd leadgenai

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env with your API keys
notepad .env

# 4. Start everything with one command
docker-compose up --build
```

The app will be available at **http://localhost:8000**

---

### Option 2: Local Development

#### Prerequisites
- Python 3.11+
- Redis (running locally on port 6379)

#### Installation

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and configure environment
cp .env.example .env
# Edit .env with your credentials

# 4. Start the FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. Start Celery workers (separate terminals)
celery -A app.celery_app worker -Q email -l info --concurrency=2
celery -A app.celery_app worker -Q whatsapp -l info --concurrency=2
celery -A app.celery_app worker -Q calls -l info --concurrency=1
celery -A app.celery_app worker -Q analytics -l info --concurrency=1
```

---

## Environment Configuration

Copy `.env.example` to `.env` and fill in the following:

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET_KEY` | ✅ | Strong random secret for JWT signing |
| `SENDGRID_API_KEY` | Email | SendGrid API key for email delivery |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp | Meta phone number ID |
| `WHATSAPP_ACCESS_TOKEN` | WhatsApp | Meta permanent access token |
| `TWILIO_ACCOUNT_SID` | Calls | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Calls | Twilio Auth Token |
| `OPENAI_API_KEY` | Calls | OpenAI API key for GPT-4 |
| `TRACKING_BASE_URL` | Email | Public URL for tracking pixels (use ngrok in dev) |

### Feature Flags

```env
FEATURE_EMAIL_ENABLED=true
FEATURE_WHATSAPP_ENABLED=true
FEATURE_CALLS_ENABLED=true
```

---

## API Documentation

Once running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### Authentication

All API endpoints (except auth and webhooks) require JWT Bearer token.

```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@example.com","password":"secure123"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"secure123"}'

# Use token in subsequent requests
curl http://localhost:8000/api/leads/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Lead Management

```bash
# Import CSV
curl -X POST http://localhost:8000/api/leads/import/csv \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@scripts/sample_leads.csv"

# Create lead manually
curl -X POST http://localhost:8000/api/leads/ \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"John Doe","email":"john@example.com","company":"TechCorp","niche":"SaaS"}'

# List leads with filters
curl "http://localhost:8000/api/leads/?status=new&niche=SaaS&page=1&per_page=50" \
  -H "Authorization: Bearer TOKEN"
```

### Email Campaigns

```bash
# Add sender account
curl -X POST http://localhost:8000/api/email/accounts \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sales Team",
    "email": "sales@yourcompany.com",
    "provider": "sendgrid",
    "sendgrid_api_key": "SG.xxx",
    "daily_limit": 500
  }'

# Create a campaign
curl -X POST http://localhost:8000/api/campaigns/ \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Q1 Outreach",
    "type": "email",
    "subject": "Quick question for {name} at {company}",
    "body": "<p>Hi {name}, ...</p>"
  }'

# Launch bulk email campaign (runs in background via Celery)
curl -X POST http://localhost:8000/api/email/campaign \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": 1,
    "subject": "Hi {name}, quick question",
    "body_html": "<p>Hello {name} at {company}...</p>",
    "filters": {"niche": "SaaS"}
  }'

# Check campaign task status
curl http://localhost:8000/api/email/task/TASK_ID \
  -H "Authorization: Bearer TOKEN"

# Get email stats
curl http://localhost:8000/api/email/stats \
  -H "Authorization: Bearer TOKEN"
```

### WhatsApp Campaigns

```bash
# Send single message
curl -X POST http://localhost:8000/api/whatsapp/send \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id": 1,
    "template_name": "business_intro",
    "parameters": [
      {"value": "John"},
      {"value": "LeadGenAI"},
      {"value": "SaaS"}
    ]
  }'

# Launch broadcast
curl -X POST http://localhost:8000/api/whatsapp/broadcast \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": 2,
    "template_name": "business_intro",
    "filters": {"niche": "SaaS"}
  }'
```

### AI Voice Calls

```bash
# Initiate single AI call
curl -X POST http://localhost:8000/api/calls/initiate \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id": 1,
    "from_number": "+14155551234",
    "call_script": "Hi, this is Alex from LeadGenAI..."
  }'

# Launch call campaign
curl -X POST http://localhost:8000/api/calls/campaign \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": 3,
    "call_script": "Hi {name}, this is Alex...",
    "filters": {"status": "interested"}
  }'

# List available Twilio numbers
curl http://localhost:8000/api/calls/numbers \
  -H "Authorization: Bearer TOKEN"

# Get call logs with transcripts
curl http://localhost:8000/api/calls/logs \
  -H "Authorization: Bearer TOKEN"
```

### Analytics & Exports

```bash
# Dashboard summary
curl http://localhost:8000/api/analytics/dashboard \
  -H "Authorization: Bearer TOKEN"

# Pipeline funnel data
curl http://localhost:8000/api/analytics/pipeline \
  -H "Authorization: Bearer TOKEN"

# 30-day timeline
curl "http://localhost:8000/api/analytics/timeline?days=30" \
  -H "Authorization: Bearer TOKEN"

# Export to Excel
curl http://localhost:8000/api/analytics/export/excel \
  -H "Authorization: Bearer TOKEN" \
  -o leads_report.xlsx

# Export to PDF
curl http://localhost:8000/api/analytics/export/pdf \
  -H "Authorization: Bearer TOKEN" \
  -o leads_report.pdf
```

---

## Twilio Setup (AI Voice Calling)

1. **Create Twilio account** at [twilio.com](https://twilio.com)
2. **Get Account SID and Auth Token** from your Twilio console
3. **Purchase a phone number** (or use the API):
   ```bash
   curl -X POST http://localhost:8000/api/calls/numbers/purchase \
     -H "Authorization: Bearer TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"country_code": "US"}'
   ```
4. **Expose your server** (for development, use ngrok):
   ```bash
   ngrok http 8000
   ```
   Set `TRACKING_BASE_URL=https://your-ngrok-url.ngrok.io` in `.env`

### Supported Countries
Purchase numbers for: USA (+1), Bahrain (+973), Qatar (+974), Kuwait (+965), UK (+44), and 100+ more countries via the Twilio console.

---

## WhatsApp Setup

1. Create a **Meta Developer App** at [developers.facebook.com](https://developers.facebook.com)
2. Add **WhatsApp Business** product to your app
3. Get your **Phone Number ID** and **Access Token**
4. Create and get **message templates** approved in Meta Business Suite
5. Configure webhook URL in Meta App:
   - Webhook URL: `https://your-domain.com/api/whatsapp/webhook`
   - Verify Token: matches `WHATSAPP_VERIFY_TOKEN` in your `.env`

---

## Email Tracking Setup

For open and click tracking, your server must be publicly accessible:

1. **Development:** Use ngrok → set `TRACKING_BASE_URL=https://xxx.ngrok.io`
2. **Production:** Use your actual domain → set `TRACKING_BASE_URL=https://yourdomain.com`

Tracking endpoints (public, no auth):
- `GET /api/track/open/{tracking_id}` — Open pixel
- `GET /api/track/click/{tracking_id}/{url}` — Click redirect

---

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_leads.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

---

## Project Structure

```
leadgenai/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Settings & feature flags
│   ├── database.py          # Async SQLAlchemy engine
│   ├── celery_app.py        # Celery + Redis config
│   ├── dependencies.py      # JWT auth dependencies
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response models
│   ├── crud/                # Database access layer
│   ├── services/            # Business logic
│   │   ├── auth_service.py
│   │   ├── email_engine.py
│   │   ├── whatsapp_engine.py
│   │   ├── voice_agent.py
│   │   ├── analytics.py
│   │   ├── csv_importer.py
│   │   ├── tracking.py
│   │   └── circuit_breaker.py
│   ├── tasks/               # Celery background tasks
│   │   ├── email_tasks.py
│   │   ├── whatsapp_tasks.py
│   │   ├── call_tasks.py
│   │   └── analytics_tasks.py
│   ├── api/                 # FastAPI route handlers
│   │   ├── auth.py
│   │   ├── leads.py
│   │   ├── campaigns.py
│   │   ├── email.py
│   │   ├── whatsapp.py
│   │   ├── calls.py
│   │   ├── analytics.py
│   │   └── tracking.py
│   ├── middleware/          # Logging & rate limiting
│   └── static/              # CRM Dashboard (HTML/CSS/JS)
├── templates/               # Jinja2 email & WhatsApp templates
├── scripts/                 # Sample data & scripts
├── tests/                   # Pytest test suite
├── logs/                    # Application logs (auto-created)
├── .env.example             # Environment template
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Production Checklist

- [ ] Set strong `JWT_SECRET_KEY` (min 32 random chars)
- [ ] Set `APP_ENV=production` and `DEBUG=false`
- [ ] Switch `DATABASE_URL` to PostgreSQL
- [ ] Configure proper `CORS_ORIGINS` (not `*`)
- [ ] Set up SSL/TLS (use nginx + certbot)
- [ ] Configure Sentry DSN for error monitoring
- [ ] Set up log rotation for `logs/` directory
- [ ] Use Docker secrets for sensitive credentials
- [ ] Configure Redis persistence for task queue durability

---

## Upgrade Path: Real-Time Voice Streaming

The current voice agent uses Twilio `<Gather>` (Phase 1). To upgrade to real-time streaming:

1. Replace `<Gather>` with Twilio Media Streams (`<Connect><Stream>`)
2. Add WebSocket endpoint `/api/calls/media-stream`
3. Integrate Deepgram for real-time STT
4. Use OpenAI Realtime API or ElevenLabs for low-latency TTS
5. Implement audio buffer and VAD (Voice Activity Detection)

---

## License

MIT License — Built by LeadGenAI Team
