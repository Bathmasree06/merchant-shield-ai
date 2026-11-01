🛡️ Merchant Shield AI

AI-Powered Dispute Defense Copilot for PayPal Merchants

Merchant Shield AI is an intelligent dispute management system designed to protect small-to-medium PayPal merchants from unfair chargebacks and payment disputes. By combining a deterministic Seller Protection rules engine with multimodal AI (Gemini 2.5 Flash), Merchant Shield AI automatically triages disputes within seconds, verifies evidence in a proactive vault, generates fact-grounded legal rebuttals, and compiles official PDF evidence packets for one-click submission.

📌 Problem & Solution

The Problem: Small businesses lose thousands of dollars annually in PayPal dispute claims because gathering tracking proof, evaluating complex Seller Protection rules, and drafting formal responses within strict deadlines (7–10 days) is overwhelming.

The Solution: Merchant Shield AI automates dispute triage, validates carrier delivery data against PayPal policy, uses Gemini to draft evidence-backed rebuttals, and gives merchants full control through a one-click human-in-the-loop approval workflow.

🏗️ Dual-Engine System Architecture

Merchant Shield AI separates deterministic policy enforcement from AI-driven document intelligence and text generation:

┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               MERCHANT SHIELD AI ARCHITECTURE                           │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                           │
  ┌────────────────────────────────────────┼────────────────────────────────────────┐
  ▼                                        ▼                                        ▼
┌──────────────────────────┐    ┌──────────────────────────┐    ┌──────────────────────────┐
│  PayPal API Integration  │    │   Deterministic Rules    │    │ Fact-Grounded Gemini AI  │
│ Webhooks (HMAC Verified) │    │ Evaluates deadlines,     │    │ Extracts receipt proof,  │
│ Disputes API & Tokenizer │ ─> │ tracking status & address│ ─> │ drafts rebuttal citing   │
│ Proactive Evidence Vault │    │ alignment automatically  │    │ verified evidence IDs    │
└──────────────────────────┘    └──────────────────────────┘    └──────────────────────────┘
                                                                             │
                                                                             ▼
                                                                ┌──────────────────────────┐
                                                                │  Human Approval Gate     │
                                                                │ Merchant reviews, edits, │
                                                                │ & generates PDF packet   │
                                                                └──────────────────────────┘



Code (Deterministic Rules Engine): Handles strict policy logic—verifying shipping deadlines, carrier delivery statuses, and postal code alignment against PayPal's Seller Protection guidelines.

AI (Gemini 2.5 Flash): Performs multimodal document processing on shipping receipts and drafts professional seller rebuttals grounded only in verified database evidence IDs (zero hallucinations).

Human-in-the-Loop Gate: Merchants retain complete control to review, edit, and approve submissions via a single click before PDF generation and status updates.

🚀 Key Features

⚡ Instant Webhook Ingestion: Real-time event handling for CUSTOMER.DISPUTE.CREATED, UPDATED, and RESOLVED webhooks with signature verification and idempotency protection.

🛡️ Automated Triage & Verdict: Calculates eligibility (STRONG FIGHT, MODERATE, WEAK, INELIGIBLE) instantly upon dispute receipt.

📦 Proactive Evidence Vault: Automatically links orders, carrier tracking (USPS/UPS/FedEx), and proof of delivery at fulfillment time.

📄 ReportLab PDF Packet Generation: Automatically builds formatted, submission-ready PDF evidence packets with document title metadata.

📊 Impact Dashboard: Track total disputes handled, total money at stake, and response metrics in real time.

🛠️ Tech Stack

Backend: Python 3.11, FastAPI, Uvicorn, SQLAlchemy, SQLite

Frontend: Jinja2 Templates, Tailwind CSS (via CDN)

AI Model: Google Gemini 2.5 Flash (google-genai SDK)

PayPal Integration: PayPal REST API (Disputes API, OAuth 2.0, Webhook Signature Verification)

PDF Generation: ReportLab

Local Tunneling: ngrok

🚦 Getting Started

Prerequisites

Python 3.11 or higher

PayPal Developer Sandbox Account (developer.paypal.com)

Google AI Studio Gemini API Key (aistudio.google.com)

Installation

Clone the repository:

git clone https://github.com/your-username/merchant-shield-ai.git
cd merchant-shield-ai



Create and activate virtual environment:

# On macOS/Linux:
python3 -m venv venv
source venv/bin/activate

# On Windows (PowerShell):
python -m venv venv
.\venv\Scripts\Activate.ps1



Install dependencies:

pip install -r requirements.txt



Configure Environment Variables:
Create a .env file in the root directory (copy from .env.example):

PAYPAL_CLIENT_ID=your_paypal_sandbox_client_id
PAYPAL_SECRET=your_paypal_sandbox_secret
PAYPAL_MODE=sandbox
PAYPAL_WEBHOOK_ID=your_paypal_webhook_id
GEMINI_API_KEY=your_gemini_api_key
SECRET_KEY=dev_secret_key_merchant_shield
DATABASE_URL=sqlite:///./merchant_shield.db



Run Application:

uvicorn app.main:app --reload



Open your browser to http://127.0.0.1:8000 to view the merchant dashboard.

🧪 Quick Demo Walkthrough & Testing

Seed Test Order & Evidence Vault:

Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8000/seed-test-data"



Trigger Mock Dispute:

Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8000/test-trigger-dispute"



Evaluate Eligibility:

Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:8000/test-eligibility"



Generate AI Rebuttal:

Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:8000/test-ai-rebuttal"



Review in Browser:
Visit http://127.0.0.1:8000/, click Review Case →, edit or review the rebuttal draft, and click Approve & Submit Evidence to PayPal to generate the PDF packet!

📜 License

This project is licensed under the MIT License - see the LICENSE file for details.