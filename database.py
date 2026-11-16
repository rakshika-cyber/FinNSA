import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

DB_PATH = os.path.join(os.path.dirname(__file__), "finnsa_cache.db")

def init_db():
    """Initialize SQLite tables for sentiment cache and file uploads."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Sentiment cache table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sentiment_cache (
        text_hash TEXT PRIMARY KEY,
        english_text TEXT,
        hinglish_text TEXT,
        english_score REAL,
        english_label TEXT,
        hinglish_score REAL,
        hinglish_label TEXT,
        fused_score REAL,
        fused_direction TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Order intents (NOT routed to a broker; see routers/orders.py)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_intents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        side TEXT NOT NULL,
        order_type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        limit_price REAL,
        reference_price REAL NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Uploaded PDF reports table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS uploaded_reports (
        id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_size INTEGER,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Uploaded dataset references table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS uploaded_datasets (
        id TEXT PRIMARY KEY,
        name_or_url TEXT NOT NULL,
        is_file INTEGER DEFAULT 0,
        file_path TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()

def get_cached_sentiment(text_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached sentiment result by hash."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT english_score, english_label, hinglish_score, hinglish_label, fused_score, fused_direction 
        FROM sentiment_cache WHERE text_hash = ?
    """, (text_hash,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "english": {"score": row[0], "label": row[1]},
            "hinglish": {"score": row[2], "label": row[3]},
            "fused": {"bcgf_score": row[4], "direction": row[5]}
        }
    return None

def save_sentiment_cache(text_hash: str, eng_text: str, hing_text: str, 
                         eng_score: float, eng_label: str, 
                         hing_score: float, hing_label: str, 
                         fused_score: float, fused_dir: str):
    """Save calculated sentiment result to SQLite cache."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO sentiment_cache 
        (text_hash, english_text, hinglish_text, english_score, english_label, hinglish_score, hinglish_label, fused_score, fused_direction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (text_hash, eng_text, hing_text, eng_score, eng_label, hing_score, hing_label, fused_score, fused_dir))
    conn.commit()
    conn.close()

def save_report_meta(report_id: str, filename: str, file_path: str, file_size: int):
    """Save PDF report upload record."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO uploaded_reports (id, filename, file_path, file_size)
        VALUES (?, ?, ?, ?)
    """, (report_id, filename, file_path, file_size))
    conn.commit()
    conn.close()

def save_dataset_meta(dataset_id: str, name_or_url: str, is_file: bool, file_path: Optional[str] = None):
    """Save dataset upload / link record."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO uploaded_datasets (id, name_or_url, is_file, file_path)
        VALUES (?, ?, ?, ?)
    """, (dataset_id, name_or_url, 1 if is_file else 0, file_path))
    conn.commit()
    conn.close()
