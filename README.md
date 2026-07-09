# DocRAG v4 — Production-Ready AI Document Analyzer

## Tech Stack (Sir ko batao)
- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python + FastAPI
- **AI Model:** LLaMA 3.3 70B via Groq API (FREE)
- **Vector Database:** ChromaDB (Persistent) — RAG ke liye
- **SQL Database:** SQLite via SQLAlchemy — Users, Documents, Chat History
- **Auth:** JWT Tokens + BCrypt Password Hashing
- **RAG:** ChromaDB se semantic search → LLaMA se answer

## Setup (Ek baar karna hai)

### Step 1 — Install libraries
```
pip install fastapi uvicorn python-multipart PyPDF2 chromadb groq python-jose passlib sqlalchemy
```

### Step 2 — API Key set karo
Windows PowerShell:
```
$env:GROQ_API_KEY="tumhari-groq-key"
```

### Step 3 — Chalaao
```
py -3.11 -m uvicorn main:app --reload
```

### Step 4 — Browser mein kholo
```
http://localhost:8000
```

## Features
✅ Register/Login with BCrypt password hashing
✅ JWT Authentication
✅ Multiple PDF upload
✅ AI Summary + Key Points (LLaMA 3.3 70B)
✅ RAG Query — ask questions about your PDFs
✅ Keyword Search inside documents
✅ Chat History (saved in SQLite)
✅ Dashboard with stats
✅ Profile edit
✅ Dark/Light mode
✅ PDF Preview
✅ Download Summary
✅ Delete documents
✅ Persistent storage — data survives server restart
✅ User data isolation — users can only see their own data
