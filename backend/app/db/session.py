from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker, Session
from backend.app.core.config import settings
from backend.app.db.models import Base, RoutingPolicy
from typing import Generator

# Create sync database engine
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

# Sync Session Factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# FastAPI DB dependency
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def _migrate_columns(conn) -> None:
    """
    Adds new columns to routing_logs if they don't already exist.
    SQLite doesn't support IF NOT EXISTS on ALTER TABLE, so we check
    the PRAGMA column list first.
    """
    existing = {row[1] for row in conn.execute(text("PRAGMA table_info(routing_logs)"))}
    migrations = [
        ("estimated_frontier_cost", "REAL DEFAULT 0.0"),
        ("cost_savings",            "REAL DEFAULT 0.0"),
        ("budget_limit_usd",        "REAL"),
    ]
    for col_name, col_def in migrations:
        if col_name not in existing:
            conn.execute(text(f"ALTER TABLE routing_logs ADD COLUMN {col_name} {col_def}"))

# Database initialization
def init_db() -> None:
    # Create all tables if they don't exist
    Base.metadata.create_all(bind=engine)

    # Apply any new column migrations
    with engine.begin() as conn:
        _migrate_columns(conn)
        
    # Populate default thresholds if empty
    db = SessionLocal()
    try:
        existing_policies = db.execute(select(RoutingPolicy)).scalars().all()
        if not existing_policies:
            for domain, threshold in settings.DEFAULT_THRESHOLDS.items():
                policy = RoutingPolicy(
                    domain=domain,
                    min_confidence_threshold=threshold
                )
                db.add(policy)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()
