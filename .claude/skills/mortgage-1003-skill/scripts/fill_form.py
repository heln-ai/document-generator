#!/usr/bin/env python3
"""
fill_form.py — Unified 1003 form filler

Dispatches to the right filling strategy based on the selected form template.

Usage:
    python fill_form.py <borrower_data.json> <output.pdf> [--form <form_id>] [--skill-dir <path>]

Form IDs (from form_registry.json):
    fannie_mae_official_2021   — Fill the official Fannie Mae AcroForm PDF
    custom_rendered            — Render a clean structured PDF with reportlab

If --form is omitted, uses the registry's default (fannie_mae_official_2021).
"""

import sys
import json
import os
import argparse
from pathlib import Path


SKILL_DIR = Path(__file__).parent.parent  # mortgage-1003-skill/
PDF_SKILL_DIR = Path("/mnt/skills/public/pdf")


def load_registry(skill_dir: Path) -> dict:
    registry_path = skill_dir / "assets" / "form_registry.json"
    with open(registry_path) as f:
        return json.load(f)


def get_form(registry: dict, form_id: str) -> dict:
    forms = {f["id"]: f for f in registry["forms"]}
    if form_id not in forms:
        available = list(forms.keys())
        raise ValueError(f"Unknown form_id '{form_id}'. Available: {available}")
    return forms[form_id]


# ── Strategy: Official AcroForm fill ──────────────────────────────────────────

def build_field_values(data: dict, field_info: list) -> list:
    """
    Map borrower JSON → list of {field_id, description, page, value} dicts
    that fill_fillable_fields.py understands.
    
    Handles all 465 fields of the 2021 Fannie Mae URLA.
    """
    b = data.get("borrower", {})
    cb = data.get("co_borrower")
    emp = data.get("employment", [])
    primary_emp = next((e for e in emp if e.get("is_primary") and not e.get("end_date")), {})
    prior_emp = [e for e in emp if e.get("end_date")]
    other_income = data.get("other_income", [])
    assets = data.get("assets", {})
    dep_accounts = assets.get("depository_accounts", [])
    ret_accounts = assets.get("retirement_accounts", [])
    liabilities = data.get("liabilities", [])
    loan = data.get("loan", {})
    declarations = data.get("declarations", {})
    military = data.get("military") or {}
    hmda = data.get("hmda", {})
    computed = data.get("computed", {})
    
    # Build checked_value lookup from field_info
    checked = {f["field_id"]: f.get("checked_value", "/Yes") for f in field_info if f["type"] == "checkbox"}
    
    def chk(field_id):
        return checked.get(field_id, "/Yes")
    
    def fmt_phone(val, part):
        """Extract area/prefix/number from phone string."""
        if not val:
            return ""
        digits = "".join(c for c in str(val) if c.isdigit())
        if len(digits) >= 10:
            parts = [digits[:3], digits[3:6], digits[6:10]]
            return parts[part] if part < len(parts) else ""
        return digits if part == 0 else ""

    def parse_date(val, part):
        """Parse MM/YYYY or MM/DD/YYYY date string. part: 0=month, 1=day, 2=year"""
        if not val:
            return ""
        val = str(val).strip()
        parts = val.split("/")
        if len(parts) == 2:  # MM/YYYY
            month_day_year = [parts[0], "01", parts[1]]
        elif len(parts) == 3:
            month_day_year = parts
        else:
            return ""
        try:
            return month_day_year[part]
        except IndexError:
            return ""

    # Build all account rows merged (checking, savings first, then retirement)
    all_accounts = []
    for acct in dep_accounts:
        all_accounts.append({
            "type": acct.get("account_type", ""),
            "institution": acct.get("institution_name", ""),
            "number": f"****{str(acct.get('account_number',''))[-4:]}",
            "value": str(acct.get("current_balance", ""))
        })
    for acct in ret_accounts:
        all_accounts.append({
            "type": "Retirement",
            "institution": acct.get("institution", ""),
            "number": "****401k",
            "value": str(acct.get("value", ""))
        })

    fvs = []
    
    def add(field_id, description, page, value):
        if value is None:
            value = ""
        fvs.append({"field_id": field_id, "description": description, "page": page, "value": str(value)})

    def add_chk(field_id, description, page, condition):
        if condition:
            fvs.append({"field_id": field_id, "description": description, "page": page, "value": chk(field_id)})

    # ── PAGE 1 ──────────────────────────────────────────────────────────────────

    bname = f"{b.get('first_name','')} {b.get('middle_name','')} {b.get('last_name','')} {b.get('suffix','') or ''}".strip()
    add("topmostSubform[0].Page1[0]._1a_Name[0]", "Borrower name", 1, bname)

    ssn = b.get("ssn", "")
    ssn_parts = ssn.replace("-", "").replace(" ", "")
    add("topmostSubform[0].Page1[0]._1a_Security_1[0]", "SSN part 1", 1, ssn_parts[:3] if len(ssn_parts) >= 3 else ssn_parts)
    add("topmostSubform[0].Page1[0]._1a_Security_2[0]", "SSN part 2", 1, ssn_parts[3:5] if len(ssn_parts) >= 5 else "")
    add("topmostSubform[0].Page1[0]._1a_Security_3[0]", "SSN part 3", 1, ssn_parts[5:9] if len(ssn_parts) >= 9 else "")

    dob = b.get("dob", "")
    add("topmostSubform[0].Page1[0]._1a_Birth_1[0]", "DOB month", 1, parse_date(dob, 0))
    add("topmostSubform[0].Page1[0]._1a_Birth_2[0]", "DOB day",   1, parse_date(dob, 1))
    add("topmostSubform[0].Page1[0]._1a_Birth_3[0]", "DOB year",  1, parse_date(dob, 2))

    citizenship = b.get("citizenship", "US_Citizen")
    add_chk("topmostSubform[0].Page1[0].citizenship[0].citizen[0]._1a_US_Citizen[0]",
            "US Citizen", 1, citizenship == "US_Citizen")
    add_chk("topmostSubform[0].Page1[0].citizenship[0].permanent[0]._1a_Permanent_Resident_Alien[0]",
            "Permanent Resident Alien", 1, citizenship == "Permanent_Resident_Alien")
    add_chk("topmostSubform[0].Page1[0].citizenship[0].non_permanent[0]._1a_Non_Permanent_Resident_Alien[0]",
            "Non-Permanent Resident Alien", 1, citizenship == "Non_Permanent_Resident_Alien")

    # Credit type
    has_co = cb is not None
    add_chk("topmostSubform[0].Page1[0].credit[0].individual[0]._1a_Individual[0]",
            "Individual credit", 1, not has_co)
    add_chk("topmostSubform[0].Page1[0].credit[0].joint[0]._1a_Joint[0]",
            "Joint credit", 1, has_co)
    if has_co:
        add("topmostSubform[0].Page1[0].credit[0].joint[0]._1a_Borrowers_Number[0]", "Total borrowers", 1, "2")
        cbname = f"{cb.get('first_name','')} {cb.get('last_name','')}".strip()
        add("topmostSubform[0].Page1[0]._1a_Borrower_s_Name[0]", "Co-borrower name", 1, cbname)

    marital = b.get("marital_status", "Unmarried")
    add_chk("topmostSubform[0].Page1[0].marital-status[0].married[0]._1a_Married[0]",   "Married",   1, marital == "Married")
    add_chk("topmostSubform[0].Page1[0].marital-status[0].separated[0]._1a_Separated[0]", "Separated", 1, marital == "Separated")
    add_chk("topmostSubform[0].Page1[0].marital-status[0].unmarried[0]._1a_Unmarried[0]", "Unmarried", 1, marital in ("Unmarried", "Single", "Divorced", "Widowed"))

    add("topmostSubform[0].Page1[0]._1a_Dependents[0]", "Dependents count", 1, str(b.get("dependents_count", 0) or 0))
    dep_ages = b.get("dependents_ages", [])
    if dep_ages:
        add("topmostSubform[0].Page1[0]._1a_Dependent_Age[0]", "Dependent ages", 1, ", ".join(str(a) for a in dep_ages))

    hp = b.get("home_phone", "")
    add("topmostSubform[0].Page1[0]._1a_PhoneH1[0]", "Home phone area", 1, fmt_phone(hp, 0))
    add("topmostSubform[0].Page1[0]._1a_PhoneH2[0]", "Home phone prefix", 1, fmt_phone(hp, 1))
    add("topmostSubform[0].Page1[0]._1a_PhoneH3[0]", "Home phone number", 1, fmt_phone(hp, 2))
    cp = b.get("cell_phone", "")
    add("topmostSubform[0].Page1[0]._1a_PhoneC1[0]", "Cell phone area", 1, fmt_phone(cp, 0))
    add("topmostSubform[0].Page1[0]._1a_PhoneC2[0]", "Cell phone prefix", 1, fmt_phone(cp, 1))
    add("topmostSubform[0].Page1[0]._1a_PhoneC3[0]", "Cell phone number", 1, fmt_phone(cp, 2))
    wp = b.get("work_phone", "")
    add("topmostSubform[0].Page1[0]._1a_PhoneW1[0]", "Work phone area", 1, fmt_phone(wp, 0))
    add("topmostSubform[0].Page1[0]._1a_PhoneW2[0]", "Work phone prefix", 1, fmt_phone(wp, 1))
    add("topmostSubform[0].Page1[0]._1a_PhoneW3[0]", "Work phone number", 1, fmt_phone(wp, 2))
    add("topmostSubform[0].Page1[0]._1a_Email[0]", "Email", 1, b.get("email", ""))

    ca = b.get("current_address", {})
    add("topmostSubform[0].Page1[0]._1a_Address_St[0]",      "Current street", 1, ca.get("street", ""))
    add("topmostSubform[0].Page1[0]._1a_Address_Unit[0]",    "Current unit",   1, ca.get("unit") or "")
    add("topmostSubform[0].Page1[0]._1a_Address_City[0]",    "Current city",   1, ca.get("city", ""))
    add("topmostSubform[0].Page1[0]._1a_Address_State[0]",   "Current state",  1, ca.get("state", ""))
    add("topmostSubform[0].Page1[0]._1a_Address_Zip[0]",     "Current ZIP",    1, ca.get("zip", ""))
    add("topmostSubform[0].Page1[0]._1a_Address_Country[0]", "Current country",1, ca.get("country", "USA"))

    years_raw = ca.get("years_at_address", 0) or 0
    whole_years = int(years_raw)
    months = round((years_raw - whole_years) * 12)
    add("topmostSubform[0].Page1[0]._1a_Address_Years[0]",  "Years at address",  1, str(whole_years))
    add("topmostSubform[0].Page1[0]._1a_Address_Months[0]", "Months at address", 1, str(months) if months else "")

    housing = ca.get("housing", "Rent")
    add_chk("topmostSubform[0].Page1[0].housing_current[0].own[0]._1a_Current_Own[0]",          "Own",      1, housing == "Own")
    add_chk("topmostSubform[0].Page1[0].housing_current[0].rent[0]._1a_Current_Rent[0]",         "Rent",     1, housing == "Rent")
    add_chk("topmostSubform[0].Page1[0].housing_current[0].no_primary[0]._1a_Current_NoPrimary[0]","No primary", 1, housing == "Rent_Free")
    if housing == "Rent":
        add("topmostSubform[0].Page1[0].housing_current[0].rent[0]._1a_Address_Rent[0]", "Monthly rent", 1, str(ca.get("monthly_rent", "") or ""))

    fa = b.get("former_address")
    if fa and isinstance(fa, dict):
        add("topmostSubform[0].Page1[0]._1a_FormerAddress_St[0]",     "Former street", 1, fa.get("street", ""))
        add("topmostSubform[0].Page1[0]._1a_Former_Address_Unit[0]",  "Former unit",   1, fa.get("unit") or "")
        add("topmostSubform[0].Page1[0]._1a_Former_Address_City[0]",  "Former city",   1, fa.get("city", ""))
        add("topmostSubform[0].Page1[0]._1a_Former_Address_State[0]", "Former state",  1, fa.get("state", ""))
        add("topmostSubform[0].Page1[0]._1a_Former_Address_Zip[0]",   "Former ZIP",    1, fa.get("zip", ""))
        fa_yrs = fa.get("years_at_address", 0) or 0
        add("topmostSubform[0].Page1[0]._1a_Former_Address_Years[0]", "Former yrs",  1, str(int(fa_yrs)))
        fh = fa.get("housing", "Rent")
        add_chk("topmostSubform[0].Page1[0].housing_former[0].former_own[0]._1a_Former_Own[0]",  "Former Own",  1, fh == "Own")
        add_chk("topmostSubform[0].Page1[0].housing_former[0].former_rent[0]._1a_Former_Rent[0]","Former Rent", 1, fh == "Rent")
    else:
        add_chk("topmostSubform[0].Page1[0]._1a_Does_Not_Apply1[0]", "Former addr N/A", 1, True)

    if not b.get("mailing_address"):
        add_chk("topmostSubform[0].Page1[0]._1a_Does_Not_Apply2[0]", "Mailing addr N/A", 1, True)

    # 1b Employment
    if primary_emp:
        ea = primary_emp.get("employer_address", {})
        add("topmostSubform[0].Page1[0]._1b_Employer[0]",  "Employer name",   1, primary_emp.get("employer_name", ""))
        add("topmostSubform[0].Page1[0]._1b_Address[0]",   "Employer street", 1, ea.get("street", ""))
        add("topmostSubform[0].Page1[0]._1b_Unit[0]",      "Employer unit",   1, ea.get("unit") or "")
        add("topmostSubform[0].Page1[0]._1b_City[0]",      "Employer city",   1, ea.get("city", ""))
        add("topmostSubform[0].Page1[0]._1b_State[0]",     "Employer state",  1, ea.get("state", ""))
        add("topmostSubform[0].Page1[0]._1b_Zip[0]",       "Employer ZIP",    1, ea.get("zip", ""))
        add("topmostSubform[0].Page1[0]._1b_Country[0]",   "Employer country",1, ea.get("country") or "USA")
        ep = primary_emp.get("employer_phone", "")
        add("topmostSubform[0].Page1[0]._1b_PhoneE1[0]", "Emp ph area",   1, fmt_phone(ep, 0))
        add("topmostSubform[0].Page1[0]._1b_PhoneE2[0]", "Emp ph prefix", 1, fmt_phone(ep, 1))
        add("topmostSubform[0].Page1[0]._1b_PhoneE3[0]", "Emp ph number", 1, fmt_phone(ep, 2))
        add("topmostSubform[0].Page1[0]._1b_Position[0]", "Position/title", 1, primary_emp.get("position_title", ""))
        sd = primary_emp.get("start_date", "")
        add("topmostSubform[0].Page1[0]._1b_Employment_Start_Month[0]", "Start month", 1, parse_date(sd, 0))
        add("topmostSubform[0].Page1[0]._1b_Employment_Start_Day[0]",   "Start day",   1, parse_date(sd, 1))
        add("topmostSubform[0].Page1[0]._1b_Employment_Start_Year[0]",  "Start year",  1, parse_date(sd, 2))
        yrs_in = primary_emp.get("years_in_profession", 0) or 0
        add("topmostSubform[0].Page1[0]._1b_Employment_Years[0]",  "Yrs in field", 1, str(int(yrs_in)))
        add("topmostSubform[0].Page1[0]._1b_Employment_Months[0]", "Mo in field",  1, "")
        add("topmostSubform[0].Page1[0]._1b_Base[0]",       "Base income",    1, _fmt_income(primary_emp.get("monthly_base_income")))
        add("topmostSubform[0].Page1[0]._1b_Overtime[0]",   "Overtime income",1, _fmt_income(primary_emp.get("monthly_overtime")))
        add("topmostSubform[0].Page1[0]._1b_Bonus[0]",      "Bonus income",   1, _fmt_income(primary_emp.get("monthly_bonus")))
        add("topmostSubform[0].Page1[0]._1b_Commission[0]", "Commission",     1, _fmt_income(primary_emp.get("monthly_commission")))
        add("topmostSubform[0].Page1[0]._1b_Military[0]",   "Military entit.",1, _fmt_income(primary_emp.get("monthly_military_entitlements")))
        add("topmostSubform[0].Page1[0]._1b_IncomeTotal[0]","Total income",   1, _fmt_income(computed.get("gross_monthly_income")))
        self_emp = primary_emp.get("employment_type") == "Self_Employed"
        add_chk("topmostSubform[0].Page1[0]._1b_Owner[0]", "Self-employed", 1, self_emp)
    else:
        add_chk("topmostSubform[0].Page1[0]._1b_Does_Not_Apply1[0]", "Employment N/A", 1, True)

    # ── PAGE 2 header ──────────────────────────────────────────────────────────
    add("topmostSubform[0].#pageSet[0].PageArea2[0]._1a_Name[0]", "Name pg2 hdr", 2, bname)
    add_chk("topmostSubform[0].Page2[0]._1c_Does_Not_Apply[0]", "Additional emp N/A", 2, True)

    # 1d Prior employment
    if prior_emp:
        pe = prior_emp[0]
        pea = pe.get("employer_address", {})
        add("topmostSubform[0].Page2[0]._1d_Employer[0]",   "Prior employer", 2, pe.get("employer_name", ""))
        add("topmostSubform[0].Page2[0]._1d_Address[0]",    "Prior street",   2, pea.get("street", ""))
        add("topmostSubform[0].Page2[0]._1d_City[0]",       "Prior city",     2, pea.get("city", ""))
        add("topmostSubform[0].Page2[0]._1d_State[0]",      "Prior state",    2, pea.get("state", ""))
        add("topmostSubform[0].Page2[0]._1d_Zip[0]",        "Prior ZIP",      2, pea.get("zip", ""))
        add("topmostSubform[0].Page2[0]._1d_Position[0]",   "Prior position", 2, pe.get("position_title", ""))
        psd = pe.get("start_date", "")
        ped = pe.get("end_date", "")
        add("topmostSubform[0].Page2[0]._1d_Employment_Start_Month[0]", "Prior start mo",  2, parse_date(psd, 0))
        add("topmostSubform[0].Page2[0]._1d_Employment_Start_Day[0]",   "Prior start day", 2, parse_date(psd, 1))
        add("topmostSubform[0].Page2[0]._1d_Employment_Start_Year[0]",  "Prior start yr",  2, parse_date(psd, 2))
        add("topmostSubform[0].Page2[0]._1d_Employment_End_Month[0]",   "Prior end mo",    2, parse_date(ped, 0))
        add("topmostSubform[0].Page2[0]._1d_Employment_End_Day[0]",     "Prior end day",   2, parse_date(ped, 1))
        add("topmostSubform[0].Page2[0]._1d_Employent_End_Year[0]",     "Prior end yr",    2, parse_date(ped, 2))
        add("topmostSubform[0].Page2[0]._1d_Gross_Monthly_Income[0]",   "Prior income",    2, _fmt_income(pe.get("monthly_base_income")))
    else:
        add_chk("topmostSubform[0].Page2[0]._1d_Does_Not_Apply[0]", "Prior emp N/A", 2, True)

    # 1e Other income
    income_source_choices = {
        "Alimony": "Alimony", "Child_Support": "Child Support",
        "Rental_Income": "Other", "Social_Security": "Social Security",
        "Disability": "Disability", "Interest_Dividends": "Interest and Dividends",
        "Pension": "Retirement (e.g., Pension, IRA)", "Retirement": "Retirement (e.g., Pension, IRA)",
        "Other": "Other"
    }
    if other_income:
        for i, oi in enumerate(other_income[:3], 1):
            src_key = oi.get("type", "Other")
            src_val = income_source_choices.get(src_key, "Other")
            add(f"topmostSubform[0].Page2[0].Table1[0].T1R{i}[0]._1e_Income_Other_Sources{i}[0]",
                f"Other income source {i}", 2, src_val)
            add(f"topmostSubform[0].Page2[0].Table1[0].T1R{i}[0]._1e_Other_Monthly_Income{i}[0]",
                f"Other income amount {i}", 2, _fmt_income(oi.get("monthly_amount")))
        total_other = sum(float(o.get("monthly_amount", 0) or 0) for o in other_income)
        add("topmostSubform[0].Page2[0].Table1[0].T1R4[0]._1e_Total_Other_Monthly_Income[0]",
            "Total other income", 2, _fmt_income(total_other))
    else:
        add_chk("topmostSubform[0].Page2[0]._1e_Does_Not_Apply[0]", "Other income N/A", 2, True)

    # ── PAGE 3 header ──────────────────────────────────────────────────────────
    add("topmostSubform[0].#pageSet[0].PageArea2[1]._1a_Name[0]", "Name pg3 hdr", 3, bname)

    # 2a Assets
    acct_type_choices = {
        "Checking": "Checking", "Savings": "Savings", "Money Market": "Money Market",
        "Certificate of Deposit": "Certificate of Deposit", "Mutual Fund": "Mutual Fund",
        "Stocks": "Stocks", "Stock Options": "Stock Options", "Bonds": "Bonds",
        "Retirement": "Retirement", "401k": "Retirement", "IRA": "Retirement",
        "Trust Account": "Trust Account", "Money_Market": "Money Market",
    }
    for i, acct in enumerate(all_accounts[:5], 1):
        at = acct_type_choices.get(acct["type"], acct["type"])
        add(f"topmostSubform[0].Page3[0].Table2a[0].TR{i}[0]._2a_Account_Type{i}[0]", f"Acct type {i}", 3, at)
        add(f"topmostSubform[0].Page3[0].Table2a[0].TR{i}[0]._2a_Financial{i}[0]",    f"Institution {i}", 3, acct["institution"])
        add(f"topmostSubform[0].Page3[0].Table2a[0].TR{i}[0]._2a_Account{i}[0]",      f"Acct number {i}", 3, acct["number"])
        add(f"topmostSubform[0].Page3[0].Table2a[0].TR{i}[0]._2a_Cash{i}[0]",         f"Acct balance {i}", 3, acct["value"])
    add("topmostSubform[0].Page3[0].Table2a[0].TR6[0]._2a_Total_Cash[0]", "Total assets", 3, _fmt_income(computed.get("total_assets")))
    add_chk("topmostSubform[0].Page3[0]._2b_Does_Not_Apply[0]", "Other assets N/A", 3, True)

    # 2c Liabilities
    if liabilities:
        lib_type_choices = {
            "Revolving": "Revolving", "Installment": "Installment",
            "Lease": "Lease", "Open_30Day": "Open 30-Day", "Other": "Other"
        }
        for i, lib in enumerate(liabilities[:5], 1):
            lt = lib_type_choices.get(lib.get("type", ""), lib.get("type", ""))
            add(f"topmostSubform[0].Page3[0].Table2c[0].TR{i}[0]._2c_Account_Type{i}[0]", f"Lib type {i}",    3, lt)
            add(f"topmostSubform[0].Page3[0].Table2c[0].TR{i}[0]._2c_Company{i}[0]",       f"Creditor {i}",   3, lib.get("creditor_name", ""))
            add(f"topmostSubform[0].Page3[0].Table2c[0].TR{i}[0]._2c_Account{i}[0]",       f"Lib acct {i}",   3, lib.get("account_number", ""))
            add(f"topmostSubform[0].Page3[0].Table2c[0].TR{i}[0]._2c_Unpaid{i}[0]",        f"Unpaid bal {i}", 3, _fmt_income(lib.get("unpaid_balance")))
            add(f"topmostSubform[0].Page3[0].Table2c[0].TR{i}[0]._2c_Monthly{i}[0]",       f"Monthly pmt {i}",3, _fmt_income(lib.get("monthly_payment")))
            if lib.get("will_be_paid_off"):
                add_chk(f"topmostSubform[0].Page3[0].Table2c[0].TR{i}[0]._2c_Paid_Off{i}[0]", f"Pay off {i}", 3, True)
    else:
        add_chk("topmostSubform[0].Page3[0]._2c_Does_Not_Apply[0]", "Liabilities N/A", 3, True)
    add_chk("topmostSubform[0].Page3[0]._2d_Does_Not_Apply[0]", "Other liabilities N/A", 3, True)

    # ── PAGE 4 header + real estate ──────────────────────────────────────────
    add("topmostSubform[0].#pageSet[0].PageArea2[2]._1a_Name[0]", "Name pg4 hdr", 4, bname)
    reo = data.get("real_estate_owned", [])
    if not reo:
        add_chk("topmostSubform[0].Page4[0]._3_Do_Not_Own[0]", "No real estate", 4, True)

    # ── PAGE 5 header + loan info ─────────────────────────────────────────────
    add("topmostSubform[0].#pageSet[0].PageArea2[3]._1a_Name[0]", "Name pg5 hdr", 5, bname)

    purpose = loan.get("purpose", "Purchase")
    add_chk("topmostSubform[0].Page5[0].loan_purpose[0].purchase[0]._4a_Purchase[0]",   "Purchase",  5, purpose == "Purchase")
    add_chk("topmostSubform[0].Page5[0].loan_purpose[0].refinance[0]._4a_Refinance[0]", "Refinance", 5, "Refinance" in purpose)
    add_chk("topmostSubform[0].Page5[0].loan_purpose[0].other[0]._4a_Other[0]",         "Other",     5, purpose not in ("Purchase",) and "Refinance" not in purpose)
    add("topmostSubform[0].Page5[0]._4a_Loan_Amount[0]", "Loan amount", 5, str(int(loan.get("loan_amount", 0) or 0)))

    pa = loan.get("property_address", {})
    add("topmostSubform[0].Page5[0]._4a_Address_St[0]",      "Prop street", 5, pa.get("street", ""))
    add("topmostSubform[0].Page5[0]._4a_Address_Unit[0]",    "Prop unit",   5, pa.get("unit") or "")
    add("topmostSubform[0].Page5[0]._4a_Address_City[0]",    "Prop city",   5, pa.get("city", ""))
    add("topmostSubform[0].Page5[0]._4a_Address_State[0]",   "Prop state",  5, pa.get("state", ""))
    add("topmostSubform[0].Page5[0]._4a_Address_Zip[0]",     "Prop ZIP",    5, pa.get("zip", ""))
    add("topmostSubform[0].Page5[0]._4a_Property_County[0]", "Prop county", 5, pa.get("county", ""))
    add("topmostSubform[0].Page5[0]._4a_Units[0]",  "Units", 5, str(loan.get("number_of_units", 1) or 1))
    add("topmostSubform[0].Page5[0]._4a_Value[0]",  "Prop value", 5, str(int(loan.get("purchase_price") or loan.get("appraised_value", 0) or 0)))

    occ = loan.get("property_use", "Primary_Residence")
    add_chk("topmostSubform[0].Page5[0].occupancy[0].primary[0]._4a_Primary[0]",     "Primary Res", 5, "Primary" in occ)
    add_chk("topmostSubform[0].Page5[0].occupancy[0].secondary[0]._4a_SecondHome[0]","Second Home", 5, "Second" in occ)
    add_chk("topmostSubform[0].Page5[0].occupancy[0].invest[0]._4a_Investment[0]",   "Investment",  5, "Investment" in occ)
    add_chk("topmostSubform[0].Page5[0].L_4a1[0].no[0]._4a_mixed_no[0]",  "Mixed use No",  5, True)
    add_chk("topmostSubform[0].Page5[0].L_4a2[0].no[0]._4a_manu_no[0]",   "Mfg home No",   5, True)
    add_chk("topmostSubform[0].Page5[0]._4b_Does_Not_Apply[0]", "Other mortgages N/A", 5, True)
    add_chk("topmostSubform[0].Page5[0]._4c_Does_Not_Apply[0]", "Rental income N/A",  5, loan.get("property_use") != "Investment_Property")

    gifts = assets.get("gift_funds", [])
    if gifts:
        for i, g in enumerate(gifts[:2], 1):
            dep_field = f"topmostSubform[0].Page5[0]._4d_Table[0].TR{i}[0]._4dL{i}[0].deposited[0]._4d_r{i}Deposited[0]"
            not_field = f"topmostSubform[0].Page5[0]._4d_Table[0].TR{i}[0]._4dL{i}[0].not[0]._4d_r{i}Not[0]"
            add_chk(dep_field, f"Gift deposited {i}", 5, g.get("deposited", False))
            add_chk(not_field, f"Gift not deposited {i}", 5, not g.get("deposited", False))
            add(f"topmostSubform[0].Page5[0]._4d_Table[0].TR{i}[0]._4d_Cash{i}[0]", f"Gift amount {i}", 5, _fmt_income(g.get("amount")))
    else:
        add_chk("topmostSubform[0].Page5[0]._4d_Does_Not_Apply[0]", "Gifts N/A", 5, True)

    # ── PAGE 6 header + declarations ─────────────────────────────────────────
    add("topmostSubform[0].#pageSet[0].PageArea2[4]._1a_Name[0]", "Name pg6 hdr", 6, bname)

    d = declarations
    def decl(base, yes_key, no_key, value_is_yes: bool, page=6):
        yes_fid = f"topmostSubform[0].Page6[0].{base}.yes[0].{yes_key}[0]"
        no_fid  = f"topmostSubform[0].Page6[0].{base}.no[0].{no_key}[0]"
        if value_is_yes:
            add_chk(yes_fid, f"{base} Yes", page, True)
        else:
            add_chk(no_fid, f"{base} No", page, True)

    decl("_5aA_primary[0]",   "_5aA_primary_yes",  "_5aA_primary_no",  d.get("primary_residence_3_years", True) or not d.get("ownership_interest_3_years", False))
    decl("_5aA_another[0]",   "_5aA_another_yes",  "_5aA_another_no",  d.get("ownership_interest_3_years", False))
    decl("_5aB[0]",           "_5aB_yes",          "_5aB_no",          False)
    decl("_5aC[0]",           "_5aC_yes",          "_5aC_no",          d.get("down_payment_borrowed", False))
    decl("_5aD1[0]",          "_5aD1_yes",         "_5aD1_no",         False)
    decl("_5aD2[0]",          "_5aD2_yes",         "_5aD2_no",         False)
    decl("_5aE[0]",           "_5aE_yes",          "_5aE_no",          False)
    decl("_5bF[0]",           "_5bF_yes",          "_5bF_no",          d.get("endorser_guarantor", False))
    decl("_5bG[0]",           "_5bG_yes",          "_5bG_no",          d.get("outstanding_judgments", False))
    decl("_5bH[0]",           "_5bH_yes",          "_5bH_no",          d.get("delinquent_federal_debt", False))
    decl("_5aI[0]",           "_5bI_yes",          "_5bI_no",          d.get("lawsuit_party", False))
    decl("_5bJ[0]",           "_5bJ_yes",          "_5bJ_no",          d.get("loan_obligation", False))
    decl("_5bK[0]",           "_5bK_yes",          "_5bK_no",          False)
    decl("_5bL[0]",           "_5bL_yes",          "_5bL_no",          d.get("foreclosure_7_years", False))
    decl("_5bM[0]",           "_5bM_yes",          "_5bM_no",          d.get("bankruptcy_7_years", False))

    # ── PAGE 7 header (acknowledgments / signature page) ───────────────────────
    add("topmostSubform[0].#pageSet[0].PageArea2[5]._1a_Name[0]", "Name pg7 hdr", 7, bname)

    # ── PAGE 8 header + military + HMDA ──────────────────────────────────────
    add("topmostSubform[0].#pageSet[0].PageArea2[6]._1a_Name[0]", "Name pg8 hdr", 8, bname)

    mil_served = bool(military)
    add_chk("topmostSubform[0].Page8[0]._7service[0].yes[0]._7service_yes[0]", "Mil yes", 8, mil_served)
    add_chk("topmostSubform[0].Page8[0]._7service[0].no[0]._7service_no[0]",   "Mil no",  8, not mil_served)

    # Ethnicity
    ethnicity = hmda.get("ethnicity", [])
    add_chk("topmostSubform[0].Page8[0].ethnicity[0].hispanic[0]._8_hispanic[0]",
            "Hispanic", 8, any("Hispanic" in e for e in ethnicity))
    add_chk("topmostSubform[0].Page8[0].ethnicity[0].not_hispanic[0]._8_not_hispanic[0]",
            "Not Hispanic", 8, any("Not_Hispanic" in e or e == "Not_Hispanic" for e in ethnicity))
    add_chk("topmostSubform[0].Page8[0].ethnicity[0].refuse[0]._8_ethnicity_refuse[0]",
            "Ethnicity decline", 8, any("Decline" in e for e in ethnicity))

    # Race
    race = hmda.get("race", [])
    race_map = {
        "Asian_Chinese": "topmostSubform[0].Page8[0]._8_race[0].asian[0].asian[0].chinese[0]._8_race_chinese[0]",
        "Asian_Indian":  "topmostSubform[0].Page8[0]._8_race[0].asian[0].asian[0].indian[0]._8_race_indian[0]",
        "Asian_Filipino":"topmostSubform[0].Page8[0]._8_race[0].asian[0].asian[0].filipino[0]._8_race_filipino[0]",
        "Asian_Japanese":"topmostSubform[0].Page8[0]._8_race[0].asian[0].asian[0].japanese[0]._8_race_japanese[0]",
        "Asian_Korean":  "topmostSubform[0].Page8[0]._8_race[0].asian[0].asian[0].korean[0]._8_race_korean[0]",
        "Asian_Vietnamese":"topmostSubform[0].Page8[0]._8_race[0].asian[0].asian[0].vietnamese[0]._8_race_vietnamese[0]",
        "Black":         "topmostSubform[0].Page8[0]._8_race[0].black[0]._8_race_black[0]",
        "White":         "topmostSubform[0].Page8[0]._8_race[0].white[0]._8_race_white[0]",
        "AmericanIndian":"topmostSubform[0].Page8[0]._8_race[0].native_american[0]._8_race_native_american[0]",
        "NHPI_Native_Hawaiian":"topmostSubform[0].Page8[0]._8_race[0].pacific[0].pacific[0].hawaiian[0]._8_race_hawaiian[0]",
        "NHPI_Guamanian":"topmostSubform[0].Page8[0]._8_race[0].pacific[0].pacific[0].guanamian[0]._8_race_guamanian[0]",
        "NHPI_Samoan":   "topmostSubform[0].Page8[0]._8_race[0].pacific[0].pacific[0].samoan[0]._8_race_samoan[0]",
    }
    has_asian = any(r.startswith("Asian") for r in race)
    if has_asian:
        add_chk("topmostSubform[0].Page8[0]._8_race[0].asian[0]._8_race_asian[0]", "Asian", 8, True)
    for r in race:
        if r in race_map:
            add_chk(race_map[r], f"Race {r}", 8, True)
    add_chk("topmostSubform[0].Page8[0]._8_race[0].not_provide[0]._8_race_refuse[0]",
            "Race decline", 8, any("Decline" in r for r in race))

    sex = hmda.get("sex", "")
    add_chk("topmostSubform[0].Page8[0].sex[0].female[0]._8_sex_female[0]", "Female", 8, sex == "Female")
    add_chk("topmostSubform[0].Page8[0].sex[0].male[0]._8_sex_male[0]",     "Male",   8, sex == "Male")
    add_chk("topmostSubform[0].Page8[0].sex[0].refuse[0]._8_sex_refuse[0]", "Sex decline", 8, sex == "Decline")

    add_chk("topmostSubform[0].Page8[0].ethnicity_visual[0].no[0]._8_inst_ethnicity_no[0]", "Eth visual no", 8, True)
    add_chk("topmostSubform[0].Page8[0].sex_visual[0].no[0]._8_inst_sex_no[0]",             "Sex visual no", 8, True)
    add_chk("topmostSubform[0].Page8[0].race_visual[0].no[0]._8_inst_race_no[0]",           "Race visual no",8, True)
    add_chk("topmostSubform[0].Page8[0]._8_infosrc[0].email[0]._8_infosrc_email[0]", "Via email", 8, True)

    # ── PAGE 9 header ──────────────────────────────────────────────────────────
    add("topmostSubform[0].#pageSet[0].PageArea2[7]._1a_Name[0]", "Name pg9 hdr", 9, bname)

    return fvs


def _fmt_income(val) -> str:
    if val is None or val == "" or val == 0:
        return ""
    try:
        f = float(val)
        return f"{f:.2f}" if f else ""
    except:
        return str(val)


def fill_official(data: dict, form_def: dict, output_path: str, skill_dir: Path):
    """Fill the official AcroForm PDF."""
    import subprocess, tempfile

    form_pdf = skill_dir / form_def["file"]
    fields_json = skill_dir / form_def["fields_inventory"]
    pdf_skill = PDF_SKILL_DIR

    with open(fields_json) as f:
        field_info = json.load(f)

    field_values = build_field_values(data, field_info)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        json.dump(field_values, tmp, indent=2)
        tmp_path = tmp.name

    result = subprocess.run(
        ["python", str(pdf_skill / "scripts/fill_fillable_fields.py"),
         str(form_pdf), tmp_path, output_path],
        capture_output=True, text=True
    )

    os.unlink(tmp_path)

    if result.returncode != 0:
        errors = [l for l in result.stdout.splitlines() if "ERROR" in l]
        if errors:
            print(f"Warnings during fill ({len(errors)} field issues):", file=sys.stderr)
            for e in errors[:10]:
                print(f"  {e}", file=sys.stderr)

    print(f"Official 1003 PDF written: {output_path}", file=sys.stderr)


def fill_custom(data: dict, output_path: str, skill_dir: Path):
    """Render the custom reportlab PDF."""
    sys.path.insert(0, str(skill_dir / "scripts"))
    from build_1003_pdf import Form1003Builder
    builder = Form1003Builder(data, output_path)
    builder.build()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fill a 1003 form from borrower JSON")
    parser.add_argument("json_path", help="Borrower data JSON file")
    parser.add_argument("output_pdf", help="Output PDF path")
    parser.add_argument("--form", default=None, help="Form ID from form_registry.json (default: registry default)")
    parser.add_argument("--skill-dir", default=None, help="Path to mortgage-1003-skill/ directory")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir) if args.skill_dir else SKILL_DIR

    with open(args.json_path) as f:
        data = json.load(f)

    registry = load_registry(skill_dir)
    form_id = args.form or registry["default"]
    form_def = get_form(registry, form_id)

    print(f"Using form: {form_def['label']}", file=sys.stderr)

    if form_def["fill_method"] == "acroform":
        fill_official(data, form_def, args.output_pdf, skill_dir)
    elif form_def["fill_method"] == "reportlab":
        fill_custom(data, args.output_pdf, skill_dir)
    else:
        raise ValueError(f"Unknown fill_method: {form_def['fill_method']}")


if __name__ == "__main__":
    main()
