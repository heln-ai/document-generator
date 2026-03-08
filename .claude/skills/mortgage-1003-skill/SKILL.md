---
name: mortgage-1003
description: >
  Generates synthetic mortgage borrower data and produces a filled Fannie Mae Form 1003
  (Uniform Residential Loan Application) PDF for AI system testing.

  Use this skill whenever the user mentions: generating test mortgage data, synthetic loan
  applications, 1003 forms, URLA, borrower data generation, mortgage AI testing, ground truth
  loan data, synthetic underwriting data, or any task involving creating fictitious but realistic
  mortgage borrower profiles. Also trigger when users describe a borrower scenario and want a
  filled loan application as output.

  Inputs: A narrative description of a borrower (can be brief like "first-time buyer, teacher,
  Denver CO, $425k purchase" or richly detailed). Optionally: specific scenario parameters
  like LTV target, loan type, DTI constraints, or which form template to use.

  Outputs:
    1. A filled Form 1003 PDF — realistic, professional-looking loan application
    2. A structured JSON file — ground truth data for every field on the form

  This skill handles the full pipeline: narrative → data generation → consistency validation
  → PDF rendering.
---

# Mortgage 1003 Synthetic Data Skill

## Purpose

This skill generates **synthetic, internally consistent mortgage borrower data** and renders it
into a filled Fannie Mae Form 1003 (URLA) PDF. The outputs serve as:

- **Ground truth** (the JSON) for AI extraction/classification systems
- **Input document** (the PDF) that the AI system reads and processes

Every generated scenario is mathematically consistent: LTV, DTI, income, employment, assets,
and debt all add up correctly and satisfy the stated loan type's guidelines.

---

## Available Form Templates

Templates are registered in `assets/form_registry.json`. The skill selects one per run.

| ID | Label | Method | Best For |
|----|-------|--------|----------|
| `fannie_mae_official_2021` | Official Fannie Mae / Freddie Mac URLA (2021) | AcroForm fill | AI extraction testing that needs realistic, lender-quality documents |
| `custom_rendered` | Custom Rendered 1003 | reportlab render | When a clean structured layout or the computed ground-truth summary panel is needed |

**Default:** `fannie_mae_official_2021`

### When to use each

**Use `fannie_mae_official_2021` (default) when:**
- User doesn't specify a template
- User says "official form", "real 1003", "Fannie Mae form"
- The goal is realistic documents indistinguishable from lender submissions
- Testing AI extraction, classification, or OCR pipelines

**Use `custom_rendered` when:**
- User explicitly asks for "your format", "the generated one", or "custom layout"
- User wants the computed ground-truth summary panel visible in the PDF itself
- Debugging or inspecting all fields in a clean structured view

**Adding new templates:** Add an entry to `assets/form_registry.json` following the existing
pattern. Set `"fill_method": "acroform"` for fillable PDFs and `"fill_method": "reportlab"` for
programmatically rendered ones. Place the PDF in `assets/` and its fields inventory alongside it.

---

## Workflow

```
Narrative → Determine form template → Generate JSON → validate_computed() → fill_form.py → PDF + JSON
```

### Step 1: Determine the Form Template

Check if the user specified a template or has a preference. If not, use the registry default.

```python
import json
registry = json.load(open("assets/form_registry.json"))
form_id = <user_specified_id> or registry["default"]  # → "fannie_mae_official_2021"
```

### Step 2: Understand the Narrative and Generate JSON

Read the user's description. Extract or infer:

| Element | What to capture |
|---|---|
| Borrower profile | Name, age, occupation, marital status, citizenship |
| Property | Location, type (SFR/condo/etc.), price, use (primary/investment) |
| Loan | Type (Conventional/FHA/VA/USDA), term, rate, LTV target |
| Income | Employment type, years, base + variable income, other sources |
| Assets | Savings, retirement, gift funds |
| Debts | Existing liabilities — car loans, credit cards, student loans |
| Special factors | Co-borrower, self-employment, military, investment property |

**Fill in what's missing** with realistic synthetic data consistent with context.
A "teacher in Denver" earns ~$55-65k/yr. A "software engineer in Seattle" earns ~$120-160k/yr.
Use regional norms, not generic national averages.

**Critical consistency rules:**
- `loan_amount` = `purchase_price` - `down_payment_amount` (Purchase loans)
- DTI thresholds by loan type (see `references/field_schema.md` for limits)
- Assets must cover: `down_payment` + `closing_costs (2-5%)` + `2+ months PITI reserves`
- If current address < 2 years: include `former_address`
- If current employment < 2 years: include prior employer in `employment[]`
- Use SSNs in the 900-xx-xxxx range for synthetic data

**Computed fields — calculate accurately:**

```
principal_interest = P × [r(1+r)^n] / [(1+r)^n - 1]
  where P = loan_amount, r = (rate/100)/12, n = loan_term_months

front_end_dti = total_piti / total_gross_monthly_income
back_end_dti  = (total_piti + total_monthly_debt) / total_gross_monthly_income
ltv           = loan_amount / appraised_value
months_reserves = (liquid_assets - down_payment - closing_costs) / total_piti
```

### Step 3: Save JSON and Build PDF

After generating the JSON, save it and call the unified form filler:

```bash
SKILL_DIR=/home/claude/mortgage-1003-skill
PREFIX=<borrower_last_name_or_tag>

# Save the JSON
cat > /tmp/${PREFIX}_borrower_data.json << 'ENDJSON'
<paste complete JSON here>
ENDJSON

# Build the PDF — uses the registry default unless --form is specified
python3 ${SKILL_DIR}/scripts/fill_form.py \
  /tmp/${PREFIX}_borrower_data.json \
  /mnt/user-data/outputs/${PREFIX}_form_1003.pdf \
  --skill-dir ${SKILL_DIR}

# To explicitly choose a template:
#   --form fannie_mae_official_2021   (official AcroForm, the default)
#   --form custom_rendered            (reportlab structured layout)

# Copy JSON to outputs
cp /tmp/${PREFIX}_borrower_data.json /mnt/user-data/outputs/${PREFIX}_borrower_data.json
```

Then use `present_files` to show the user both outputs.

---

## How `fill_form.py` Works

`scripts/fill_form.py` is the single entrypoint for all PDF generation. It:

1. Reads `assets/form_registry.json` to locate the selected template's metadata
2. Dispatches to the right fill strategy based on `fill_method`:
   - **`acroform`** → maps borrower JSON fields to the PDF's AcroForm field IDs
     (using the form's `fields_inventory` JSON) and calls `fill_fillable_fields.py`
   - **`reportlab`** → calls `build_1003_pdf.py` to render a structured PDF from scratch
3. Writes the filled PDF to the specified output path

**Adding a new template** requires only:
1. Place the PDF in `assets/`
2. Run `extract_form_field_info.py <form.pdf> assets/<form>_fields.json` to generate its inventory
3. Add an entry to `form_registry.json` — no code changes needed

---

## Scenario Variety Guidelines

When generating multiple test cases, vary across these dimensions:

| Dimension | Variants to include |
|---|---|
| Loan type | Conventional, FHA, VA, USDA |
| Borrower type | W-2 employee, self-employed, retired, dual-income |
| Property type | SFR, condo, townhouse, 2-4 unit |
| LTV | Low (<70%), medium (75-85%), high (90-97%) |
| DTI | Conservative (<28/36), moderate (32/43), borderline (38/50) |
| Special factors | Gift funds, co-borrower, investment property, ARM |
| Declarations | Mostly clean, occasional prior bankruptcy (>7yrs) |
| Demographics | Diverse HMDA data across ethnicity, race, sex |

---

## Output Format

Both outputs go to `/mnt/user-data/outputs/`:

```
<prefix>_borrower_data.json     ← ground truth for all fields
<prefix>_form_1003.pdf          ← filled loan application PDF
```

Top-level JSON structure (full schema in `references/field_schema.md`):

```json
{
  "metadata": {
    "generated_at": "<ISO timestamp>",
    "narrative_summary": "<1-sentence summary>",
    "scenario_tags": ["first_time_buyer", "conventional", ...],
    "form_template": "<form_id used>"
  },
  "borrower": { ... },
  "co_borrower": null,
  "employment": [ ... ],
  "co_borrower_employment": [],
  "other_income": [ ... ],
  "assets": { "depository_accounts": [...], "retirement_accounts": [...], "gift_funds": [...] },
  "liabilities": [ ... ],
  "real_estate_owned": [ ... ],
  "loan": { ... },
  "declarations": { ... },
  "military": null,
  "hmda": { ... },
  "computed": {
    "gross_monthly_income": 0,
    "total_gross_monthly_income": 0,
    "total_monthly_debt": 0,
    "proposed_payment": { "principal_interest": 0, "taxes": 0, "insurance": 0,
                          "pmi": 0, "hoa": 0, "total_piti": 0 },
    "front_end_dti": 0,
    "back_end_dti": 0,
    "ltv": 0,
    "total_liquid_assets": 0,
    "total_assets": 0,
    "months_reserves": 0,
    "estimated_closing_costs": 0
  }
}
```

Include `"form_template": "<form_id>"` in `metadata` so ground truth records which template was used.

---

## Quality Checklist

Before presenting outputs, verify:

- [ ] `loan_amount` = `purchase_price` - `down_payment_amount`
- [ ] `ltv` = `loan_amount` / `appraised_value`
- [ ] `front_end_dti` and `back_end_dti` within guideline thresholds for the loan type
- [ ] `total_liquid_assets` ≥ `down_payment` + `closing_costs` + 2 months PITI
- [ ] Employment history spans ≥ 2 years (prior employer entry if needed)
- [ ] `former_address` populated if current address < 2 years
- [ ] SSN is in 900-xx-xxxx test range
- [ ] PMI included if LTV > 80% (Conventional)
- [ ] `metadata.form_template` records which template was used
- [ ] Scenario tags accurately reflect the case

---

## Reference Files

| File | Purpose |
|------|---------|
| `assets/form_registry.json` | Registry of all available form templates |
| `assets/fannie_mae_1003_official_2021.pdf` | Official Fannie Mae / Freddie Mac URLA (2021) |
| `assets/fannie_mae_1003_fields.json` | All 465 AcroForm field IDs and valid values for the official form |
| `scripts/fill_form.py` | **Unified entrypoint** — reads registry, dispatches to right fill strategy |
| `scripts/build_1003_pdf.py` | reportlab renderer (backend for `custom_rendered` template) |
| `scripts/generate_borrower_data.py` | Standalone CLI for API-driven batch generation |
| `scripts/run_1003.py` | End-to-end orchestrator (narrative → JSON → PDF via fill_form.py) |
| `references/field_schema.md` | Complete field definitions, data types, and DTI/LTV rules |
