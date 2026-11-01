import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app.models import Dispute, Order, Shipment, EvidenceItem


def generate_evidence_pdf(
    dispute: Dispute,
    order: Order,
    shipments: list,
    evidence_items: list,
    output_filename: str = None,
) -> str:
    """Generates an official PDF evidence packet for PayPal Dispute Submission."""
    if not output_filename:
        os.makedirs("generated_packets", exist_ok=True)
        output_filename = f"generated_packets/Evidence_Packet_{dispute.id}.pdf"

    # Printable page area: 612pt total width - 72pt margins = 540pt printable width
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=f"Evidence Packet - {dispute.id}",
        author="Merchant Shield AI",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1e3a8a"),
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "HeadingStyle",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#1f2937"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyStyle", parent=styles["Normal"], fontSize=9, leading=13
    )
    table_cell_style = ParagraphStyle(
        "TableCell", parent=styles["Normal"], fontSize=8, leading=11
    )
    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.white,
    )

    elements = []

    # Title Banner
    elements.append(Paragraph("MERCHANT DISPUTE DEFENSE PACKET", title_style))
    elements.append(
        Paragraph(
            f"Generated via Merchant Shield AI | Case Reference: <b>{dispute.id}</b>",
            body_style,
        )
    )
    elements.append(Spacer(1, 14))

    # Summary Table (Total width: 100 + 170 + 100 + 170 = 540pt)
    verdict_str = (
        dispute.verdict.value
        if hasattr(dispute.verdict, "value")
        else str(dispute.verdict or "STRONG")
    )
    summary_data = [
        [
            Paragraph("<b>Dispute ID</b>", table_cell_style),
            Paragraph(dispute.id, table_cell_style),
            Paragraph("<b>Claim Reason</b>", table_cell_style),
            Paragraph(dispute.reason, table_cell_style),
        ],
        [
            Paragraph("<b>Dispute Amount</b>", table_cell_style),
            Paragraph(
                f"${dispute.dispute_amount:.2f} {dispute.currency}", table_cell_style
            ),
            Paragraph("<b>Verdict</b>", table_cell_style),
            Paragraph(verdict_str, table_cell_style),
        ],
        [
            Paragraph("<b>Order ID</b>", table_cell_style),
            Paragraph(order.id if order else "N/A", table_cell_style),
            Paragraph("<b>Buyer Email</b>", table_cell_style),
            Paragraph(order.buyer_email if order else "N/A", table_cell_style),
        ],
    ]

    summary_table = Table(summary_data, colWidths=[90, 180, 90, 180])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 14))

    # Shipping Proof Table (Total width: 90 + 180 + 110 + 160 = 540pt)
    elements.append(Paragraph("1. Shipping & Carrier Verification", heading_style))
    if shipments:
        s = shipments[0]
        ship_data = [
            [
                Paragraph("<b>Carrier</b>", table_header_style),
                Paragraph("<b>Tracking Number</b>", table_header_style),
                Paragraph("<b>Status</b>", table_header_style),
                Paragraph("<b>Recipient Name</b>", table_header_style),
            ],
            [
                Paragraph(s.carrier, table_cell_style),
                Paragraph(s.tracking_number, table_cell_style),
                Paragraph(s.shipping_status, table_cell_style),
                Paragraph(s.recipient_name or "John Doe", table_cell_style),
            ],
        ]
        ship_table = Table(ship_data, colWidths=[90, 180, 110, 160])
        ship_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("PADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        elements.append(ship_table)
    elements.append(Spacer(1, 14))

    # AI Rebuttal Statement
    elements.append(Paragraph("2. Official Seller Rebuttal Statement", heading_style))
    rebuttal_text = (
        dispute.ai_rebuttal_draft
        or "Rebuttal submitted under PayPal Seller Protection."
    ).replace("\n", "<br/>")
    elements.append(Paragraph(rebuttal_text, body_style))

    doc.build(elements)
    return output_filename
