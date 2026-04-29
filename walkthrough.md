# Hybrid AI Outreach Agent — Project Walkthrough

I have successfully designed and built the complete **Hybrid AI Outreach Agent System**. This production-ready platform unifies Email, WhatsApp, and AI Voice Calling into a single CRM dashboard, powered by a highly scalable asynchronous backend.

## 🚀 Key Achievements

### 1. Robust Core Infrastructure
- **FastAPI Backend**: Built a fully asynchronous API utilizing modern Python features for high performance.
- **Task Queues**: Integrated **Celery & Redis** to handle heavy background tasks (bulk emailing, mass WhatsApp broadcasting, and concurrent AI calling campaigns) without blocking the main API thread.
- **Database Architecture**: Implemented `SQLAlchemy` with async drivers (`aiosqlite`) designed for easy migration to PostgreSQL in production.
- **Dockerized**: Created a comprehensive `docker-compose.yml` that seamlessly spins up the FastAPI app, Redis broker, and 4 dedicated Celery workers for each channel.

### 2. Multi-Channel Automation
- **📧 Email Engine**: Supports dynamic sender rotation, Jinja2 personalization, SMTP/SendGrid integration, and custom pixel/link injection for accurate open & click tracking.
- **💬 WhatsApp Engine**: Connects to the Meta Cloud API for bulk template broadcasting and processes inbound webhooks for intelligent auto-replies.
- **📞 AI Voice Calling**: Built a robust Phase 1 Voice Agent using Twilio's `<Gather>` loop integrated with **OpenAI GPT-4**. It makes outbound calls, interprets speech, generates human-like conversational responses, and auto-classifies the call outcome (e.g., Interested, Voicemail).

### 3. Lead Management & Analytics
- **CRM Features**: Complete CRUD operations for leads, campaigns, and activity logs.
- **CSV Importer**: An intelligent pandas-based ingestion service that handles bulk lead imports, sanitizes data, standardizes phone numbers, and prevents duplicates.
- **Advanced Analytics**: Real-time pipeline funnel calculations, 30-day activity trend generation, and capabilities to export reports to Excel and PDF.

### 4. Premium Frontend Dashboard
- **Sleek UI/UX**: Designed a custom Dribbble-inspired red-and-black dark mode interface with glassmorphic top bars, subtle gradients, and micro-animations.
- **Interactive Visualizations**: Integrated `Chart.js` for dynamic timeline trends and channel performance distribution.
- **Seamless SPA Experience**: Built a lightweight Vanilla JS Single Page Application (SPA) that communicates asynchronously with the backend, featuring JWT-based auth flows and toast notifications.

---

## 🏗️ Architecture Map

The system is highly modularized under `c:\leadgenai\app`:

- `api/` — FastAPI route definitions and input validation.
- `services/` — Core business logic engines (`email_engine.py`, `whatsapp_engine.py`, `voice_agent.py`).
- `tasks/` — Celery worker definitions for handling rate-limited bulk campaigns.
- `crud/` — Database interactions.
- `models/` — SQLAlchemy ORM schemas.
- `static/` — The premium HTML/CSS/JS frontend application.

---

## 🏃‍♂️ How to Run It

Since all dependencies and the Docker environment are configured, you can launch the entire stack easily.

### Option 1: Using Docker (Recommended)
1. Ensure Docker Desktop is running.
2. Open your terminal in `c:\leadgenai`.
3. Run the following command to build and start the entire cluster (API, Redis, 4 Celery workers):
   ```bash
   docker-compose up --build
   ```

### Option 2: Local Development
If you prefer running it locally without Docker:
1. Open a terminal as Administrator in `c:\leadgenai`.
2. Create and activate a virtual environment:
   ```cmd
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install the required dependencies:
   ```cmd
   pip install -r requirements.txt
   ```
4. Start the development server:
   ```cmd
   uvicorn app.main:app --reload
   ```
5. Ensure a local instance of Redis is running on port `6379`.

---

## 🔑 Next Steps for You

1. **API Keys**: Open the `.env` file in the project root and populate your specific API keys:
   - `SENDGRID_API_KEY`
   - `WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_ACCESS_TOKEN`
   - `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`
   - `OPENAI_API_KEY`
2. **Access the Dashboard**: Once the server is running, navigate to [http://localhost:8000](http://localhost:8000) in your browser.
3. **Log In**: Register a new admin account via the modal to access the full suite of tools.
4. **API Docs**: To explore the backend endpoints, visit [http://localhost:8000/docs](http://localhost:8000/docs).

> [!TIP]
> The system is currently designed to use local SQLite for easy testing. When you are ready for a heavy production load, simply change the `DATABASE_URL` in your `.env` to point to an `asyncpg` PostgreSQL database string. No code changes are required!
