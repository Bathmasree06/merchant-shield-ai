"""Reset and re-seed the demo dispute.

Run from the project root (the folder that contains the `app` folder):
    python scripts/seed_demo.py

Safe to run as many times as you like, for example before each video take.
"""

import asyncio
import pathlib
import sys
import time

# Make `import app...` work when this file lives in scripts/
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta

from app.ai.gemini import generate_ai_rebuttal
from app.db import Base, SessionLocal, engine
from app.models import AuditLog, Dispute, EvidenceItem, Order, Shipment
from app.services.eligibility import evaluate_dispute_eligibility

Base.metadata.create_all(bind=engine)

ORDER_ID = "ORD-DEMO-99"
DISPUTE_ID = "PP-D-DEMO-2026"
ADDRESS = {
    "line1": "123 Tech Lane",
    "city": "San Jose",
    "state": "CA",
    "postal_code": "95131",
    "country_code": "US",
}
# gemini.py returns this exact opening when Gemini fails and its fallback template is used
FALLBACK_START = (
    f"REBUTTAL FOR DISPUTE {DISPUTE_ID}\n\n"
    "The item was shipped and tracking confirms delivery."
)


def main():
    db = SessionLocal()
    try:
        # 1. Clear old demo data (children first)
        db.query(EvidenceItem).delete()
        db.query(Dispute).delete()
        db.query(Shipment).delete()
        db.query(Order).delete()
        db.commit()

        now = datetime.utcnow()

        # 2. Order
        order = Order(
            id=ORDER_ID,
            transaction_id="TXN-987654321",
            buyer_email="john@example.com",
            buyer_name="John Doe",
            shipping_address=ADDRESS,
            amount=149.99,
            currency="USD",
            status="SHIPPED",
        )
        db.add(order)
        db.commit()

        # 3. Shipment (simulated carrier data)
        shipment = Shipment(
            order_id=order.id,
            carrier="USPS",
            tracking_number="94001112024000000001",
            shipping_status="DELIVERED",
            shipped_at=now - timedelta(days=5),
            delivered_at=now - timedelta(days=2),
            recipient_name="John Doe",
            delivery_address=ADDRESS,
        )
        db.add(shipment)
        db.commit()

        # 4. Evidence item (simulated carrier lookup result)
        evidence = EvidenceItem(
            id="EV-1001",
            shipment_id=shipment.id,
            evidence_type="PROOF_OF_DELIVERY",
            extracted_data={
                "carrier": "USPS",
                "tracking_number": shipment.tracking_number,
                "delivery_status": "DELIVERED",
                "delivered_at": shipment.delivered_at.isoformat(),
                "recipient_name": "John Doe",
                "delivery_postal_code": "95131",
                "source": "simulated carrier lookup",
            },
        )
        db.add(evidence)
        db.commit()

        # 5. Dispute
        dispute = Dispute(
            id=DISPUTE_ID,
            order_id=order.id,
            reason="MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
            status="WAITING_FOR_SELLER_RESPONSE",
            dispute_amount=149.99,
            currency="USD",
            respond_by=now + timedelta(days=5),
        )
        db.add(dispute)
        db.commit()

        # 6. Rules engine returns (verdict, reasons, missing_evidence)
        verdict, reasons, missing = evaluate_dispute_eligibility(
            dispute, order, [shipment], [evidence]
        )
        print("Verdict :", verdict)
        print("Reasons :", reasons)
        print("Missing :", missing)

        dispute.verdict = verdict
        dispute.eligibility_reasons = {"reasons": reasons, "missing_evidence": missing}
        db.commit()

        # 7. Real Gemini call (async function, so we use asyncio.run)
        evidence_data = [
            {
                "evidence_id": evidence.id,
                "type": evidence.evidence_type,
                "details": evidence.extracted_data,
            }
        ]
        verdict_str = getattr(verdict, "value", str(verdict))

        draft = None
        for attempt in range(1, 4):
            text = asyncio.run(
                generate_ai_rebuttal(
                    dispute_id=dispute.id,
                    reason=dispute.reason,
                    amount=dispute.dispute_amount,
                    currency=dispute.currency,
                    verdict=verdict_str,
                    reasons=reasons,
                    evidence_data=evidence_data,
                )
            )
            if text and not text.startswith(FALLBACK_START):
                draft = text
                break
            print(
                f"Attempt {attempt}/3: Gemini did not return a real draft "
                "(bad key or rate limit). Waiting 20 seconds..."
            )
            time.sleep(20)

        if draft:
            dispute.ai_rebuttal_draft = draft
            db.add(
                AuditLog(
                    dispute_id=dispute.id,
                    action="AI_DRAFT_GENERATED",
                    details={"model": "gemini-2.5-flash", "verdict": verdict_str},
                )
            )
            db.commit()
            print("\nGemini draft saved.")
        else:
            print(
                "\nWARNING: no real Gemini draft was saved. Check GEMINI_API_KEY in .env "
                "and the error line printed above, wait a minute, then run this again."
            )

        print("\nStatus :", dispute.status)
        print("Draft saved:", bool(dispute.ai_rebuttal_draft))
        print("Done. Refresh http://127.0.0.1:8000 in your browser.")
    except Exception:
        db.rollback()
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
