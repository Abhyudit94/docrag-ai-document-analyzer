# DocRAG — AI Document Analyzer

An AI-powered document analysis platform that lets users upload PDFs, get instant summaries, and ask questions about their documents using RAG (Retrieval-Augmented Generation).

## Tech Stack

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python + FastAPI
- **AI Model:** LLaMA 3.3 70B via Groq API
- **Vector Database:** ChromaDB (persistent) — used for RAG-based semantic search
- **SQL Database:** SQLite via SQLAlchemy — stores users, documents, and chat history
- **Authentication:** JWT tokens + BCrypt password hashing
- **RAG Pipeline:** ChromaDB semantic search → relevant context → LLaMA generates the answer

## Features

- Register/Login with secure password hashing
- JWT-based authentication
- Multiple PDF upload support
- AI-generated summaries and key points (LLaMA 3.3 70B)
- RAG-based Q&A — ask questions about your uploaded PDFs
- Keyword search inside documents
- Persistent chat history (saved in SQLite)
- Dashboard with usage stats
- Profile editing
- Dark/Light mode
- PDF preview in-browser
- Downloadable summaries
- Document deletion
- Persistent storage — data survives server restarts
- User data isolation — each user only sees their own documents

## Setup Instructions

### Step 1 — Install dependencies

### Step 2 — Configure environment variables
Copy `.env.example` to `.env` and fill in your values:

'''
GROQ_API_KEY=your-groq-api-key
JWT_SECRET_KEY=your-random-secret-string
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
'''

### Step 3 — Run the server

### Step 4 — Open in browser

## Live Demo
[Add your Render deployment link here once deployed]

