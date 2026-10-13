# MSFincap — RAG Business Profile Documents

These are the actual reference documents that go into the knowledge base / vector store — one per business/employer category. Each profile is retrieved by the AI agent during the live PD session to establish domain benchmarks and evaluate against the ongoing transcript.

**Format note:** Each profile follows a clean, three-part structure:
1. **Overview**: Industry context and operational characteristics.
2. **Required Outputs Checklist ("Info Needed for Good PD")**: The exhaustive list of trade-specific facts, metrics, and operational details that must be captured during the PD discussion.
3. **Red Flags to Watch For**: Specific category-relevant inconsistencies, risks, and warning signals.

*(Note: Static follow-up question banks are deliberately excluded from RAG. The AI follow-up agent dynamically generates customized, contextual follow-up questions on the fly based on the live audio transcript, asked questions, and missing items from the Required Outputs Checklist).*

---

## Profile: Manufacturing / Job-Work

**Overview:** Small-scale manufacturing or job-work operations (metalworking, fabrication, machine-shop work) — typically 1-10 employees, working on contract orders for other businesses rather than direct retail sale. Revenue is often irregular, tied to order flow rather than steady footfall.

**Required Outputs Checklist:**
- [ ] Machinery inventory — type, count, approximate age/condition
- [ ] Order model — own-orders vs. job-work for other companies (materially changes revenue predictability)
- [ ] Client concentration — number of regular clients; a business with 1-2 clients is riskier than one with 5+
- [ ] Raw material sourcing and payment terms (cash upfront vs. credit)
- [ ] Turnaround time and typical order size
- [ ] Seasonality — is demand steady or does it spike/dip with festivals, agricultural cycles, or client industries
- [ ] Secondary income streams (e.g. scrap metal sales — common and legitimate, should be verified not assumed)
- [ ] Customer payment terms — immediate vs. credit period, and typical credit period length
- [ ] Employee wage structure (helps validate stated expenses)
- [ ] Premises ownership status

**Red Flags to Watch For:**
- Client concentration risk: revenue overwhelmingly from one or two clients
- A stated turnover that doesn't match the scale of machinery/premises visible in photos
- No registrations at all (Udyam, trade license) despite years in operation — not disqualifying, but worth noting
- Heavy reliance on informal/cash-only transactions with no fallback verification

---

## Profile: Retail / Trading (Kirana, General Store, Boutique)

**Overview:** Fixed-location retail selling directly to end consumers. Revenue is driven by footfall and repeat customers rather than large individual orders. Inventory turnover and supplier credit terms are the key financial signals.

**Required Outputs Checklist:**
- [ ] Product category and typical price points
- [ ] Daily/weekly footfall pattern
- [ ] Inventory value and turnover rate (how often restocked)
- [ ] Supplier relationship — credit terms vs. cash purchase
- [ ] Seasonal demand pattern (festivals, school-opening season, etc.)
- [ ] Whether credit is extended to regular customers (common, but affects effective cash flow)
- [ ] Premises type — fixed shop vs. cart/temporary stall (materially different risk profile)
- [ ] Competition — nearby similar shops, if mentioned

**Red Flags to Watch For:**
- Stated inventory value dramatically mismatched with photo evidence of stock on shelves
- Extending significant credit to customers with no tracking system
- A "fixed shop" claim that photos show is actually a temporary/mobile setup
- Turnover claims inconsistent with visible shop size/foot traffic during the visit

---

## Profile: Services (Tailoring, Salon, Small Repair Shop)

**Overview:** Skill/labor-based small services businesses. Revenue is per-job rather than per-product-sale. Equipment investment is typically modest; the main asset is the operator's skill and time.

**Required Outputs Checklist:**
- [ ] Service delivery model — walk-in retail customers vs. contract/bulk work for other businesses (e.g. a tailor doing contract stitching for a garment shop vs. individual customer orders) — these have very different revenue predictability
- [ ] Typical price range per job
- [ ] Seasonal demand pattern (strongly seasonal for tailoring/festival-adjacent services)
- [ ] Equipment count and condition
- [ ] Staff/assistants, if any
- [ ] Customer acquisition — repeat/referral-based vs. walk-in
- [ ] Weekly job volume (a proxy for capacity utilization)

**Red Flags to Watch For:**
- Large gap between stated peak-season and off-season income with no clear conservative (lean-period) figure available for eligibility calculation
- Claimed job volume inconsistent with equipment count/staff (e.g. one person claiming volume that would require several workers)
- No distinction made between gross job revenue and net income after materials/supplies

---

## Profile: Salaried — Private Sector (Small/Mid-Size Company)

**Overview:** Employees of privately-owned businesses without the stability assumptions that apply to government/large-corporate employment. Employer stability and payment consistency matter more here than for other salaried categories.

**Required Outputs Checklist:**
- [ ] Employer's industry and perceived business stability
- [ ] Salary payment consistency — any history of delays
- [ ] Employment documentation — offer letter, appointment letter
- [ ] Statutory benefits (PF/ESI) — presence is a positive stability signal, absence is common and not disqualifying but worth noting
- [ ] Variable/bonus pay component, if any
- [ ] Total work experience (including prior employers, as a stability/skill proxy)
- [ ] Employer size (rough employee count)

**Red Flags to Watch For:**
- Salary paid in cash with no formal documentation at all
- History of delayed salary payments
- Very recent job change with no clear explanation
- Employer in a visibly declining or highly seasonal industry with no acknowledgment of that risk in the borrower's own answers

---

## Profile: Salaried — Government / PSU

**Overview:** Generally the most stable salaried category, but still requires verification — confirmation status (permanent vs. probationary) and pay grade matter more here than employer-stability questions, since the employer itself is assumed stable.

**Required Outputs Checklist:**
- [ ] Confirmation status — permanent/confirmed vs. probationary/contractual government role (these carry different risk profiles despite both being "government")
- [ ] Pay grade / pay level
- [ ] Retirement benefit type (pension vs. NPS — affects long-term financial picture)
- [ ] Salary bank account (often institutionally mandated, useful corroboration)
- [ ] Employment ID/service proof

**Red Flags to Watch For:**
- Claiming "government job" without being able to produce any employment ID or documentation
- Contractual/outsourced government-adjacent roles (e.g. contract staff at a government office) being conflated with permanent government employment — these are materially different risk categories and should not be scored the same

---

## Template for Adding a New Profile

When extending to new categories (agriculture, transport, construction, food service, etc.), follow this standardized structure:

```
## Profile: [Category Name]

**Overview:** [2-3 sentences on what defines this business/employment type and what's
distinctive about assessing it]

**Required Outputs Checklist:**
- [ ] [Specific, trade-critical items the AI agent verifies from the discussion]

**Red Flags to Watch For:**
- [Category-specific risk indicators and discrepancy signals]
```

Each new profile should be reviewed by a credit professional before going live to validate benchmarks and requirements against MSFincap's real lending experience.

