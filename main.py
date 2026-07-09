from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from groq import Groq
import PyPDF2
import chromadb
import uuid, json, io
from database import get_db, User, ChatHistory, Stats, Document
from auth import create_token, verify_token, hash_password, verify_password
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="DocRAG API")

_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("documents")
ai_client = Groq()
security = HTTPBearer()

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class QueryRequest(BaseModel):
    question: str

class SearchRequest(BaseModel):
    keyword: str

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None

def get_or_create_stats(db, email):
    stats = db.query(Stats).filter(Stats.user_email == email).first()
    if not stats:
        stats = Stats(user_email=email, total_docs=0, total_queries=0, total_pages=0)
        db.add(stats); db.commit(); db.refresh(stats)
    return stats

def extract_text_from_pdf(content: bytes):
    text = ""
    pages = 0
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        pages = len(reader.pages)
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {str(e)}")
    return text, pages

@app.get("/")
def home():
    return FileResponse("static/index.html")

@app.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if not req.name.strip() or not req.email.strip() or not req.password.strip():
        raise HTTPException(status_code=400, detail="All fields are required")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if db.query(User).filter(User.email == req.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(name=req.name.strip(), email=req.email.lower().strip(), password=hash_password(req.password))
    db.add(user); db.commit()
    get_or_create_stats(db, req.email.lower())
    return {"token": create_token(req.email.lower()), "name": user.name}

@app.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail="Email and password required")
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"token": create_token(user.email), "name": user.name}

@app.get("/profile")
def get_profile(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    email = verify_token(credentials.credentials)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    stats = get_or_create_stats(db, email)
    return {"name": user.name, "email": user.email,
            "member_since": user.created_at.strftime("%B %Y"),
            "stats": {"total_docs": stats.total_docs, "total_queries": stats.total_queries, "total_pages": stats.total_pages}}

@app.put("/profile")
def update_profile(req: UpdateProfileRequest, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    email = verify_token(credentials.credentials)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if req.name: user.name = req.name.strip()
    if req.password:
        if len(req.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        user.password = hash_password(req.password)
    db.commit()
    return {"message": "Profile updated successfully", "name": user.name}

@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    email = verify_token(credentials.credentials)
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum 10MB allowed")

    text, pages = extract_text_from_pdf(content)

    if len(text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Could not extract text. This may be a scanned PDF. Please use a text-based PDF.")

    doc_id = str(uuid.uuid4())

    # Save the original PDF to disk so it persists across restarts
    stored_filename = f"{doc_id}.pdf"
    with open(os.path.join(UPLOAD_DIR, stored_filename), "wb") as f:
        f.write(content)

    # Store chunks in ChromaDB for RAG search
    chunks = [text[i:i+800] for i in range(0, min(len(text), 16000), 800)]
    for i, chunk in enumerate(chunks):
        if chunk.strip():
            collection.add(
                documents=[chunk],
                ids=[f"{doc_id}_{i}"],
                metadatas=[{"filename": file.filename, "doc_id": doc_id, "user": email}]
            )

    # AI Summary
    try:
        response = ai_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": f"""Analyze this document. Respond ONLY with valid JSON, no markdown.
Format: {{"summary":"2-3 sentence summary","points":["point 1","point 2","point 3","point 4","point 5"]}}
Document: {text[:3000]}"""}],
            max_tokens=1000
        )
        raw = response.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
        result = json.loads(raw)
    except Exception:
        result = {"summary": "Summary could not be generated.", "points": []}

    size_kb = round(len(content) / 1024, 1)
    summary = result.get("summary", "")
    points = result.get("points", [])

    # Persist the document record so it survives server restarts
    doc = Document(
        doc_id=doc_id, user_email=email, filename=file.filename,
        pages=pages, size_kb=size_kb, summary=summary, points=json.dumps(points)
    )
    db.add(doc)

    stats = get_or_create_stats(db, email)
    stats.total_docs += 1
    stats.total_pages += pages
    db.commit()

    return {"doc_id": doc_id, "filename": file.filename,
            "summary": summary, "points": points,
            "pages": pages, "size_kb": size_kb}

@app.get("/documents")
def list_documents(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    email = verify_token(credentials.credentials)
    docs = db.query(Document).filter(Document.user_email == email).order_by(Document.created_at.desc()).all()
    return {"documents": [{
        "doc_id": d.doc_id, "filename": d.filename, "pages": d.pages,
        "size_kb": d.size_kb, "summary": d.summary, "points": json.loads(d.points or "[]"),
        "created_at": d.created_at.strftime("%d %b %Y, %I:%M %p")
    } for d in docs]}

@app.get("/documents/{doc_id}/file")
def get_document_file(doc_id: str, token: str, db: Session = Depends(get_db)):
    email = verify_token(token)
    doc = db.query(Document).filter(Document.doc_id == doc_id, Document.user_email == email).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File missing on server")
    return FileResponse(path, media_type="application/pdf", filename=doc.filename)

@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    email = verify_token(credentials.credentials)
    doc = db.query(Document).filter(Document.doc_id == doc_id, Document.user_email == email).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        collection.delete(where={"doc_id": doc_id})
    except Exception:
        pass

    path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")
    if os.path.exists(path):
        os.remove(path)

    stats = get_or_create_stats(db, email)
    stats.total_docs = max(0, stats.total_docs - 1)
    stats.total_pages = max(0, stats.total_pages - (doc.pages or 0))
    db.delete(doc)
    db.commit()

    return {"message": "Document deleted"}

@app.post("/query")
def query_documents(req: QueryRequest, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    email = verify_token(credentials.credentials)
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        total = collection.count()
        if total == 0:
            raise HTTPException(status_code=404, detail="Please upload some PDFs first.")
        results = collection.query(query_texts=[req.question], n_results=min(5, total), where={"user": email})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not results["documents"][0]:
        raise HTTPException(status_code=404, detail="No relevant content found in your documents.")

    context = "\n\n".join(results["documents"][0])
    filenames = list(set([m["filename"] for m in results["metadatas"][0]]))

    try:
        response = ai_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": f"""You are a helpful RAG assistant. Answer using ONLY the document context.
If not found, say "I couldn't find this in the uploaded documents."
Mention which document the answer comes from.
Documents ({', '.join(filenames)}): {context}
Question: {req.question}"""}],
            max_tokens=800
        )
        answer = response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI error: {str(e)}")

    chat = ChatHistory(user_email=email, question=req.question, answer=answer, sources=json.dumps(filenames))
    db.add(chat)
    stats = get_or_create_stats(db, email)
    stats.total_queries += 1
    db.commit()

    return {"answer": answer, "sources": filenames}

@app.post("/search")
def search_documents(req: SearchRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    email = verify_token(credentials.credentials)
    if not req.keyword.strip():
        raise HTTPException(status_code=400, detail="Search keyword cannot be empty")
    try:
        total = collection.count()
        if total == 0:
            return {"results": []}
        results = collection.query(query_texts=[req.keyword], n_results=min(8, total), where={"user": email})
    except Exception:
        return {"results": []}

    if not results["documents"][0]:
        return {"results": []}

    seen = set()
    search_results = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        key = f"{meta['doc_id']}_{doc[:50]}"
        if key not in seen:
            seen.add(key)
            search_results.append({"filename": meta["filename"], "snippet": doc[:300], "doc_id": meta["doc_id"]})
    return {"results": search_results}

@app.get("/history")
def get_history(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    email = verify_token(credentials.credentials)
    history = db.query(ChatHistory).filter(ChatHistory.user_email == email).order_by(ChatHistory.created_at.desc()).limit(50).all()
    return {"history": [{"question": h.question, "answer": h.answer,
                         "sources": json.loads(h.sources or "[]"),
                         "created_at": h.created_at.strftime("%d %b %Y, %I:%M %p")} for h in history]}

@app.delete("/history")
def clear_history(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    email = verify_token(credentials.credentials)
    db.query(ChatHistory).filter(ChatHistory.user_email == email).delete()
    db.commit()
    return {"message": "History cleared"}

@app.get("/stats")
def get_stats(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    email = verify_token(credentials.credentials)
    stats = get_or_create_stats(db, email)
    return {"total_docs": stats.total_docs, "total_queries": stats.total_queries, "total_pages": stats.total_pages}
