#!/usr/bin/env python3
"""
run_1003.py — Master orchestrator for the 1003 Synthetic Data Skill

Given a borrower narrative, this script:
  1. Calls Claude to generate internally consistent synthetic borrower data (JSON)
  2. Validates the computed fields for mathematical accuracy
  3. Renders the filled Form 1003 PDF via fill_form.py (registry-based dispatch)

Usage:
    python run_1003.py "narrative" [--output-dir ./output] [--prefix case001] [--form <form_id>]
    python run_1003.py --file narrative.txt [--output-dir ./output] [--prefix case001]

Form IDs (from assets/form_registry.json):
    fannie_mae_official_2021   — Official Fannie Mae AcroForm PDF (default)
    custom_rendered            — Programmatically rendered structured PDF

Outputs:
    {output_dir}/{prefix}_borrower_data.json   — Ground truth data
    {output_dir}/{prefix}_form_1003.pdf        — Filled loan application
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic 1003 borrower data and PDF")
    parser.add_argument("narrative", nargs="?", help="Borrower narrative text")
    parser.add_argument("--file", help="Read narrative from a text file")
    parser.add_argument("--output-dir", default="./output", help="Output directory (default: ./output)")
    parser.add_argument("--prefix", default=None, help="Output file prefix (default: auto-generated timestamp)")
    parser.add_argument("--form", default=None, help="Form template ID from form_registry.json (default: registry default)")
    parser.add_argument("--json-only", action="store_true", help="Only generate JSON, skip PDF")
    parser.add_argument("--pdf-only", help="Generate PDF from existing JSON file (pass JSON path)")
    args = parser.parse_args()

    # Get the script's directory so we can import sibling scripts
    script_dir = Path(__file__).parent

    # Ensure output directory exists
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine prefix
    prefix = args.prefix or datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = output_dir / f"{prefix}_borrower_data.json"
    pdf_path = output_dir / f"{prefix}_form_1003.pdf"

    if args.pdf_only:
        # Skip data generation, go straight to PDF
        print(f"Building PDF from existing JSON: {args.pdf_only}")
        _build_pdf(script_dir, args.pdf_only, str(pdf_path), args.form)
        print(f"\n✅ PDF: {pdf_path}")
        return

    # Get narrative
    if args.file:
        with open(args.file) as f:
            narrative = f.read().strip()
    elif args.narrative:
        narrative = args.narrative
    else:
        print("Enter borrower narrative (press Enter twice when done):")
        lines = []
        while True:
            line = input()
            if not line and lines and not lines[-1]:
                break
            lines.append(line)
        narrative = "\n".join(lines).strip()

    if not narrative:
        print("Error: no narrative provided.", file=sys.stderr)
        sys.exit(1)

    # Step 1: Generate data
    print(f"\n📋 Step 1: Generating synthetic borrower data...")
    sys.path.insert(0, str(script_dir))
    from generate_borrower_data import generate_borrower_data
    
    data = generate_borrower_data(narrative)
    
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"   ✅ JSON written: {json_path}")

    # Print quick summary
    computed = data.get("computed", {})
    b = data.get("borrower", {})
    loan = data.get("loan", {})
    print(f"\n   📊 Quick Summary:")
    print(f"      Borrower:    {b.get('first_name','')} {b.get('last_name','')}")
    print(f"      Property:    {loan.get('property_address',{}).get('city','')}, {loan.get('property_address',{}).get('state','')}")
    print(f"      Loan:        ${loan.get('loan_amount',0):,.0f} @ {loan.get('interest_rate',0)}% ({loan.get('loan_type','')})")
    print(f"      LTV:         {computed.get('ltv',0)*100:.1f}%")
    print(f"      Front DTI:   {computed.get('front_end_dti',0)*100:.1f}%")
    print(f"      Back DTI:    {computed.get('back_end_dti',0)*100:.1f}%")
    print(f"      Income:      ${computed.get('total_gross_monthly_income',0):,.0f}/mo")
    print(f"      Reserves:    {computed.get('months_reserves',0):.1f} months")
    
    if args.json_only:
        print(f"\n✅ Done (JSON only mode)")
        return

    # Step 2: Build PDF
    print(f"\n📄 Step 2: Rendering Form 1003 PDF...")
    _build_pdf(script_dir, str(json_path), str(pdf_path), args.form)
    print(f"   ✅ PDF written: {pdf_path}")

    print(f"\n{'='*60}")
    print(f"✅ Complete!")
    print(f"   Ground Truth JSON: {json_path}")
    print(f"   Filled Form 1003:  {pdf_path}")
    print(f"{'='*60}")


def _build_pdf(script_dir, json_path, pdf_path, form_id=None):
    """Dispatch PDF generation through fill_form.py (registry-based)."""
    import subprocess
    skill_dir = Path(script_dir).parent

    cmd = [
        sys.executable, str(script_dir / "fill_form.py"),
        json_path, pdf_path,
        "--skill-dir", str(skill_dir),
    ]
    if form_id:
        cmd += ["--form", form_id]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"fill_form.py failed (exit {result.returncode})")
    if result.stderr:
        print(result.stderr, file=sys.stderr)


if __name__ == "__main__":
    main()
