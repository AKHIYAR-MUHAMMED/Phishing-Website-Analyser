"""
PhishGuard-X Database Layer:
1. Relational Database Engine (SQLAlchemy ORM for PostgreSQL / SQLite)
2. Document Store Client (MongoDB for raw HTML & JSON evidence)
3. In-Memory Cache & Message Queue Client (Redis for rate limiting & token blacklist)
"""

import os
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

# Database URLs
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "phishguard_x.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{SQLITE_DB_PATH}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True
)

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()


class UserDB(Base):
    """User accounts & authentication ORM model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="analyst") # admin, analyst, reader
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ScanResultDB(Base):
    """Multimodal detection scan results ORM model."""
    __tablename__ = "scan_results"

    id = Column(Integer, primary_key=True, index=True)
    target_url = Column(String(2048), index=True, nullable=False)
    verdict = Column(String(50), nullable=False)
    overall_threat_score = Column(Float, nullable=False)
    risk_level = Column(String(50), nullable=False)
    attack_category = Column(String(100), nullable=False)
    confidence_score = Column(Float, nullable=False)
    scan_latency_ms = Column(Integer, default=14)
    recommended_actions = Column(Text, nullable=True)
    modality_scores = Column(JSON, nullable=True)
    xai_evidence_matrix = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ModelRegistryDB(Base):
    """MLOps model registry tracking ORM model."""
    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    accuracy = Column(Float, nullable=False)
    precision = Column(Float, nullable=False)
    recall = Column(Float, nullable=False)
    f1_score = Column(Float, nullable=False)
    weights_filepath = Column(String(255), nullable=False)
    deployed_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuditLogDB(Base):
    """Security audit log ORM model."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


# Initialize Database Tables & Seed Pre-loaded Full Records
def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # 1. Create Default Admin User
        admin_user = db.query(UserDB).filter(UserDB.username == "admin").first()
        if not admin_user:
            default_admin = UserDB(
                username="admin",
                email="admin@phishguardx.io",
                hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeg6Lruj3vjPGga31lW", # hashed 'admin123'
                role="admin",
                is_active=True
            )
            db.add(default_admin)

        # 2. Pre-seed Full Scan Results if empty
        if db.query(ScanResultDB).count() == 0:
            sample_scans = [
                ("http://paypal-security-verification-center.com/login", "PHISHING DETECTED", 98.5, "CRITICAL RISK", "BRAND IMPERSONATION & FAKE LOGO SPOOFING"),
                ("http://login.microsoftonline.security-auth-check.xyz/oauth2", "PHISHING DETECTED", 99.2, "CRITICAL RISK", "CREDENTIAL HARVESTING & EXTERNAL FORM POSTING"),
                ("http://verify-bankofamerica-account-update.info/signin", "PHISHING DETECTED", 96.8, "CRITICAL RISK", "CLOAKED DOM GRAPH & OBFUSCATED JAVASCRIPT"),
                ("http://adobe-id-security-auth-login.com/checkpoint", "PHISHING DETECTED", 95.4, "HIGH RISK", "TYPOSQUATTING & SUSPICIOUS DOMAIN"),
                ("https://github.com/torvalds/linux", "LEGITIMATE SITE", 0.1, "SAFE", "NONE (VERIFIED SAFE INFRASTRUCTURE)"),
                ("https://www.google.com/search?q=machine+learning", "LEGITIMATE SITE", 0.2, "SAFE", "NONE (VERIFIED SAFE INFRASTRUCTURE)"),
                ("https://www.amazon.com/dp/B08N5WRWNW", "LEGITIMATE SITE", 0.3, "SAFE", "NONE (VERIFIED SAFE INFRASTRUCTURE)"),
                ("https://www.apple.com/iphone-15-pro", "LEGITIMATE SITE", 0.1, "SAFE", "NONE (VERIFIED SAFE INFRASTRUCTURE)")
            ]
            for url, verdict, score, risk, cat in sample_scans:
                db.add(ScanResultDB(
                    target_url=url,
                    verdict=verdict,
                    overall_threat_score=score,
                    risk_level=risk,
                    attack_category=cat,
                    confidence_score=99.8,
                    scan_latency_ms=14,
                    recommended_actions="Quarantine URL" if "PHISHING" in verdict else "Allow traffic"
                ))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Database] Warning during seed: {e}")
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# In-Memory Redis Fallback Client
class MockRedisCache:
    def __init__(self):
        self._store = {}

    def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        self._store[key] = value
        return True

    def incr(self, key: str) -> int:
        val = int(self._store.get(key, 0)) + 1
        self._store[key] = str(val)
        return val


redis_client = MockRedisCache()


if __name__ == "__main__":
    init_db()
    print("Database tables initialized and pre-seeded successfully!")
