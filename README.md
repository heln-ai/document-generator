# document-generator

Generate documents with ground truth to verify classification and extraction.

## Installation

Add this repo as a skill directory in Claude Code:

```bash
claude mcp add-skill /path/to/document-generator
```

Or add it directly to your project's `.claude/settings.json`:

```json
{
  "skills": ["/path/to/document-generator/.claude/skills"]
}
```

## Skills

### Mortgage Form 1003 Generator

Generates synthetic mortgage borrower data and produces a filled **Fannie Mae Form 1003** (Uniform Residential Loan Application) PDF. Useful for testing AI extraction, classification, and OCR pipelines.

**Trigger phrases:** generate test mortgage data, synthetic loan application, 1003 form, URLA, borrower data generation, mortgage AI testing, ground truth loan data

**Input:** A narrative description of a borrower scenario — can be brief or detailed.

```
"First-time buyer, teacher, Denver CO, $425k purchase"
```

Optional parameters: LTV target, loan type, DTI constraints, form template.

**Outputs:**

| File | Description |
|------|-------------|
| `<prefix>_form_1003.pdf` | Filled loan application PDF |
| `<prefix>_borrower_data.json` | Ground truth data for every field on the form |

**Form templates:**

| Template | Method | Best For |
|----------|--------|----------|
| `fannie_mae_official_2021` (default) | AcroForm fill | Realistic documents for AI extraction testing |
| `custom_rendered` | reportlab render | Clean structured layout with computed ground-truth summary panel |

**Consistency guarantees:**

- `loan_amount = purchase_price - down_payment`
- DTI thresholds enforced per loan type
- Assets cover down payment + closing costs + 2+ months PITI reserves
- Employment and address history span 2+ years
- SSNs use the 900-xx-xxxx test range

**Scenario variety:** Supports Conventional, FHA, VA, and USDA loans across W-2 employees, self-employed, retired, and dual-income borrowers with varying LTV, DTI, and property types.
