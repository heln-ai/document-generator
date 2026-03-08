#!/usr/bin/env python3
"""
generate_borrower_data.py

Takes a borrower narrative (text description) and generates a complete,
internally consistent synthetic borrower data JSON conforming to the 1003 URLA schema.

Usage:
    python generate_borrower_data.py "narrative text" [output.json]
    python generate_borrower_data.py --file narrative.txt [output.json]
    python generate_borrower_data.py --interactive

The generated JSON is the ground truth used to fill the 1003 PDF form.
"""

import sys
import json
import os
import math
import argparse
from datetime import datetime, date
import random


# ── Claude API call ────────────────────────────────────────────────────────────

def call_claude(system_prompt: str, user_message: str, max_tokens: int = 4096) -> str:
    """Call the Anthropic API and return the text response."""
    import urllib.request

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}]
    }

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
        return data["content"][0]["text"]


# ── Data generation ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a mortgage data specialist generating synthetic borrower data for AI system testing. 
Your job is to take a narrative description of a borrower and produce a complete, internally consistent JSON 
dataset that fills every field of the Uniform Residential Loan Application (1003 URLA).

CRITICAL RULES:
1. Generate SYNTHETIC data only. Use SSNs in the 900-xx-xxxx test range.
2. Ensure ALL numbers are internally consistent:
   - loan_amount = purchase_price - down_payment_amount
   - DTI ratios must be realistic for the loan type
   - Income must be plausible for the stated job title and location
   - Assets must cover down payment + closing costs + minimum reserves
3. Infer unstated details from context (e.g., a "teacher in Denver" earns ~$55-65k/yr)
4. Make declarations realistic (most first-time buyers have clean declarations)
5. HMDA data should be consistent with any ethnicity/demographic cues in the narrative
6. Every employment record must have start/end dates that make logical sense
7. If the narrative mentions a co-borrower, generate full data for both

OUTPUT FORMAT: Return ONLY valid JSON. No explanation, no markdown fences, no preamble.

The JSON must follow this exact top-level structure:
{
  "metadata": {
    "generated_at": "<ISO timestamp>",
    "narrative_summary": "<1-sentence summary of the borrower scenario>",
    "scenario_tags": ["<tag1>", "<tag2>"]
  },
  "borrower": { ... },
  "co_borrower": null,
  "employment": [ ... ],
  "co_borrower_employment": [],
  "other_income": [ ... ],
  "assets": { 
    "depository_accounts": [ ... ],
    "retirement_accounts": [ ... ],
    "other_real_estate": [ ... ],
    "gift_funds": [ ... ],
    "other": [ ... ]
  },
  "liabilities": [ ... ],
  "real_estate_owned": [ ... ],
  "loan": { ... },
  "declarations": { ... },
  "co_borrower_declarations": null,
  "military": null,
  "hmda": { ... },
  "computed": {
    "gross_monthly_income": 0,
    "co_borrower_gross_monthly_income": 0,
    "total_gross_monthly_income": 0,
    "total_monthly_debt": 0,
    "proposed_payment": {
      "principal_interest": 0,
      "taxes": 0,
      "insurance": 0,
      "pmi": 0,
      "hoa": 0,
      "total_piti": 0
    },
    "front_end_dti": 0,
    "back_end_dti": 0,
    "ltv": 0,
    "cltv": 0,
    "total_liquid_assets": 0,
    "total_assets": 0,
    "total_liabilities_balance": 0,
    "net_worth": 0,
    "months_reserves": 0,
    "estimated_closing_costs": 0
  }
}

For computed fields, calculate them accurately:
- principal_interest: use the standard mortgage payment formula: M = P[r(1+r)^n]/[(1+r)^n-1]
  where P = loan_amount, r = (interest_rate/100)/12, n = loan_term_months
- front_end_dti = (proposed_payment.total_piti) / total_gross_monthly_income
- back_end_dti = (proposed_payment.total_piti + total_monthly_debt) / total_gross_monthly_income
- ltv = loan.loan_amount / loan.appraised_value
- months_reserves = (total_liquid_assets - loan.down_payment_amount - estimated_closing_costs) / proposed_payment.total_piti

Scenario tags should include relevant labels such as: first_time_buyer, refinance, self_employed, 
va_loan, fha_loan, conventional, investment_property, second_home, co_borrower, high_dti, 
low_ltv, gift_funds, jumbo, arm, etc.

For the borrower object, use this structure:
{
  "first_name": "...", "middle_name": "...", "last_name": "...", "suffix": null,
  "ssn": "900-XX-XXXX",
  "dob": "MM/DD/YYYY",
  "citizenship": "US_Citizen",
  "marital_status": "...",
  "dependents_count": 0,
  "dependents_ages": [],
  "current_address": {
    "street": "...", "unit": null, "city": "...", "state": "XX", "zip": "XXXXX",
    "years_at_address": 0.0,
    "housing": "Rent",
    "monthly_rent": 0
  },
  "former_address": null,
  "mailing_address": null,
  "home_phone": "XXX-XXX-XXXX",
  "cell_phone": "XXX-XXX-XXXX",
  "work_phone": null,
  "email": "..."
}

For employment array items:
{
  "employer_name": "...",
  "employer_address": {"street": "...", "city": "...", "state": "XX", "zip": "XXXXX"},
  "position_title": "...",
  "start_date": "MM/YYYY",
  "end_date": null,
  "years_in_profession": 0.0,
  "employment_type": "Employed",
  "is_primary": true,
  "monthly_base_income": 0,
  "monthly_overtime": 0,
  "monthly_bonus": 0,
  "monthly_commission": 0,
  "monthly_military_entitlements": 0
}
"""


def generate_borrower_data(narrative: str) -> dict:
    """Generate complete borrower data from a narrative using Claude."""
    print(f"Generating synthetic borrower data from narrative...", file=sys.stderr)
    
    prompt = f"""Generate complete 1003 URLA borrower data for this scenario:

NARRATIVE:
{narrative}

Remember:
- Make all numbers internally consistent
- Compute all derived fields accurately  
- Use SSNs in 900-xx-xxxx range for synthetic data
- Generate realistic but fictional names, addresses, employer names
- Return ONLY the JSON object, no other text
"""
    
    response_text = call_claude(SYSTEM_PROMPT, prompt, max_tokens=6000)
    
    # Strip any accidental markdown fences
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    
    data = json.loads(text)
    
    # Post-process: re-verify computed fields for accuracy
    data = verify_and_fix_computed(data)
    
    return data


def verify_and_fix_computed(data: dict) -> dict:
    """Re-compute the computed fields to ensure mathematical accuracy."""
    loan = data.get("loan", {})
    computed = data.get("computed", {})
    
    # Re-calculate P&I payment
    P = float(loan.get("loan_amount", 0))
    annual_rate = float(loan.get("interest_rate", 7.0))
    n = int(loan.get("loan_term_months", 360))
    
    if P > 0 and annual_rate > 0 and n > 0:
        r = (annual_rate / 100) / 12
        pi = P * (r * (1 + r)**n) / ((1 + r)**n - 1)
        computed["proposed_payment"]["principal_interest"] = round(pi, 2)
    
    # Re-sum income
    emp_income = sum(
        float(e.get("monthly_base_income", 0)) +
        float(e.get("monthly_overtime", 0)) +
        float(e.get("monthly_bonus", 0)) +
        float(e.get("monthly_commission", 0))
        for e in data.get("employment", [])
        if e.get("is_primary", True) and e.get("end_date") is None
    )
    other_income = sum(float(i.get("monthly_amount", 0)) for i in data.get("other_income", []))
    computed["gross_monthly_income"] = round(emp_income + other_income, 2)
    
    # Co-borrower income
    co_emp_income = sum(
        float(e.get("monthly_base_income", 0)) +
        float(e.get("monthly_overtime", 0)) +
        float(e.get("monthly_bonus", 0))
        for e in data.get("co_borrower_employment", [])
        if e.get("end_date") is None
    )
    computed["co_borrower_gross_monthly_income"] = round(co_emp_income, 2)
    computed["total_gross_monthly_income"] = round(
        computed["gross_monthly_income"] + computed["co_borrower_gross_monthly_income"], 2
    )
    
    # Re-sum liquid assets
    liquid = sum(
        float(a.get("current_balance", 0))
        for a in data.get("assets", {}).get("depository_accounts", [])
    )
    computed["total_liquid_assets"] = round(liquid, 2)
    
    retirement = sum(
        float(a.get("value", 0))
        for a in data.get("assets", {}).get("retirement_accounts", [])
    )
    other_assets = sum(
        float(a.get("value", 0))
        for a in data.get("assets", {}).get("other", [])
    )
    re_equity = sum(
        float(a.get("value", 0)) - float(a.get("mortgage_balance", 0))
        for a in data.get("assets", {}).get("other_real_estate", [])
    )
    computed["total_assets"] = round(liquid + retirement + other_assets + max(re_equity, 0), 2)
    
    # Re-sum debts (exclude items being paid off)
    monthly_debt = sum(
        float(l.get("monthly_payment", 0))
        for l in data.get("liabilities", [])
        if not l.get("will_be_paid_off", False)
    )
    computed["total_monthly_debt"] = round(monthly_debt, 2)
    
    total_balance = sum(float(l.get("unpaid_balance", 0)) for l in data.get("liabilities", []))
    computed["total_liabilities_balance"] = round(total_balance, 2)
    computed["net_worth"] = round(computed["total_assets"] - total_balance, 2)
    
    # PITI total
    pp = computed.get("proposed_payment", {})
    piti = (
        float(pp.get("principal_interest", 0)) +
        float(pp.get("taxes", 0)) +
        float(pp.get("insurance", 0)) +
        float(pp.get("pmi", 0)) +
        float(pp.get("hoa", 0))
    )
    computed["proposed_payment"]["total_piti"] = round(piti, 2)
    
    # DTI
    tgi = computed["total_gross_monthly_income"]
    if tgi > 0:
        computed["front_end_dti"] = round(piti / tgi, 4)
        computed["back_end_dti"] = round((piti + monthly_debt) / tgi, 4)
    
    # LTV
    appraised = float(loan.get("appraised_value", 0))
    loan_amt = float(loan.get("loan_amount", 0))
    if appraised > 0:
        computed["ltv"] = round(loan_amt / appraised, 4)
        computed["cltv"] = computed["ltv"]  # simplified; update if subordinate financing
    
    # Reserves
    dp = float(loan.get("down_payment_amount", 0))
    cc = float(computed.get("estimated_closing_costs", 0))
    if piti > 0:
        computed["months_reserves"] = round(
            max(0, liquid - dp - cc) / piti, 1
        )
    
    data["computed"] = computed
    return data


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic 1003 borrower data from a narrative"
    )
    parser.add_argument("narrative", nargs="?", help="Borrower narrative text")
    parser.add_argument("output", nargs="?", help="Output JSON file path")
    parser.add_argument("--file", help="Read narrative from a text file")
    parser.add_argument("--interactive", action="store_true", help="Prompt for narrative interactively")
    
    args = parser.parse_args()
    
    if args.interactive:
        print("Enter the borrower narrative (press Enter twice when done):")
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
        narrative = "\n".join(lines).strip()
    elif args.file:
        with open(args.file) as f:
            narrative = f.read().strip()
    elif args.narrative:
        narrative = args.narrative
    else:
        parser.print_help()
        sys.exit(1)
    
    data = generate_borrower_data(narrative)
    
    json_str = json.dumps(data, indent=2)
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(json_str)
        print(f"Borrower data written to: {args.output}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
