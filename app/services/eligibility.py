from datetime import datetime
from typing import Dict, Any, List, Tuple
from app.models import Order, Shipment, EvidenceItem, Dispute, VerdictType


def evaluate_dispute_eligibility(
    dispute: Dispute,
    order: Order,
    shipments: List[Shipment],
    evidence_items: List[EvidenceItem],
) -> Tuple[VerdictType, List[str], List[str]]:
    """
    Evaluates dispute seller protection eligibility based on standard PayPal rules.
    Returns: (VerdictType, reasons_list, missing_evidence_list)
    """
    reasons: List[str] = []
    missing_evidence: List[str] = []

    # 1. Deadline Check
    if dispute.respond_by and datetime.utcnow() > dispute.respond_by:
        return (
            VerdictType.INELIGIBLE,
            ["Dispute response deadline has expired."],
            [],
        )

    # 2. Check Order & Tracking Availability
    if not shipments:
        reasons.append("No shipping records found for this order in vault.")
        missing_evidence.append("PROOF_OF_SHIPMENT")
        return VerdictType.WEAK, reasons, missing_evidence

    primary_shipment = shipments[0]

    # 3. Handle 'Item Not Received' (INR) Disputes
    if dispute.reason in [
        "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
        "ITEM_NOT_RECEIVED",
    ]:
        if primary_shipment.shipping_status != "DELIVERED":
            reasons.append("Tracking status is not yet marked as DELIVERED.")
            missing_evidence.append("PROOF_OF_DELIVERY")
            verdict = VerdictType.MODERATE
        else:
            reasons.append(
                f"Valid carrier tracking ({primary_shipment.carrier}: {primary_shipment.tracking_number}) confirms delivery."
            )
            verdict = VerdictType.STRONG

        # Check Address Alignment
        order_addr = order.shipping_address or {}
        ship_addr = primary_shipment.delivery_address or {}
        if order_addr.get("postal_code") and ship_addr.get("postal_code"):
            if order_addr.get("postal_code") != ship_addr.get("postal_code"):
                reasons.append(
                    "Delivery postal code does not match order shipping address."
                )
                verdict = VerdictType.MODERATE

    # 4. Handle 'Significantly Not as Described' (SNAD) Disputes
    elif dispute.reason in [
        "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED",
        "SNAD",
    ]:
        reasons.append(
            "SNAD disputes require product description proof and item condition photos."
        )
        missing_evidence.append("ITEM_CONDITION_PHOTOS")
        verdict = VerdictType.MODERATE

    # Default fallback
    else:
        reasons.append("Standard claim requiring order transaction logs.")
        verdict = VerdictType.MODERATE

    # 5. Verify Evidence Vault Attachments
    has_pod = any(e.evidence_type == "PROOF_OF_DELIVERY" for e in evidence_items)
    if not has_pod and "PROOF_OF_DELIVERY" not in missing_evidence:
        missing_evidence.append("PROOF_OF_DELIVERY")

    return verdict, reasons, missing_evidence
