# 1003 URLA Field Schema Reference

This document defines every field in the Uniform Residential Loan Application (Fannie Mae Form 1003 / Freddie Mac Form 65, 2021+ URLA format) along with data types, constraints, and consistency rules.

---

## Section 1 — Borrower Information

### 1a. Personal Information
- `borrower.first_name` — string
- `borrower.middle_name` — string (optional)
- `borrower.last_name` — string
- `borrower.suffix` — enum: Jr, Sr, II, III, IV (optional)
- `borrower.ssn` — string, format: XXX-XX-XXXX (synthetic: use 900-xx-xxxx range for test data)
- `borrower.dob` — date, format: MM/DD/YYYY
- `borrower.citizenship` — enum: US_Citizen, Permanent_Resident_Alien, Non_Permanent_Resident_Alien
- `borrower.marital_status` — enum: Married, Separated, Unmarried
- `borrower.dependents_count` — integer 0–15
- `borrower.dependents_ages` — list of integers

### 1b. Current Address
- `borrower.current_address.street` — string
- `borrower.current_address.unit` — string (optional)
- `borrower.current_address.city` — string
- `borrower.current_address.state` — 2-letter state code
- `borrower.current_address.zip` — 5-digit string
- `borrower.current_address.years_at_address` — decimal (e.g., 2.5)
- `borrower.current_address.housing` — enum: Own, Rent, Rent_Free
- `borrower.current_address.monthly_rent` — decimal (if Rent)

### 1c. Former Address (if <2 years at current)
- `borrower.former_address.*` — same structure as current_address

### 1d. Mailing Address (if different)
- `borrower.mailing_address.*`

### 1e. Contact
- `borrower.home_phone` — string
- `borrower.cell_phone` — string
- `borrower.work_phone` — string (optional)
- `borrower.email` — string

---

## Section 2 — Employment Information

### Current Employment (Employer 1)
- `employment[0].employer_name` — string
- `employment[0].employer_address.street` — string
- `employment[0].employer_address.city` — string
- `employment[0].employer_address.state` — string
- `employment[0].employer_address.zip` — string
- `employment[0].position_title` — string
- `employment[0].start_date` — date MM/YYYY
- `employment[0].years_in_profession` — decimal
- `employment[0].employment_type` — enum: Employed, Self_Employed, Military
- `employment[0].is_primary` — boolean (true)
- `employment[0].monthly_base_income` — decimal
- `employment[0].monthly_overtime` — decimal
- `employment[0].monthly_bonus` — decimal
- `employment[0].monthly_commission` — decimal
- `employment[0].monthly_military_entitlements` — decimal

### Prior Employment (if current <2 years)
- `employment[1].*` — same structure, `is_primary: false`

---

## Section 3 — Additional Income Sources
- `other_income[].type` — enum: Alimony, Child_Support, Rental_Income, Social_Security, Disability, Interest_Dividends, Pension, Other
- `other_income[].monthly_amount` — decimal

---

## Section 4 — Assets

### Checking / Savings Accounts
- `assets.depository_accounts[].institution_name` — string
- `assets.depository_accounts[].account_type` — enum: Checking, Savings, Money_Market
- `assets.depository_accounts[].account_number` — string (last 4 digits for synthetic)
- `assets.depository_accounts[].current_balance` — decimal

### Other Assets
- `assets.retirement_accounts[].institution` — string
- `assets.retirement_accounts[].value` — decimal
- `assets.other_real_estate[].address` — string
- `assets.other_real_estate[].value` — decimal
- `assets.other_real_estate[].mortgage_balance` — decimal
- `assets.other[].type` — enum: Stocks, Bonds, BusinessAssets, Other
- `assets.other[].value` — decimal

### Gift Funds (if applicable)
- `assets.gift_funds[].donor_relationship` — enum: Relative, Employer, Government, Other
- `assets.gift_funds[].amount` — decimal
- `assets.gift_funds[].deposited` — boolean

---

## Section 5 — Liabilities & Monthly Expenses

- `liabilities[].creditor_name` — string
- `liabilities[].account_number` — string
- `liabilities[].type` — enum: Revolving, Installment, Lease, Mortgage, Open_30Day, Other
- `liabilities[].monthly_payment` — decimal
- `liabilities[].unpaid_balance` — decimal
- `liabilities[].months_remaining` — integer
- `liabilities[].will_be_paid_off` — boolean

---

## Section 6 — Real Estate

- `real_estate[].address` — string
- `real_estate[].property_value` — decimal
- `real_estate[].status` — enum: Sold, Pending_Sale, Retained
- `real_estate[].intended_occupancy` — enum: Primary, Secondary, Investment, FHA_Secondary
- `real_estate[].monthly_mortgage_payment` — decimal
- `real_estate[].monthly_insurance_taxes` — decimal
- `real_estate[].monthly_rental_income` — decimal
- `real_estate[].monthly_gross_rental` — decimal

---

## Section 7 — Loan and Property Information

- `loan.purpose` — enum: Purchase, Refinance_CashOut, Refinance_RateAndTerm, Construction, ConstructionToPerm, Other
- `loan.property_use` — enum: Primary_Residence, Second_Home, Investment_Property
- `loan.property_type` — enum: SFR, Condo, Townhouse, Cooperative, Manufactured, TwoToFourUnit
- `loan.property_address.street` — string
- `loan.property_address.city` — string
- `loan.property_address.state` — string
- `loan.property_address.zip` — string
- `loan.property_address.county` — string
- `loan.number_of_units` — integer (1–4)
- `loan.year_built` — integer
- `loan.loan_amount` — decimal
- `loan.purchase_price` — decimal
- `loan.appraised_value` — decimal
- `loan.down_payment_amount` — decimal
- `loan.down_payment_source` — enum: Savings, Gift, Sale_of_Asset, Other
- `loan.loan_type` — enum: Conventional, FHA, VA, USDA_RD, Other
- `loan.loan_term_months` — integer (typical: 360, 240, 180, 120)
- `loan.interest_rate` — decimal (e.g., 7.125)
- `loan.amortization_type` — enum: Fixed, ARM, GPM, Other
- `loan.arm_index` — string (if ARM)
- `loan.arm_margin` — decimal (if ARM)

---

## Section 8 — Declarations

Boolean fields (Yes/No) for each borrower:
- `declarations.outstanding_judgments`
- `declarations.bankruptcy_7_years`
- `declarations.foreclosure_7_years`
- `declarations.lawsuit_party`
- `declarations.loan_obligation`
- `declarations.delinquent_federal_debt`
- `declarations.alimony_child_support_obligation`
- `declarations.down_payment_borrowed`
- `declarations.endorser_guarantor`
- `declarations.us_citizen`
- `declarations.permanent_resident_alien`
- `declarations.primary_residence_3_years`
- `declarations.ownership_interest_3_years`
- `declarations.ownership_interest_type` — enum: Sole_Ownership, Joint_Tenancy, Tenancy_Common, Tenancy_Entirety, Other

---

## Section 9 — Military Service (if applicable)
- `military.currently_serving` — boolean
- `military.veteran` — boolean
- `military.surviving_spouse` — boolean
- `military.branch` — enum: Army, Navy, Marines, AirForce, CoastGuard, NationalGuard, Other

---

## Section 10 — Demographic Information (HMDA)
- `hmda.ethnicity` — list of enum: Hispanic_Mexican, Hispanic_PuertoRican, Hispanic_Cuban, Hispanic_Other, Not_Hispanic, Decline
- `hmda.race` — list of enum: AmericanIndian, Asian_Indian, Asian_Chinese, Asian_Filipino, Asian_Japanese, Asian_Korean, Asian_Vietnamese, Asian_Other, Black, NHPI_Guamanian, NHPI_Native_Hawaiian, NHPI_Samoan, NHPI_Other, White, Decline
- `hmda.sex` — enum: Male, Female, Decline
- `hmda.age_obtained_by` — enum: Visual, Surname, NA

---

## Computed / Derived Fields (Ground Truth)

These must be calculated and included in the JSON output:

- `computed.gross_monthly_income` — sum of all income sources
- `computed.total_monthly_debt` — sum of all monthly liability payments (excluding accounts being paid off)
- `computed.proposed_monthly_payment.principal_interest` — calculated from loan amount, rate, term
- `computed.proposed_monthly_payment.taxes` — estimated property taxes / 12
- `computed.proposed_monthly_payment.insurance` — estimated homeowners insurance / 12
- `computed.proposed_monthly_payment.pmi` — if LTV > 80%
- `computed.proposed_monthly_payment.hoa` — if applicable
- `computed.proposed_monthly_payment.total_piti` — sum of above
- `computed.front_end_dti` — (PITI) / (gross monthly income), expressed as decimal
- `computed.back_end_dti` — (PITI + monthly debts) / (gross monthly income), expressed as decimal
- `computed.ltv` — loan_amount / appraised_value
- `computed.cltv` — combined LTV if subordinate financing
- `computed.total_liquid_assets` — sum of depository accounts
- `computed.total_assets` — all assets
- `computed.total_liabilities` — sum of unpaid balances
- `computed.net_worth` — total_assets - total_liabilities
- `computed.months_reserves` — (total_liquid_assets - down_payment - closing_costs) / proposed_monthly_payment.total_piti

---

## Consistency Rules

### Income Consistency
- Employment income must be plausible for stated job title and location
- If self-employed: require 2 years history, use 24-month average income
- Income must support the DTI ratios

### DTI Thresholds (Guideline Defaults)
- Conventional: front-end ≤ 36%, back-end ≤ 45% (DU may allow up to 50%)
- FHA: front-end ≤ 31%, back-end ≤ 43%
- VA: back-end ≤ 41% (no front-end requirement)
- USDA: front-end ≤ 29%, back-end ≤ 41%

### LTV Consistency
- `loan_amount` = `purchase_price` - `down_payment_amount` (for Purchase)
- LTV > 80% → PMI typically required (Conventional)
- LTV > 97% → not permitted for Conventional
- LTV > 96.5% → not permitted for FHA
- VA: up to 100% permitted

### Asset Adequacy
- `down_payment_amount` + estimated closing costs (2-5% of purchase price) must be ≤ `total_liquid_assets` + gift_funds
- Reserves: minimum 2 months PITI for Conventional (some programs require more)

### Employment History
- If current employment < 2 years: must provide prior employer
- Total employment history should span at least 2 years
- Gap > 1 month: must be explained

### Debt Consistency
- Monthly payment on each installment loan should be consistent with balance and remaining months
- Credit card minimum payment: typically 2% of balance

### Address History
- If current address < 2 years: must provide former address
- Former address housing type should be consistent with credit profile
