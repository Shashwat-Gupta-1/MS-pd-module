import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from jinja2 import Template
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.application import Application
from app.models.applicant import Applicant
from sqlalchemy import or_
from app.models.pd_session import PDSession
from app.models.extracted_field import ExtractedField
from app.models.bre_preliminary_calc import BREPreliminaryCalc
from app.models.customer_consistency_flag import CustomerConsistencyFlag
from app.models.officer_pd_score import OfficerPDScore
from app.models.officer_remark import OfficerRemark
from app.models.ground_pd_photo import GroundPDPhoto
from app.models.photo_extraction import PhotoExtraction
from app.models.asset_valuation import AssetValuation
from app.models.business_estimate import BusinessEstimate
from app.calculations.emi_foir_ltv import calculate_emi, calculate_foir, calculate_ltv
from app.utils.pii_masking import mask_pii
from app.agents.report_narrative import generate_narrative_section

logger = logging.getLogger(__name__)

REPORT_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>MSFincap — Credit Assessment Memorandum (CAM)</title>
  <style>
    body { font-family: 'Helvetica Neue', Arial, sans-serif; margin: 40px; color: #1e293b; line-height: 1.5; }
    h1 { color: #0f172a; border-bottom: 2px solid #2563eb; padding-bottom: 8px; font-size: 24px; }
    h2 { color: #1e40af; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px; margin-top: 24px; font-size: 18px; }
    .header-table, .data-table { width: 100%; border-collapse: collapse; margin-top: 12px; margin-bottom: 16px; }
    .data-table th, .data-table td { border: 1px solid #cbd5e1; padding: 8px 12px; text-align: left; font-size: 13px; }
    .data-table th { background-color: #f1f5f9; font-weight: 600; color: #334155; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
    .badge-approved { background-color: #dcfce7; color: #15803d; }
    .badge-review { background-color: #fef9c3; color: #a16207; }
    .badge-high { background-color: #fee2e2; color: #b91c1c; }
    .badge-bonus { background-color: #dbeafe; color: #1d4ed8; }
    .narrative-box { background: #f8fafc; border-left: 4px solid #2563eb; padding: 12px 16px; margin: 12px 0; font-size: 13px; }
    .internal-box { background: #fef2f2; border: 1px dashed #ef4444; padding: 12px; border-radius: 6px; margin-top: 16px; }
  </style>
</head>
<body>
  <h1>MSFincap — Credit Assessment Memorandum (CAM)</h1>
  
  <table class="header-table">
    <tr>
      <td><strong>Case Number:</strong> {{ case_number }}</td>
      <td><strong>Application ID:</strong> {{ application_id }}</td>
      <td><strong>Date:</strong> {{ date_str }}</td>
    </tr>
    <tr>
      <td><strong>Applicant:</strong> {{ applicant_name }}</td>
      <td><strong>Phone:</strong> {{ applicant_phone }}</td>
      <td><strong>PAN:</strong> {{ applicant_pan }}</td>
    </tr>
    <tr>
      <td><strong>Employment Type:</strong> {{ employment_type }}</td>
      <td><strong>Sub-Profile:</strong> {{ sub_profile }}</td>
      <td><strong>Loan Type:</strong> {{ loan_type }}</td>
    </tr>
  </table>

  <h2>1. Executive Summary & Recommendation</h2>
  <table class="data-table">
    <tr>
      <th>Requested Loan Amount</th>
      <td>Rs. {{ requested_amount }}</td>
      <th>Proposed Tenure</th>
      <td>{{ tenure_months }} Months</td>
    </tr>
    <tr>
      <th>Calculated EMI</th>
      <td>Rs. {{ proposed_emi }}</td>
      <th>Final FOIR</th>
      <td>{{ final_foir }}%</td>
    </tr>
    <tr>
      <th>Final LTV</th>
      <td>{{ final_ltv if final_ltv is not none else 'N/A (Unsecured)' }}%</td>
      <th>BRE System Recommendation</th>
      <td><span class="badge badge-approved">{{ bre_recommendation }}</span></td>
    </tr>
  </table>

  <h2>2. Business & Physical Verification Overview</h2>
  <div class="narrative-box">
    {{ business_overview }}
  </div>

  <h2>3. Financial Assessment Narrative</h2>
  <div class="narrative-box">
    {{ financial_overview }}
  </div>

  <h2>4. Verified Ground Extracted Data</h2>
  <table class="data-table">
    <thead>
      <tr>
        <th>Field Name</th>
        <th>Extracted Value</th>
        <th>Capture Source</th>
        <th>Officer Reconfirmed</th>
      </tr>
    </thead>
    <tbody>
      {% for field in extracted_fields %}
      <tr>
        <td>{{ field.name }}</td>
        <td>{{ field.value }}</td>
        <td>{{ field.source | upper }}</td>
        <td>{{ 'Yes' if field.confirmed else 'Pending' }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <h2>5. Customer Consistency & Contradiction Audit</h2>
  {% if consistency_flags %}
  <table class="data-table">
    <thead>
      <tr>
        <th>Field / Topic</th>
        <th>Statement A</th>
        <th>Statement B</th>
        <th>Severity</th>
        <th>Resolution / Explanation</th>
      </tr>
    </thead>
    <tbody>
      {% for flag in consistency_flags %}
      <tr>
        <td>{{ flag.field_name }}</td>
        <td>{{ flag.value_a }}</td>
        <td>{{ flag.value_b }}</td>
        <td><span class="badge badge-high">{{ flag.severity | upper }}</span></td>
        <td>{{ flag.resolution_note or 'Unresolved discrepancy' }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p>No customer contradictions detected across interview statements.</p>
  {% endif %}

  <h2>6. Ground Verification Photos & GPS Tightness</h2>
  <table class="data-table">
    <thead>
      <tr>
        <th>Photo Category</th>
        <th>GPS Latitude</th>
        <th>GPS Longitude</th>
        <th>Verification Status</th>
      </tr>
    </thead>
    <tbody>
      {% for photo in photos %}
      <tr>
        <td>{{ photo.category }}</td>
        <td>{{ photo.lat }}</td>
        <td>{{ photo.lng }}</td>
        <td>Captured On-Site</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  {% if physical_assets or business_estimate %}
  <h2>6b. Physical Assets & Valuation (Agent 3 Vision Audit)</h2>
  {% if business_estimate %}
  <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; padding:12px; margin-bottom:15px;">
    <strong>Premises Valuation Summary:</strong>
    Estimated Stock: ₹{{ "{:,.0f}".format(business_estimate.estimated_stock_value) }} |
    Estimated Machinery: ₹{{ "{:,.0f}".format(business_estimate.estimated_machinery_value) }} |
    Total Physical Assets: ₹{{ "{:,.0f}".format(business_estimate.total_physical_assets_min) }} - ₹{{ "{:,.0f}".format(business_estimate.total_physical_assets_max) }}<br/>
    <small>Income Consistency: <strong>{{ business_estimate.consistency_with_declared_income }}</strong> | Activity: <strong>{{ business_estimate.activity_level }}</strong> | {{ business_estimate.justification }}</small>
  </div>
  {% endif %}
  {% if physical_assets %}
  <table class="data-table">
    <thead>
      <tr>
        <th>Category</th>
        <th>Detected Asset</th>
        <th>Count</th>
        <th>Condition</th>
        <th>Unit Value Range (INR)</th>
        <th>Total Value Range (INR)</th>
      </tr>
    </thead>
    <tbody>
      {% for asset in physical_assets %}
      <tr>
        <td>{{ asset.category }}</td>
        <td><strong>{{ asset.item_name }}</strong></td>
        <td>{{ asset.total_count }}</td>
        <td>{{ asset.condition }}</td>
        <td>₹{{ "{:,.0f}".format(asset.unit_value_min_inr) }} - ₹{{ "{:,.0f}".format(asset.unit_value_max_inr) }}</td>
        <td>₹{{ "{:,.0f}".format(asset.total_value_min_inr) }} - ₹{{ "{:,.0f}".format(asset.total_value_max_inr) }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% endif %}
  {% endif %}

  <h2>7. Qualitative Officer Remarks</h2>
  <div class="narrative-box">
    {{ officer_remarks or 'No qualitative remarks recorded.' }}
  </div>

  <div class="internal-box">
    <h3 style="margin-top:0; color:#b91c1c;">Internal Underwriter Quality Metrics (Do Not Disclose to Borrower)</h3>
    <table class="data-table">
      <tr>
        <th>Questionnaire Coverage</th>
        <td>{{ officer_coverage_score }}%</td>
        <th>Follow-up Uptake</th>
        <td>{{ officer_uptake_score }}%</td>
      </tr>
      <tr>
        <th>Photo Diligence</th>
        <td>{{ officer_photo_score }}%</td>
        <th>Proactive Diligence Bonus</th>
        <td><span class="badge badge-bonus">+{{ officer_proactive_bonus }} Points</span></td>
      </tr>
      <tr>
        <th>Composite Diligence Score</th>
        <td colspan="3"><strong>{{ officer_overall_score }} / 100</strong></td>
      </tr>
    </table>
  </div>
</body>
</html>
"""


def compile_cam_data(application_id: str, db: Session) -> Dict[str, Any]:
    """
    Compiles all audited CAM report data into a structured dictionary (Section 11).
    Used by both the PDF assembler and the frontend interactive CAM report viewer.
    """
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise ValueError(f"Application {application_id} not found")

    applicant = app.applicant
    sessions = db.query(PDSession).filter(PDSession.application_id == application_id).order_by(PDSession.started_at.desc()).all()
    session = sessions[0] if sessions else None
    session_ids = [str(s.id) for s in sessions]
    session_id = str(session.id) if session else ""

    # Financial calculations
    req_amt = float(app.requested_amount or 0.0)
    tenure = int(app.tenure_months or 60)
    rate = float(app.interest_rate or 12.0)
    proposed_emi = calculate_emi(req_amt, rate, tenure)

    # Check or compute BRE calculation
    bre_calc = db.query(BREPreliminaryCalc).filter(BREPreliminaryCalc.application_id == application_id).first()
    if bre_calc:
        final_foir = float(bre_calc.final_foir)
        final_ltv = float(bre_calc.final_ltv) if bre_calc.final_ltv is not None else None
        bre_rec = bre_calc.bre_recommendation
    else:
        monthly_inc = float(applicant.declared_monthly_income or 50000.0) if applicant else 50000.0
        final_foir = calculate_foir(total_obligations_incl_new_emi=proposed_emi, net_monthly_income=monthly_inc)
        ltv_ratio, _ = calculate_ltv(req_amt, float(getattr(app, "collateral_value", 0.0) or 0.0), is_secured=(app.loan_type == "LAP"))
        final_ltv = ltv_ratio
        bre_rec = "APPROVE" if final_foir <= 60.0 else "REVIEW"

    # Extracted fields (deduplicated by field_name, latest first)
    if session_ids:
        raw_extracted = db.query(ExtractedField).filter(ExtractedField.pd_session_id.in_(session_ids)).all()
    else:
        raw_extracted = []
    
    seen_fields = set()
    extracted_fields = []
    for ef in raw_extracted:
        if ef.field_name not in seen_fields:
            seen_fields.add(ef.field_name)
            extracted_fields.append({
                "name": ef.field_name,
                "value": ef.value,
                "source": ef.source,
                "confidence": getattr(ef, "confidence_note", None),
                "confirmed": bool(ef.officer_confirmed)
            })

    # Customer consistency flags
    flags_db = db.query(CustomerConsistencyFlag).filter(
        CustomerConsistencyFlag.pd_session_id.in_(session_ids)
    ).all() if session_ids else []
    consistency_flags = [
        {
            "field_name": flag.field_name,
            "value_a": flag.value_a,
            "value_b": flag.value_b,
            "severity": flag.severity,
            "resolution_note": flag.resolution_note or ""
        }
        for flag in flags_db
    ]

    # Officer scores
    score = db.query(OfficerPDScore).filter(OfficerPDScore.pd_session_id.in_(session_ids)).first() if session_ids else None
    cov_score = float(score.coverage_score) if score else 100.0
    uptake_score = float(score.suggestion_uptake_score) if score else 100.0
    photo_score = float(score.reconfirmation_diligence_score) if score else 100.0
    proactive_bonus = float(score.proactive_diligence_bonus) if score else 0.0
    overall_score = float(score.overall_score) if score else 95.0

    # Officer remarks
    remarks = db.query(OfficerRemark).filter(OfficerRemark.pd_session_id.in_(session_ids)).first() if session_ids else None
    remarks_text = remarks.remark_text if remarks else ""

    # Photos
    photo_filter = [GroundPDPhoto.application_id == (app.id if app else None)]
    if session_ids:
        photo_filter.append(GroundPDPhoto.pd_session_id.in_(session_ids))
    photos_db = db.query(GroundPDPhoto).filter(or_(*photo_filter)).order_by(GroundPDPhoto.captured_at.desc()).all()
    photos = []
    for p in photos_db:
        ext = p.extraction or db.query(PhotoExtraction).filter_by(photo_id=p.id).first()
        photos.append({
            "id": p.id,
            "category": p.category,
            "url": p.url,
            "lat": float(p.lat) if p.lat is not None else 0.0,
            "lng": float(p.lng) if p.lng is not None else 0.0,
            "accuracy_radius": float(p.accuracy_radius) if p.accuracy_radius is not None else None,
            "captured_at": p.captured_at.isoformat() if p.captured_at else None,
            "summary": ext.summary if ext else None,
            "category_matches_photo": ext.category_matches_photo if ext else None,
            "category_mismatch_reason": ext.category_mismatch_reason if ext else None,
            "stock_level": ext.stock_level if ext else None,
            "overall_condition": ext.overall_condition if ext else None,
            "premises_type": ext.premises_type if ext else None,
            "items": ext.items if ext and ext.items else [],
            "estimated_total_value_min": float(ext.estimated_total_value_min) if ext and ext.estimated_total_value_min is not None else 0.0,
            "estimated_total_value_max": float(ext.estimated_total_value_max) if ext and ext.estimated_total_value_max is not None else 0.0,
        })

    # Narratives
    biz_source = {
        "sub_profile": applicant.sub_profile if applicant else "RETAIL",
        "extracted_facts": {ef["name"]: ef["value"] for ef in extracted_fields[:6]},
        "observations": remarks_text
    }
    fin_source = {
        "turnover": next((ef["value"] for ef in extracted_fields if "turnover" in ef["name"]), "Declared"),
        "margins": next((ef["value"] for ef in extracted_fields if "margin" in ef["name"]), "Normal range"),
        "proposed_emi": proposed_emi,
        "foir": final_foir
    }

    biz_narrative = generate_narrative_section("business_overview", biz_source)
    fin_narrative = generate_narrative_section("financial_overview", fin_source)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Physical Assets & Valuation (Agent 3 Vision Audit)
    asset_valuations = db.query(AssetValuation).filter(AssetValuation.application_id == app.id).all() if app else []
    b_est = db.query(BusinessEstimate).filter(BusinessEstimate.application_id == app.id).first() if app else None
    physical_assets = [
        {
            "category": a.category,
            "item_name": a.item_name,
            "total_count": a.total_count,
            "condition": a.condition,
            "unit_value_min_inr": a.unit_value_min_inr,
            "unit_value_max_inr": a.unit_value_max_inr,
            "total_value_min_inr": a.total_value_min_inr,
            "total_value_max_inr": a.total_value_max_inr,
        }
        for a in asset_valuations
    ]
    biz_est_dict = {
        "estimated_stock_value": b_est.estimated_stock_value if b_est else 0.0,
        "estimated_machinery_value": b_est.estimated_machinery_value if b_est else 0.0,
        "total_physical_assets_min": b_est.total_physical_assets_min if b_est else 0.0,
        "total_physical_assets_max": b_est.total_physical_assets_max if b_est else 0.0,
        "activity_level": b_est.activity_level if b_est else "medium",
        "consistency_with_declared_income": b_est.consistency_with_declared_income if b_est else "MATCH",
        "justification": b_est.justification if b_est else "",
    } if b_est else None

    return {
        "case_number": app.case_number or f"CASE-{app.id[:8]}",
        "application_id": str(app.id),
        "session_id": session_id,
        "date_str": date_str,
        "applicant_name": applicant.full_name if applicant else "N/A",
        "applicant_phone": applicant.phone_number if applicant else "N/A",
        "applicant_pan": applicant.pan_number if applicant else "N/A",
        "employment_type": getattr(applicant.employment_type, "value", applicant.employment_type) if applicant and applicant.employment_type else "SELF_EMPLOYED",
        "sub_profile": applicant.sub_profile if applicant else "RETAIL",
        "loan_type": app.loan_type or "BL",
        "requested_amount": req_amt,
        "requested_amount_str": f"{req_amt:,.2f}",
        "tenure_months": tenure,
        "interest_rate": rate,
        "proposed_emi": proposed_emi,
        "proposed_emi_str": f"{proposed_emi:,.2f}",
        "final_foir": final_foir,
        "final_foir_str": f"{final_foir:.2f}",
        "final_ltv": final_ltv,
        "final_ltv_str": f"{final_ltv:.2f}" if final_ltv is not None else None,
        "bre_recommendation": bre_rec,
        "executive_summary": (
            f"Credit Assessment Memorandum for {applicant.full_name if applicant else 'Applicant'}. "
            f"Subject has applied for an unsecured micro-business facility of INR {req_amt:,.0f} for a tenure of {tenure} months. "
            f"Calculated reducing balance EMI is INR {proposed_emi:,.0f} at an annual interest rate of {rate}%, "
            f"yielding a Fixed Obligation to Income Ratio (FOIR) of {final_foir:.1f}%. "
            f"BRE system recommendation is {bre_rec}. "
            f"Assessment incorporates {len(extracted_fields)} verified ground discussion facts, "
            f"{len(consistency_flags)} evaluated customer contradiction checks, and {len(photos)} geotagged site verification photo(s)."
        ),
        "business_overview": biz_narrative,
        "financial_overview": fin_narrative,
        "extracted_fields": extracted_fields,
        "consistency_flags": consistency_flags,
        "photos": photos,
        "physical_assets": physical_assets,
        "business_estimate": biz_est_dict,
        "officer_remarks": remarks_text,
        "officer_coverage_score": f"{cov_score:.1f}",
        "officer_uptake_score": f"{uptake_score:.1f}",
        "officer_photo_score": f"{photo_score:.1f}",
        "officer_proactive_bonus": f"{proactive_bonus:.0f}",
        "officer_overall_score": f"{overall_score:.1f}",
        "scores": {
            "coverage_score": cov_score,
            "suggestion_uptake_score": uptake_score,
            "reconfirmation_diligence_score": photo_score,
            "proactive_diligence_bonus": proactive_bonus,
            "overall_score": overall_score
        }
    }


def assemble_report(application_id: str, db: Session) -> str:
    """
    Assembles complete audited CAM report (Section 11):
    1. Compiles data dictionary via compile_cam_data().
    2. Renders HTML with Jinja2.
    3. Masks all PII via mask_pii().
    4. Renders final PDF via WeasyPrint (with graceful HTML fallback).
    5. Returns the file path of the generated report.
    """
    data = compile_cam_data(application_id, db)

    # Render Jinja2 HTML
    template = Template(REPORT_HTML_TEMPLATE)
    raw_html = template.render(
        case_number=data["case_number"],
        application_id=data["application_id"],
        date_str=data["date_str"],
        applicant_name=data["applicant_name"],
        applicant_phone=data["applicant_phone"],
        applicant_pan=data["applicant_pan"],
        employment_type=data["employment_type"],
        sub_profile=data["sub_profile"],
        loan_type=data["loan_type"],
        requested_amount=data["requested_amount_str"],
        tenure_months=data["tenure_months"],
        proposed_emi=data["proposed_emi_str"],
        final_foir=data["final_foir_str"],
        final_ltv=data["final_ltv_str"],
        bre_recommendation=data["bre_recommendation"],
        business_overview=data["business_overview"],
        financial_overview=data["financial_overview"],
        extracted_fields=data["extracted_fields"],
        consistency_flags=data["consistency_flags"],
        photos=data["photos"],
        physical_assets=data.get("physical_assets", []),
        business_estimate=data.get("business_estimate"),
        officer_remarks=data["officer_remarks"],
        officer_coverage_score=data["officer_coverage_score"],
        officer_uptake_score=data["officer_uptake_score"],
        officer_photo_score=data["officer_photo_score"],
        officer_proactive_bonus=data["officer_proactive_bonus"],
        officer_overall_score=data["officer_overall_score"]
    )

    # Apply PII Masking right before final render (Section 11 & 9a)
    masked_html = mask_pii(raw_html)

    # Ensure output directory exists
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)
    pdf_path = os.path.join(settings.REPORTS_DIR, f"cam_report_{application_id}.pdf")
    html_path = os.path.join(settings.REPORTS_DIR, f"cam_report_{application_id}.html")

    # Save HTML
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(masked_html)

    # Attempt WeasyPrint PDF compilation
    try:
        from weasyprint import HTML
        HTML(string=masked_html).write_pdf(pdf_path)
        logger.info(f"CAM report PDF generated successfully: {pdf_path}")
        return pdf_path
    except Exception as e:
        logger.warning(f"WeasyPrint PDF rendering unavailable or failed ({e}). Returning generated HTML report path: {html_path}")
        return html_path
