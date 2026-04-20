# Nagrik AI
## 📄 Local Language Civic Document Translator (MVP)

A beginner-friendly full-stack application that extracts, interprets, and simplifies civic documents (PDFs/images) into understandable language, with optional audio output.

# 🚀 Overview

Government and civic documents are often complex, technical, and inaccessible—especially for users unfamiliar with formal or non-local language.

This MVP solves that by:

Extracting text from uploaded documents using OCR
Structuring content in a page-aware format
Retrieving relevant civic knowledge
Generating simplified, grounded explanations
Optionally converting output into speech
🧱 Tech Stack
Frontend
HTML
CSS
Vanilla JavaScript
Backend
Python
FastAPI
Core Integrations
Mistral OCR API → document text extraction
PageIndex-style tree indexing → page-aware retrieval
Civic knowledge base → contextual grounding
Mistral Chat (optional) → simplification
gTTS → audio generation
⚙️ How It Works
User uploads a PDF or image
File is sent to Mistral Files API (purpose=ocr)
OCR extracts structured text
Text is converted into a page-aware tree index
Relevant sections are retrieved using similarity
Civic knowledge base provides grounded explanations
Optional: Chat model simplifies output
Optional: gTTS converts explanation to audio
🖥️ Setup & Run
✅ Windows (Recommended)

From project root:

./scripts/start_server.ps1
What this script does:
Creates .venv (if not present)
Installs dependencies from backend/requirements.txt
Creates .env from .env.example (if missing)
Starts FastAPI server using Uvicorn
⚡ Optional Flags
# Skip dependency installation
./scripts/start_server.ps1 -SkipInstall

# Disable auto-reload
./scripts/start_server.ps1 -NoReload

# Custom port
./scripts/start_server.ps1 -Port 8080

# Bind host
./scripts/start_server.ps1 -BindHost 0.0.0.0 -Port 8000
🧰 Alternative (Batch Script)
start-server.bat
🌐 Access App

Open in browser:

http://127.0.0.1:8000
🛠️ Manual Setup (All Platforms)
1. Create virtual environment
python -m venv .venv

2. Activate environment
Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
macOS/Linux:
source .venv/bin/activate

3. Install dependencies
pip install -r backend/requirements.txt

4. Setup environment variables
cp .env.example .env

5. Run server
python -m uvicorn backend.main:app --reload
🔐 Environment Variables

Create a .env file in the root directory:

MISTRAL_API_KEY=your_key_here
MISTRAL_BASE_URL=https://api.mistral.ai/v1
MISTRAL_OCR_MODEL=mistral-ocr-latest
MISTRAL_CHAT_MODEL=mistral-small-latest

MAX_CONTEXT_NODES=3
MAX_GUIDELINE_HITS=3
TTS_LANGUAGE=en
ELEVENLABS_API_KEY=

# 🧠 Key Features
📄 OCR-based document understanding
🌳 Page-aware indexing (better than flat text parsing)
📚 Grounded civic explanations (reduces hallucination)
🧾 Works even without LLM (deterministic fallback)
🔊 Text-to-speech output
⚠️ Limitations (Be Honest — This Matters)
OCR quality depends on input clarity
Civic knowledge base is limited (not exhaustive)
Simplification quality depends on model availability
No multilingual UI yet (despite the idea targeting it)

If you present this in a hackathon and ignore these, judges will call it out.

# 🧭 Future Improvements
- Multi-language translation (Hindi + regional languages)
- Better retrieval (vector DB instead of basic indexing)
- User personalization (education level, language preference)
- Mobile-friendly UI
- Offline support for rural areas

# 🎯 Use Cases
- Rural citizens understanding government forms
- Students learning how civic systems work
- NGOs assisting people with documentation
- First-time applicants navigating bureaucracy
  
Otherwise, it stays a “good idea with a working prototype”—not a product.
