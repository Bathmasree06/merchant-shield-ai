import enum
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Text,
    Enum,
    JSON,
)
from sqlalchemy.orm import relationship
from app.db import Base


class VerdictType(str, enum.Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    INELIGIBLE = "INELIGIBLE"


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)  # PayPal Order ID
    transaction_id = Column(String, unique=True, index=True, nullable=True)
    buyer_email = Column(String, nullable=False)
    buyer_name = Column(String, nullable=True)
    shipping_address = Column(JSON, nullable=True)  # Stored as JSON dict
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    shipments = relationship("Shipment", back_populates="order")
    disputes = relationship("Dispute", back_populates="order")


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    carrier = Column(String, nullable=False)  # USPS, FEDEX, UPS, DHL
    tracking_number = Column(String, nullable=False, index=True)
    shipping_status = Column(
        String, default="SHIPPED"
    )  # SHIPPED, IN_TRANSIT, DELIVERED
    shipped_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)
    recipient_name = Column(String, nullable=True)
    delivery_address = Column(JSON, nullable=True)

    order = relationship("Order", back_populates="shipments")
    evidence_items = relationship("EvidenceItem", back_populates="shipment")


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id = Column(String, primary_key=True)  # e.g., EV-1001
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=True)
    evidence_type = Column(String, nullable=False)  # PROOF_OF_DELIVERY, RECEIPT, LOGS
    file_path = Column(String, nullable=True)
    extracted_data = Column(JSON, nullable=True)  # Output from Gemini vision
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    shipment = relationship("Shipment", back_populates="evidence_items")


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(String, primary_key=True)  # PayPal Dispute ID (e.g. PP-D-1234)
    order_id = Column(String, ForeignKey("orders.id"), nullable=True)
    reason = Column(String, nullable=False)  # MERCHANDISE_OR_SERVICE_NOT_RECEIVED, etc.
    status = Column(
        String, nullable=False
    )  # WAITING_FOR_SELLER_RESPONSE, UNDER_REVIEW, RESOLVED
    dispute_amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    respond_by = Column(DateTime, nullable=True)

    # Engine Analysis Fields
    verdict = Column(Enum(VerdictType), nullable=True)
    eligibility_reasons = Column(JSON, nullable=True)
    ai_rebuttal_draft = Column(Text, nullable=True)
    ai_tool_trace = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = relationship("Order", back_populates="disputes")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dispute_id = Column(String, nullable=True)
    action = Column(String, nullable=False)  # WEBHOOK_RECEIVED, AI_DRAFT_GENERATED
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
