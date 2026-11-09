import logging
import os
import json
from datetime import datetime, timedelta
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    BackgroundTasks,
    Form,
    status,
)
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, engine, get_db, SessionLocal
from app.models import Order, Shipment, EvidenceItem, Dispute, AuditLog, VerdictType
from app.paypal.client import paypal_client
from app.paypal.webhooks import verify_webhook_signature
from app.services.eligibility import evaluate_dispute_eligibility
from app.services.packet import generate_evidence_pdf
from app.ai.gemini import generate_ai_rebuttal

# Initialize Database Tables
Base.metadata.create_all(bind=engine)

logger = logging.getLogger("merchant_shield")

app = FastAPI(
    title="Merchant Shield AI",
    description="AI dispute defense copilot for PayPal merchants",
    version="1.0.0",
)

templates = Jinja2Templates(directory="app/templates")


# Middleware for ngrok Interstitial Header Bypass
@app.middleware("http")
async def add_ngrok_skip_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["ngrok-skip-browser-warning"] = "1"
    return response


async def process_dispute_event(event_data: dict, db_session_factory):
    """Background task: Fetches detailed dispute data and logs audit trail."""
    db = db_session_factory()
    try:
        resource = event_data.get("resource", {})
        dispute_id = resource.get("dispute_id") or resource.get("id")
        event_type = event_data.get("event_type")

        if not dispute_id:
            return

        # Fetch latest full dispute payload directly from PayPal Disputes API
        try:
            dispute_detail = await paypal_client.request(
                "GET", f"/v1/customer/disputes/{dispute_id}"
            )
        except Exception as err:
            logger.warning(
                f"Could not fetch full dispute details for {dispute_id}: {err}"
            )
            dispute_detail = resource

        # Parse dispute fields safely
        dispute_amount_obj = dispute_detail.get("dispute_amount", {})
        amount = float(dispute_amount_obj.get("value", 0.0))
        currency = dispute_amount_obj.get("currency_code", "USD")
        reason = dispute_detail.get("reason", "UNKNOWN_REASON")
        dispute_status = dispute_detail.get("status", "WAITING_FOR_SELLER_RESPONSE")

        respond_by_str = dispute_detail.get("seller_response_due_date")
        respond_by_dt = None
        if respond_by_str:
            try:
                respond_by_dt = datetime.fromisoformat(
                    respond_by_str.replace("Z", "+00:00")
                )
            except Exception:
                pass

        # Upsert dispute into DB
        dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
        if not dispute:
            dispute = Dispute(
                id=dispute_id,
                reason=reason,
                status=dispute_status,
                dispute_amount=amount,
                currency=currency,
                respond_by=respond_by_dt,
            )
            db.add(dispute)
        else:
            dispute.status = dispute_status
            dispute.updated_at = datetime.utcnow()

        # Add Audit Log entry
        audit = AuditLog(
            dispute_id=dispute_id,
            action=f"WEBHOOK_{event_type}",
            details={"status": dispute_status, "amount": amount, "reason": reason},
        )
        db.add(audit)
        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing background dispute webhook: {e}")
    finally:
        db.close()


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "mode": settings.PAYPAL_MODE,
        "paypal_configured": bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_SECRET),
        "gemini_configured": bool(settings.GEMINI_API_KEY),
    }


@app.get("/test-paypal-token")
async def test_paypal_token():
    try:
        token = await paypal_client.get_access_token()
        return {
            "status": "success",
            "token_preview": f"{token[:15]}...",
            "message": "Successfully authenticated with PayPal Sandbox API!",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhooks/paypal")
async def paypal_webhook_handler(
    request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    body_bytes = await request.body()

    # The simulator header skips signature checks, so it is OFF unless you turn it on
    # explicitly (add `ALLOW_SIMULATOR: bool = False` to Settings and set it in .env).
    allow_simulator = bool(getattr(settings, "ALLOW_SIMULATOR", False))
    is_simulator = (
        allow_simulator
        and request.headers.get("paypal-transmission-id") == "SIMULATOR"
    )

    if settings.PAYPAL_WEBHOOK_ID and not is_simulator:
        is_valid = await verify_webhook_signature(
            request, body_bytes, settings.PAYPAL_WEBHOOK_ID
        )
        if not is_valid:
            raise HTTPException(
                status_code=400, detail="Invalid PayPal Webhook Signature"
            )

    try:
        event_data = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_id = event_data.get("id", "SIMULATED_EVENT")
    event_type = event_data.get("event_type", "CUSTOMER.DISPUTE.CREATED")

    audit = AuditLog(
        action=f"RECEIVED_{event_type}",
        details={"event_id": event_id, "event_type": event_type},
    )
    db.add(audit)
    db.commit()

    background_tasks.add_task(process_dispute_event, event_data, SessionLocal)
    return {"status": "accepted", "event_id": event_id}


@app.post("/test-trigger-dispute")
async def trigger_mock_dispute(db: Session = Depends(get_db)):
    """Manually creates a dispute record in the DB for local testing."""
    dispute_id = "PP-D-DEMO-2026"
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()

    if not dispute:
        dispute = Dispute(
            id=dispute_id,
            order_id="ORD-DEMO-99",
            reason="MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
            status="WAITING_FOR_SELLER_RESPONSE",
            dispute_amount=149.99,
            currency="USD",
            respond_by=datetime.utcnow() + timedelta(days=7),
        )
        db.add(dispute)

    audit = AuditLog(
        dispute_id=dispute_id,
        action="MANUAL_DISPUTE_TRIGGERED",
        details={"reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED", "amount": 149.99},
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "dispute_id": dispute_id,
        "message": "Demo dispute successfully initialized in DB!",
    }


@app.get("/test-eligibility")
async def test_eligibility_engine(db: Session = Depends(get_db)):
    """Tests the eligibility engine against demo seeded database records."""
    order = db.query(Order).filter(Order.id == "ORD-DEMO-99").first()
    dispute = db.query(Dispute).filter(Dispute.id == "PP-D-DEMO-2026").first()

    if not order or not dispute:
        raise HTTPException(
            status_code=404,
            detail="Seeded order or dispute not found. Run python scripts/seed_demo.py first.",
        )

    shipments = db.query(Shipment).filter(Shipment.order_id == order.id).all()
    evidence = (
        db.query(EvidenceItem)
        .filter(EvidenceItem.shipment_id.in_([s.id for s in shipments]))
        .all()
    )

    verdict, reasons, missing = evaluate_dispute_eligibility(
        dispute, order, shipments, evidence
    )

    dispute.verdict = verdict
    dispute.eligibility_reasons = {"reasons": reasons, "missing_evidence": missing}
    db.commit()

    return {
        "status": "success",
        "dispute_id": dispute.id,
        "verdict": verdict.value,
        "reasons": reasons,
        "missing_evidence": missing,
    }


@app.get("/test-ai-rebuttal")
async def test_ai_rebuttal(db: Session = Depends(get_db)):
    """Tests Gemini AI draft rebuttal generation."""
    dispute = db.query(Dispute).filter(Dispute.id == "PP-D-DEMO-2026").first()
    order = db.query(Order).filter(Order.id == "ORD-DEMO-99").first()

    if not dispute or not order:
        raise HTTPException(
            status_code=404,
            detail="Demo dispute or order not found.",
        )

    evidence_items = (
        db.query(EvidenceItem)
        .join(Shipment)
        .filter(Shipment.order_id == order.id)
        .all()
    )

    evidence_data = [
        {
            "evidence_id": item.id,
            "type": item.evidence_type,
            "details": item.extracted_data,
        }
        for item in evidence_items
    ]

    reasons = (dispute.eligibility_reasons or {}).get("reasons", [])
    verdict_str = dispute.verdict.value if dispute.verdict else "STRONG"

    draft = await generate_ai_rebuttal(
        dispute_id=dispute.id,
        reason=dispute.reason,
        amount=dispute.dispute_amount,
        currency=dispute.currency,
        verdict=verdict_str,
        reasons=reasons,
        evidence_data=evidence_data,
    )

    dispute.ai_rebuttal_draft = draft
    db.commit()

    return {
        "status": "success",
        "dispute_id": dispute.id,
        "ai_rebuttal_draft": draft,
    }


@app.get("/", response_class=HTMLResponse)
async def render_dashboard(request: Request, db: Session = Depends(get_db)):
    """Renders main Merchant Shield case queue dashboard."""
    disputes = db.query(Dispute).order_by(Dispute.created_at.desc()).all()
    total_disputes = len(disputes)
    total_amount = sum(d.dispute_amount for d in disputes)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "disputes": disputes,
            "total_disputes": total_disputes,
            "total_amount": total_amount,
        },
    )


@app.get("/cases/{dispute_id}", response_class=HTMLResponse)
async def render_case_detail(
    dispute_id: str, request: Request, db: Session = Depends(get_db)
):
    """Renders detailed dispute view for review and approval."""
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute case not found")

    return templates.TemplateResponse(
        request=request,
        name="case.html",
        context={"dispute": dispute},
    )


@app.post("/cases/{dispute_id}/submit")
async def submit_dispute_approval(
    dispute_id: str,
    request: Request,
    rebuttal_text: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Human approval: saves edits, builds the PDF packet, then submits to PayPal."""
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute case not found")

    # Keep the merchant's edits from the textarea
    if rebuttal_text:
        dispute.ai_rebuttal_draft = rebuttal_text

    order = (
        db.query(Order).filter(Order.id == dispute.order_id).first()
        if dispute.order_id
        else None
    )
    shipments = (
        db.query(Shipment).filter(Shipment.order_id == dispute.order_id).all()
        if dispute.order_id
        else []
    )
    # Only the evidence that belongs to this dispute's order
    evidence_items = (
        db.query(EvidenceItem)
        .join(Shipment, EvidenceItem.shipment_id == Shipment.id)
        .filter(Shipment.order_id == dispute.order_id)
        .all()
        if dispute.order_id
        else []
    )

    pdf_path = generate_evidence_pdf(dispute, order, shipments, evidence_items)

    is_demo_case = dispute.id.startswith("PP-D-DEMO")
    success_message = None
    error_message = None
    new_status = None
    submitted_to_paypal = False

    if is_demo_case:
        # Seeded case: PayPal has no such dispute, so we do not pretend to send it.
        new_status = "UNDER_REVIEW"
        success_message = (
            "Demo case: evidence packet built and approved locally. "
            "This seeded dispute does not exist at PayPal, so nothing was sent."
        )
    else:
        shipment = shipments[0] if shipments else None
        try:
            await paypal_client.provide_evidence(
                dispute_id=dispute.id,
                evidence_type="PROOF_OF_FULFILLMENT",
                notes=dispute.ai_rebuttal_draft or "",
                carrier_name=shipment.carrier if shipment else None,
                tracking_number=shipment.tracking_number if shipment else None,
                pdf_path=pdf_path,
            )
            submitted_to_paypal = True
            new_status = "UNDER_REVIEW"
            success_message = "Evidence submitted to PayPal through the Disputes API."
        except Exception as exc:  # noqa: BLE001
            logger.error(f"PayPal provide-evidence failed for {dispute.id}: {exc}")
            error_message = f"PayPal did not accept the evidence: {exc}"

    if new_status:
        dispute.status = new_status

    db.add(
        AuditLog(
            dispute_id=dispute.id,
            action="HUMAN_APPROVED_SUBMISSION",
            details={
                "status": dispute.status,
                "pdf_generated": pdf_path,
                "demo_case": is_demo_case,
                "submitted_to_paypal": submitted_to_paypal,
                "error": error_message,
            },
        )
    )
    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="case.html",
        context={
            "dispute": dispute,
            "success_message": success_message,
            "error_message": error_message,
            "pdf_path": pdf_path,
        },
    )


@app.get("/download-packet/{dispute_id}")
async def download_evidence_packet(dispute_id: str):
    """Downloads the generated PDF evidence packet."""
    filename = f"generated_packets/Evidence_Packet_{dispute_id}.pdf"
    if not os.path.exists(filename):
        raise HTTPException(status_code=404, detail="PDF Evidence packet not found.")
    return FileResponse(
        path=filename,
        filename=f"Evidence_Packet_{dispute_id}.pdf",
        media_type="application/pdf",
    )