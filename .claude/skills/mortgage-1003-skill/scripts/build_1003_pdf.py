#!/usr/bin/env python3
"""
build_1003_pdf.py

Takes a borrower data JSON file and renders a filled Uniform Residential
Loan Application (Form 1003 / URLA 2021) PDF using reportlab.

This produces a realistic, professional-looking form that closely mirrors
the official Fannie Mae 1003 layout.

Usage:
    python build_1003_pdf.py borrower_data.json output.pdf
"""

import sys
import json
import math
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white, gray, Color
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, HRFlowable
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# ── Color palette ───────────────────────────────────────────────────────────────
HEADER_BG    = HexColor("#1F3864")   # Dark navy (Fannie Mae brand)
SECTION_BG   = HexColor("#D6E4F0")   # Light blue section headers
FIELD_BG     = HexColor("#FAFAFA")   # Light gray field rows
LINE_COLOR   = HexColor("#999999")
LABEL_COLOR  = HexColor("#444444")
VALUE_COLOR  = HexColor("#000000")
ACCENT       = HexColor("#2F75B6")

PAGE_W, PAGE_H = letter
MARGIN = 0.4 * inch
INNER_W = PAGE_W - 2 * MARGIN


# ── Helpers ─────────────────────────────────────────────────────────────────────

def fmt_currency(val):
    if val is None or val == 0:
        return ""
    try:
        return f"${float(val):,.2f}"
    except:
        return str(val)

def fmt_pct(val):
    if val is None or val == 0:
        return ""
    try:
        return f"{float(val)*100:.3f}%"
    except:
        return str(val)

def fmt_phone(val):
    if not val:
        return ""
    digits = "".join(c for c in str(val) if c.isdigit())
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return str(val)

def fmt_bool(val):
    if val is None:
        return ""
    return "Yes" if val else "No"

def safe(d, *keys, default=""):
    """Safe nested dict access."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, None)
        if d is None:
            return default
    return d if d is not None else default


# ── PDF Builder Class ────────────────────────────────────────────────────────────

class Form1003Builder:
    def __init__(self, data: dict, output_path: str):
        self.data = data
        self.output_path = output_path
        self.borrower = data.get("borrower", {})
        self.co_borrower = data.get("co_borrower")
        self.employment = data.get("employment", [])
        self.co_emp = data.get("co_borrower_employment", [])
        self.other_income = data.get("other_income", [])
        self.assets = data.get("assets", {})
        self.liabilities = data.get("liabilities", [])
        self.loan = data.get("loan", {})
        self.declarations = data.get("declarations", {})
        self.military = data.get("military")
        self.hmda = data.get("hmda", {})
        self.computed = data.get("computed", {})
        self.real_estate_owned = data.get("real_estate_owned", [])
        
        # Page tracking
        self.current_page = 0
        self.elements = []
        
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.fonts import addMapping
        
        self.styles = getSampleStyleSheet()
        
        # Custom styles
        self.style_label = self._make_style("label", 6, LABEL_COLOR, bold=False)
        self.style_value = self._make_style("value", 8, VALUE_COLOR, bold=True)
        self.style_section = self._make_style("section", 7.5, white, bold=True)
        self.style_header = self._make_style("header", 9, white, bold=True)
        self.style_title = self._make_style("title", 11, white, bold=True)
        self.style_small = self._make_style("small", 6.5, LABEL_COLOR, bold=False)

    def _make_style(self, name, size, color, bold=False):
        from reportlab.lib.styles import ParagraphStyle
        return ParagraphStyle(
            name,
            fontName="Helvetica-Bold" if bold else "Helvetica",
            fontSize=size,
            textColor=color,
            leading=size + 2,
            spaceAfter=0,
            spaceBefore=0,
        )

    # ── Element builders ─────────────────────────────────────────────────────────

    def _page_header(self, title="Uniform Residential Loan Application"):
        """Render form header."""
        data = [
            [Paragraph(title, self.style_title),
             Paragraph("Fannie Mae Form 1003 / Freddie Mac Form 65", self.style_header),
             Paragraph("OMB Approval No. 2502-0265", self.style_small)],
        ]
        t = Table(data, colWidths=[INNER_W*0.5, INNER_W*0.35, INNER_W*0.15])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, -1), white),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (0, -1), 8),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("ALIGN", (2, 0), (2, 0), "RIGHT"),
            ("RIGHTPADDING", (2, 0), (2, 0), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        self.elements.append(t)
        self.elements.append(Spacer(1, 4))

    def _section_bar(self, number, title):
        data = [[Paragraph(f"Section {number}: {title}", self.style_section)]]
        t = Table(data, colWidths=[INNER_W])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SECTION_BG),
            ("TEXTCOLOR", (0, 0), (-1, -1), HEADER_BG),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("BOX", (0, 0), (-1, -1), 0.5, ACCENT),
        ]))
        self.elements.append(Spacer(1, 4))
        self.elements.append(t)
        self.elements.append(Spacer(1, 2))

    def _subsection_bar(self, title):
        data = [[Paragraph(title, self._make_style("sub", 7, HEADER_BG, bold=True))]]
        t = Table(data, colWidths=[INNER_W])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#EBF3FB")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, ACCENT),
        ]))
        self.elements.append(t)

    def _field_row(self, fields, col_widths=None):
        """
        fields: list of (label, value) tuples
        Renders a row of labeled fields.
        """
        if col_widths is None:
            w = INNER_W / len(fields)
            col_widths = [w] * len(fields)
        
        labels = []
        values = []
        for label, val in fields:
            labels.append(Paragraph(label, self.style_label))
            values.append(Paragraph(str(val) if val else "", self.style_value))
        
        table_data = [labels, values]
        t = Table(table_data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F0F0F0")),
            ("BACKGROUND", (0, 1), (-1, 1), white),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, 0), 2),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
            ("TOPPADDING", (0, 1), (-1, 1), 3),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 3),
            ("GRID", (0, 0), (-1, -1), 0.3, LINE_COLOR),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        self.elements.append(t)

    def _checkbox_row(self, items):
        """Render a row of checkbox + label items."""
        cells = []
        for checked, label in items:
            mark = "☑" if checked else "☐"
            cells.append(Paragraph(f"{mark}  {label}", self._make_style("chk", 7, VALUE_COLOR)))
        
        t = Table([cells], colWidths=[INNER_W / len(items)] * len(items))
        t.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("BACKGROUND", (0, 0), (-1, -1), white),
            ("GRID", (0, 0), (-1, -1), 0.3, LINE_COLOR),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        self.elements.append(t)

    def _declaration_row(self, question, answer_bool):
        yes = "☑ Yes  ☐ No" if answer_bool else "☐ Yes  ☑ No"
        data = [[
            Paragraph(question, self._make_style("dq", 7, VALUE_COLOR)),
            Paragraph(yes, self._make_style("da", 7, VALUE_COLOR, bold=True))
        ]]
        t = Table(data, colWidths=[INNER_W * 0.82, INNER_W * 0.18])
        t.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (0, 0), 6),
            ("LEFTPADDING", (1, 0), (1, 0), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.3, LINE_COLOR),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, -1), white),
        ]))
        self.elements.append(t)

    def _computed_box(self):
        """Render the financial summary / computed metrics box as a flat table."""
        c = self.computed
        pp = c.get("proposed_payment", {})
        
        title_style = self._make_style("ct", 7, white, bold=True)
        val_style = self._make_style("cv", 8, VALUE_COLOR, bold=True)
        lbl_style = self._make_style("cl", 6, LABEL_COLOR)
        
        # Render as a single flat table with 4 columns: [label, value, label, value]
        W = INNER_W
        col_w = [W*0.22, W*0.18, W*0.35, W*0.25]
        
        def frow(l1, v1, l2, v2):
            return [
                Paragraph(l1, lbl_style), Paragraph(v1, val_style),
                Paragraph(l2, lbl_style), Paragraph(v2, val_style),
            ]
        
        rows = [
            [Paragraph("PROPOSED MONTHLY PAYMENT", title_style), Paragraph("", title_style),
             Paragraph("QUALIFYING RATIOS & METRICS", title_style), Paragraph("", title_style)],
            frow("Principal & Interest", fmt_currency(pp.get("principal_interest")),
                 "Gross Monthly Income", fmt_currency(c.get("total_gross_monthly_income"))),
            frow("Property Taxes (est.)", fmt_currency(pp.get("taxes")),
                 "Front-End DTI (PITI/Income)", fmt_pct(c.get("front_end_dti"))),
            frow("Homeowners Insurance", fmt_currency(pp.get("insurance")),
                 "Back-End DTI (Total/Income)", fmt_pct(c.get("back_end_dti"))),
            frow("PMI", fmt_currency(pp.get("pmi")) if pp.get("pmi") else "N/A",
                 "LTV Ratio", fmt_pct(c.get("ltv"))),
            frow("HOA Dues", fmt_currency(pp.get("hoa")) if pp.get("hoa") else "N/A",
                 "Total Liquid Assets", fmt_currency(c.get("total_liquid_assets"))),
            frow("TOTAL PITI", fmt_currency(pp.get("total_piti")),
                 "Months Reserves", f"{c.get('months_reserves', 0):.1f} mo."),
        ]
        
        t = Table(rows, colWidths=col_w)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("SPAN", (0, 0), (1, 0)),
            ("SPAN", (2, 0), (3, 0)),
            ("BACKGROUND", (0, 1), (-1, -1), white),
            ("BACKGROUND", (0, 6), (1, 6), HexColor("#EBF3FB")),
            ("FONTNAME", (1, 6), (1, 6), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.3, LINE_COLOR),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        
        self.elements.append(Spacer(1, 6))
        self.elements.append(t)

    # ── Section renderers ─────────────────────────────────────────────────────────

    def _render_section1_borrower_info(self):
        self._section_bar("1", "Borrower Information")
        b = self.borrower
        cb = self.co_borrower
        
        # Name row
        has_co = cb is not None
        
        self._subsection_bar("1a. Personal Information — Borrower" + ("   |   Co-Borrower" if has_co else ""))
        
        cols = [INNER_W*0.20, INNER_W*0.12, INNER_W*0.14, INNER_W*0.10,
                INNER_W*0.20, INNER_W*0.12, INNER_W*0.12]
        
        bname = f"{safe(b,'first_name')} {safe(b,'middle_name')} {safe(b,'last_name')} {safe(b,'suffix')}".strip()
        cbname = f"{safe(cb,'first_name')} {safe(cb,'middle_name')} {safe(cb,'last_name')}".strip() if cb else ""
        
        self._field_row([
            ("Borrower Full Name", bname),
            ("SSN", safe(b, "ssn")),
            ("Date of Birth", safe(b, "dob")),
            ("Citizenship", safe(b, "citizenship", default="").replace("_", " ")),
            ("Co-Borrower Full Name", cbname if has_co else "N/A"),
            ("Co-Borrower SSN", safe(cb, "ssn") if has_co else ""),
            ("Co-Borrower DOB", safe(cb, "dob") if has_co else ""),
        ], col_widths=cols)
        
        self._field_row([
            ("Marital Status", safe(b, "marital_status")),
            ("Dependents (count)", str(safe(b, "dependents_count", default=0))),
            ("Dependent Ages", ", ".join(str(a) for a in safe(b, "dependents_ages", default=[]))),
            ("Home Phone", fmt_phone(safe(b, "home_phone"))),
            ("Cell Phone", fmt_phone(safe(b, "cell_phone"))),
            ("Email Address", safe(b, "email")),
        ], col_widths=[INNER_W*0.14, INNER_W*0.12, INNER_W*0.18, INNER_W*0.16, INNER_W*0.16, INNER_W*0.24])
        
        # Current address
        self._subsection_bar("1b. Current Address")
        ca = safe(b, "current_address", default={})
        addr = f"{safe(ca,'street')}{', ' + safe(ca,'unit') if safe(ca,'unit') else ''}"
        
        self._field_row([
            ("Street Address", addr),
            ("City", safe(ca, "city")),
            ("State", safe(ca, "state")),
            ("ZIP", safe(ca, "zip")),
            ("Years at Address", str(safe(ca, "years_at_address", default=""))),
            ("Housing", safe(ca, "housing")),
            ("Monthly Rent", fmt_currency(safe(ca, "monthly_rent")) if safe(ca, "housing") == "Rent" else "—"),
        ], col_widths=[INNER_W*0.25, INNER_W*0.18, INNER_W*0.07, INNER_W*0.09, INNER_W*0.13, INNER_W*0.14, INNER_W*0.14])
        
        # Former address if applicable
        fa = safe(b, "former_address", default=None)
        if fa and isinstance(fa, dict):
            self._subsection_bar("1c. Former Address (if <2 years at current)")
            fa_addr = f"{safe(fa,'street')}"
            self._field_row([
                ("Street Address", fa_addr),
                ("City", safe(fa, "city")),
                ("State", safe(fa, "state")),
                ("ZIP", safe(fa, "zip")),
                ("Years at Address", str(safe(fa, "years_at_address", default=""))),
                ("Housing", safe(fa, "housing")),
            ], col_widths=[INNER_W*0.28, INNER_W*0.20, INNER_W*0.08, INNER_W*0.10, INNER_W*0.14, INNER_W*0.20])

    def _render_section2_employment(self):
        self._section_bar("2", "Employment Information")
        
        primary = [e for e in self.employment if e.get("is_primary")]
        prior = [e for e in self.employment if not e.get("is_primary")]
        
        for i, emp in enumerate(primary):
            label = "Current Employment / Self-Employment" if not i else f"Additional Employment {i+1}"
            self._subsection_bar(f"2a. {label}")
            
            ea = emp.get("employer_address", {})
            emp_addr = f"{safe(ea,'street')}, {safe(ea,'city')}, {safe(ea,'state')} {safe(ea,'zip')}"
            
            self._field_row([
                ("Employer / Business Name", safe(emp, "employer_name")),
                ("Employer Address", emp_addr),
                ("Position / Title", safe(emp, "position_title")),
                ("Start Date", safe(emp, "start_date")),
                ("Employment Type", safe(emp, "employment_type")),
                ("Years in Profession", str(safe(emp, "years_in_profession", default=""))),
            ], col_widths=[INNER_W*0.22, INNER_W*0.26, INNER_W*0.18, INNER_W*0.10, INNER_W*0.13, INNER_W*0.11])
            
            self._field_row([
                ("Monthly Base Income", fmt_currency(safe(emp, "monthly_base_income"))),
                ("Monthly Overtime", fmt_currency(safe(emp, "monthly_overtime"))),
                ("Monthly Bonus", fmt_currency(safe(emp, "monthly_bonus"))),
                ("Monthly Commission", fmt_currency(safe(emp, "monthly_commission"))),
                ("Military Entitlements", fmt_currency(safe(emp, "monthly_military_entitlements"))),
                ("TOTAL Monthly Income", fmt_currency(
                    sum(float(safe(emp, k, default=0) or 0) for k in
                        ["monthly_base_income","monthly_overtime","monthly_bonus","monthly_commission"])
                )),
            ], col_widths=[INNER_W*0.17]*6)
        
        for emp in prior:
            self._subsection_bar("2b. Prior Employment (if current < 2 years)")
            ea = emp.get("employer_address", {})
            emp_addr = f"{safe(ea,'street')}, {safe(ea,'city')}, {safe(ea,'state')} {safe(ea,'zip')}"
            self._field_row([
                ("Employer Name", safe(emp, "employer_name")),
                ("Address", emp_addr),
                ("Position", safe(emp, "position_title")),
                ("Start Date", safe(emp, "start_date")),
                ("End Date", safe(emp, "end_date")),
            ], col_widths=[INNER_W*0.22, INNER_W*0.26, INNER_W*0.18, INNER_W*0.17, INNER_W*0.17])
        
        # Other income
        if self.other_income:
            self._subsection_bar("2c. Additional / Other Income Sources")
            rows = [[
                Paragraph("Income Source", self.style_label),
                Paragraph("Monthly Amount", self.style_label),
            ]]
            for oi in self.other_income:
                rows.append([
                    Paragraph(safe(oi, "type", default="").replace("_", " "), self.style_value),
                    Paragraph(fmt_currency(safe(oi, "monthly_amount")), self.style_value),
                ])
            t = Table(rows, colWidths=[INNER_W*0.5, INNER_W*0.5])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F0F0F0")),
                ("GRID", (0, 0), (-1, -1), 0.3, LINE_COLOR),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            self.elements.append(t)

    def _render_section3_assets(self):
        self._section_bar("3", "Financial Information — Assets")
        
        # Depository accounts
        dep = self.assets.get("depository_accounts", [])
        if dep:
            self._subsection_bar("3a. Checking & Savings Accounts")
            rows = [[
                Paragraph("Institution", self.style_label),
                Paragraph("Account Type", self.style_label),
                Paragraph("Account # (last 4)", self.style_label),
                Paragraph("Current Balance", self.style_label),
            ]]
            for acct in dep:
                rows.append([
                    Paragraph(safe(acct, "institution_name"), self.style_value),
                    Paragraph(safe(acct, "account_type"), self.style_value),
                    Paragraph(f"****{str(safe(acct,'account_number',''))[-4:]}", self.style_value),
                    Paragraph(fmt_currency(safe(acct, "current_balance")), self.style_value),
                ])
            t = Table(rows, colWidths=[INNER_W*0.34, INNER_W*0.20, INNER_W*0.22, INNER_W*0.24])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F0F0F0")),
                ("GRID", (0, 0), (-1, -1), 0.3, LINE_COLOR),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            self.elements.append(t)
        
        # Retirement
        ret = self.assets.get("retirement_accounts", [])
        if ret:
            self._subsection_bar("3b. Retirement / Investment Accounts")
            rows = [[
                Paragraph("Institution", self.style_label),
                Paragraph("Account Value", self.style_label),
            ]]
            for r in ret:
                rows.append([
                    Paragraph(safe(r, "institution"), self.style_value),
                    Paragraph(fmt_currency(safe(r, "value")), self.style_value),
                ])
            t = Table(rows, colWidths=[INNER_W*0.6, INNER_W*0.4])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F0F0F0")),
                ("GRID", (0, 0), (-1, -1), 0.3, LINE_COLOR),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            self.elements.append(t)
        
        # Gifts
        gifts = self.assets.get("gift_funds", [])
        if gifts:
            self._subsection_bar("3c. Gift Funds")
            for g in gifts:
                deposited = "Deposited" if safe(g, "deposited") else "Not Yet Deposited"
                self._field_row([
                    ("Donor Relationship", safe(g, "donor_relationship")),
                    ("Gift Amount", fmt_currency(safe(g, "amount"))),
                    ("Status", deposited),
                ], col_widths=[INNER_W*0.34, INNER_W*0.33, INNER_W*0.33])
        
        # Total Assets Summary
        self._field_row([
            ("Total Liquid Assets", fmt_currency(self.computed.get("total_liquid_assets"))),
            ("Total All Assets", fmt_currency(self.computed.get("total_assets"))),
            ("Net Worth", fmt_currency(self.computed.get("net_worth"))),
        ], col_widths=[INNER_W/3]*3)

    def _render_section4_liabilities(self):
        self._section_bar("4", "Financial Information — Liabilities")
        
        if not self.liabilities:
            self.elements.append(Paragraph("No liabilities listed.", self.style_value))
            return
        
        rows = [[
            Paragraph("Creditor Name", self.style_label),
            Paragraph("Type", self.style_label),
            Paragraph("Monthly Payment", self.style_label),
            Paragraph("Unpaid Balance", self.style_label),
            Paragraph("Mo. Remaining", self.style_label),
            Paragraph("Pay Off?", self.style_label),
        ]]
        
        for lib in self.liabilities:
            rows.append([
                Paragraph(safe(lib, "creditor_name"), self.style_value),
                Paragraph(safe(lib, "type", default="").replace("_", " "), self.style_value),
                Paragraph(fmt_currency(safe(lib, "monthly_payment")), self.style_value),
                Paragraph(fmt_currency(safe(lib, "unpaid_balance")), self.style_value),
                Paragraph(str(safe(lib, "months_remaining", default="")), self.style_value),
                Paragraph("Yes" if safe(lib, "will_be_paid_off") else "No", self.style_value),
            ])
        
        t = Table(rows, colWidths=[INNER_W*0.28, INNER_W*0.14, INNER_W*0.15, INNER_W*0.15, INNER_W*0.14, INNER_W*0.14])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F0F0F0")),
            ("GRID", (0, 0), (-1, -1), 0.3, LINE_COLOR),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        self.elements.append(t)
        
        self._field_row([
            ("Total Monthly Debt Payments", fmt_currency(self.computed.get("total_monthly_debt"))),
            ("Total Unpaid Balance", fmt_currency(self.computed.get("total_liabilities_balance"))),
        ], col_widths=[INNER_W/2]*2)

    def _render_section5_loan_info(self):
        self._section_bar("5", "Loan and Property Information")
        
        loan = self.loan
        
        self._field_row([
            ("Loan Purpose", safe(loan, "purpose", default="").replace("_", " ")),
            ("Loan Type", safe(loan, "loan_type")),
            ("Property Use", safe(loan, "property_use", default="").replace("_", " ")),
            ("Property Type", safe(loan, "property_type")),
            ("Number of Units", str(safe(loan, "number_of_units", default=1))),
            ("Year Built", str(safe(loan, "year_built", default=""))),
        ], col_widths=[INNER_W/6]*6)
        
        pa = safe(loan, "property_address", default={})
        prop_addr = f"{safe(pa,'street')}, {safe(pa,'city')}, {safe(pa,'state')} {safe(pa,'zip')}"
        
        self._field_row([
            ("Subject Property Address", prop_addr),
            ("County", safe(pa, "county")),
        ], col_widths=[INNER_W*0.65, INNER_W*0.35])
        
        self._field_row([
            ("Purchase Price / Appraised Value", fmt_currency(safe(loan, "purchase_price") or safe(loan, "appraised_value"))),
            ("Loan Amount", fmt_currency(safe(loan, "loan_amount"))),
            ("Down Payment", fmt_currency(safe(loan, "down_payment_amount"))),
            ("Down Payment Source", safe(loan, "down_payment_source")),
            ("LTV Ratio", fmt_pct(self.computed.get("ltv"))),
        ], col_widths=[INNER_W*0.24, INNER_W*0.20, INNER_W*0.18, INNER_W*0.22, INNER_W*0.16])
        
        amort_type = safe(loan, "amortization_type")
        arm_info = f"  (Index: {safe(loan,'arm_index')}, Margin: {safe(loan,'arm_margin')}%)" if amort_type == "ARM" else ""
        
        self._field_row([
            ("Loan Term", f"{safe(loan, 'loan_term_months', default=360)} months"),
            ("Interest Rate", f"{safe(loan, 'interest_rate', default='')}%"),
            ("Amortization Type", f"{amort_type}{arm_info}"),
            ("Estimated Closing Costs", fmt_currency(self.computed.get("estimated_closing_costs"))),
        ], col_widths=[INNER_W*0.18, INNER_W*0.16, INNER_W*0.36, INNER_W*0.30])

    def _render_section6_declarations(self):
        self._section_bar("6", "Declarations")
        
        d = self.declarations
        decl_map = [
            ("Are there any outstanding judgments against you?", d.get("outstanding_judgments", False)),
            ("Have you declared bankruptcy within the past 7 years?", d.get("bankruptcy_7_years", False)),
            ("Have you had property foreclosed upon in the last 7 years?", d.get("foreclosure_7_years", False)),
            ("Are you a party to a lawsuit?", d.get("lawsuit_party", False)),
            ("Have you directly or indirectly been obligated on any loan resulting in foreclosure?", d.get("loan_obligation", False)),
            ("Are you presently delinquent or in default on any federal debt?", d.get("delinquent_federal_debt", False)),
            ("Are you obligated to pay alimony, child support, or separate maintenance?", d.get("alimony_child_support_obligation", False)),
            ("Is any part of the down payment borrowed?", d.get("down_payment_borrowed", False)),
            ("Are you a co-maker or endorser on a note?", d.get("endorser_guarantor", False)),
            ("Are you a U.S. citizen?", d.get("us_citizen", False)),
            ("Are you a permanent resident alien?", d.get("permanent_resident_alien", False)),
            ("Do you intend to occupy the property as your primary residence?", d.get("primary_residence_3_years", False)),
            ("Have you had ownership interest in a property in the last 3 years?", d.get("ownership_interest_3_years", False)),
        ]
        
        for question, answer in decl_map:
            self._declaration_row(question, answer)

    def _render_section7_military(self):
        mil = self.military
        if not mil:
            return
        self._section_bar("7", "Military Service")
        items = [
            (bool(mil.get("currently_serving")), "Currently Serving"),
            (bool(mil.get("veteran")), "Veteran"),
            (bool(mil.get("surviving_spouse")), "Surviving Spouse"),
        ]
        self._checkbox_row(items)
        if mil.get("branch"):
            self._field_row([("Branch of Service", safe(mil, "branch"))], col_widths=[INNER_W])

    def _render_section8_hmda(self):
        self._section_bar("8", "Demographic Information (HMDA)")
        h = self.hmda
        
        eth = h.get("ethnicity", [])
        race = h.get("race", [])
        
        self._field_row([
            ("Ethnicity", ", ".join(e.replace("_", " ").replace("Hispanic ", "") for e in eth) if eth else "Not provided"),
            ("Race", ", ".join(r.replace("_", " ").replace("Asian ", "").replace("NHPI ", "") for r in race) if race else "Not provided"),
            ("Sex", safe(h, "sex", default="Not provided")),
        ], col_widths=[INNER_W*0.33]*3)

    def _render_computed_summary(self):
        self._section_bar("★", "Ground Truth Summary (Computed Fields)")
        self._computed_box()

    # ── Main build ───────────────────────────────────────────────────────────────

    def build(self):
        from reportlab.platypus import SimpleDocTemplate
        
        doc = SimpleDocTemplate(
            self.output_path,
            pagesize=letter,
            topMargin=MARGIN,
            bottomMargin=MARGIN,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
        )
        
        # Add watermark "SYNTHETIC TEST DATA" as background? — handled via canvas
        
        self._page_header()
        
        # Narrative summary box
        meta = self.data.get("metadata", {})
        summary = meta.get("narrative_summary", "")
        tags = meta.get("scenario_tags", [])
        
        if summary:
            tag_str = "  |  ".join(f"[{t}]" for t in tags)
            meta_data = [[
                Paragraph(f"<b>Scenario:</b> {summary}", self._make_style("ms", 8, HEADER_BG)),
                Paragraph(tag_str, self._make_style("mt", 7, ACCENT)),
            ]]
            mt = Table(meta_data, colWidths=[INNER_W*0.65, INNER_W*0.35])
            mt.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#EBF3FB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("BOX", (0, 0), (-1, -1), 0.5, ACCENT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            self.elements.append(mt)
            self.elements.append(Spacer(1, 4))
        
        # Render all sections
        self._render_section1_borrower_info()
        self._render_section2_employment()
        self._render_section3_assets()
        self._render_section4_liabilities()
        self._render_section5_loan_info()
        self._render_section6_declarations()
        self._render_section7_military()
        self._render_section8_hmda()
        self._render_computed_summary()
        
        # Footer note
        self.elements.append(Spacer(1, 12))
        footer_text = ("⚠ SYNTHETIC TEST DATA ONLY — Not a real loan application. "
                       "Generated for AI system testing purposes. "
                       "All names, SSNs, addresses, and financial figures are fictitious.")
        self.elements.append(
            Paragraph(footer_text, self._make_style("footer", 7, HexColor("#CC0000"), bold=True))
        )
        
        doc.build(self.elements, onFirstPage=self._add_watermark, onLaterPages=self._add_watermark)
        print(f"PDF written to: {self.output_path}", file=sys.stderr)

    def _add_watermark(self, canv, doc):
        """Add page number and watermark to each page."""
        canv.saveState()
        canv.setFont("Helvetica", 7)
        canv.setFillColor(HexColor("#CCCCCC"))
        canv.drawCentredString(PAGE_W / 2, 0.25 * inch, 
                                f"SYNTHETIC TEST DATA — Fannie Mae Form 1003 URLA — Page {canv.getPageNumber()}")
        canv.restoreState()


# ── CLI ──────────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("Usage: python build_1003_pdf.py <borrower_data.json> <output.pdf>")
        sys.exit(1)
    
    json_path = sys.argv[1]
    pdf_path = sys.argv[2]
    
    with open(json_path) as f:
        data = json.load(f)
    
    builder = Form1003Builder(data, pdf_path)
    builder.build()


if __name__ == "__main__":
    main()
