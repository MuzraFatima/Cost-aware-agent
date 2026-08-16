import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import List, Optional

class Base(DeclarativeBase):
    pass

class RoutingLog(Base):
    __tablename__ = "routing_logs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_frontier_cost: Mapped[float] = mapped_column(Float, default=0.0)
    cost_savings: Mapped[float] = mapped_column(Float, default=0.0)
    budget_limit_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    final_tier: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    eval_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    steps: Mapped[List["RoutingStep"]] = relationship(
        "RoutingStep", back_populates="routing_log", cascade="all, delete-orphan", lazy="selectin"
    )

class RoutingStep(Base):
    __tablename__ = "routing_steps"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    routing_log_id: Mapped[str] = mapped_column(ForeignKey("routing_logs.id", ondelete="CASCADE"), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    routing_log: Mapped["RoutingLog"] = relationship("RoutingLog", back_populates="steps")

class RoutingPolicy(Base):
    __tablename__ = "routing_policies"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    min_confidence_threshold: Mapped[float] = mapped_column(Float, default=0.70)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
