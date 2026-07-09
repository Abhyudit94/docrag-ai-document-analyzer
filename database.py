from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# SQLite permanent database
import os
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./docrag.db")
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ── MODELS ────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=False)
    email      = Column(String, unique=True, index=True, nullable=False)
    password   = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"
    id         = Column(Integer, primary_key=True, index=True)
    doc_id     = Column(String, unique=True, index=True)
    user_email = Column(String, index=True)
    filename   = Column(String)
    pages      = Column(Integer)
    size_kb    = Column(Float)
    summary    = Column(Text)
    points     = Column(Text)   # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id         = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, index=True)
    question   = Column(Text)
    answer     = Column(Text)
    sources    = Column(Text)   # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)

class Stats(Base):
    __tablename__ = "stats"
    id            = Column(Integer, primary_key=True, index=True)
    user_email    = Column(String, unique=True, index=True)
    total_docs    = Column(Integer, default=0)
    total_queries = Column(Integer, default=0)
    total_pages   = Column(Integer, default=0)

# Create all tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
