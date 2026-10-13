"""Pure deterministic credit underwriting calculation functions.

Includes:
- calculate_emi: Reducing balance Equated Monthly Installment.
- calculate_foir: Fixed Obligation to Income Ratio (%).
- calculate_ltv: Loan to Value Ratio (%) and status flag.

Zero LLM interaction. Must be covered by comprehensive unit tests.
"""

from typing import Optional, Tuple


def calculate_emi(principal: float, annual_rate_pct: float, tenure_months: int) -> float:
    """Calculate the reducing balance EMI.
    
    Formula: E = P * r * (1 + r)^n / ((1 + r)^n - 1)
    where:
      P = Principal loan amount
      r = Monthly interest rate (annual_rate_pct / 12 / 100)
      n = Tenure in months
    """
    if tenure_months <= 0:
        raise ValueError("Tenure months must be greater than 0.")
    if principal <= 0:
        return 0.0
    if annual_rate_pct < 0:
        raise ValueError("Annual interest rate cannot be negative.")
        
    # Zero interest edge case (e.g. promotional 0% interest loan)
    if annual_rate_pct == 0:
        return round(principal / tenure_months, 2)
        
    monthly_rate = (annual_rate_pct / 12.0) / 100.0
    growth_factor = (1.0 + monthly_rate) ** tenure_months
    
    emi = principal * monthly_rate * growth_factor / (growth_factor - 1.0)
    return round(emi, 2)


def calculate_foir(total_obligations_incl_new_emi: float, net_monthly_income: float) -> float:
    """Calculate Fixed Obligation to Income Ratio (FOIR %).
    
    Formula: (Total Monthly Obligations including Proposed EMI / Net Monthly Income) * 100
    """
    if net_monthly_income <= 0:
        raise ValueError("Net monthly income must be greater than zero to calculate FOIR.")
    if total_obligations_incl_new_emi < 0:
        raise ValueError("Obligations cannot be negative.")
        
    foir = (total_obligations_incl_new_emi / net_monthly_income) * 100.0
    return round(foir, 2)


def calculate_ltv(
    loan_amount: float,
    collateral_value: Optional[float] = None,
    is_secured: bool = True
) -> Tuple[Optional[float], str]:
    """Calculate Loan-to-Value (LTV %) and determine LTV status.
    
    Statuses:
    - 'computed': Collateral value is verified and LTV is calculated.
    - 'not_applicable': Unsecured loan product.
    - 'pending_collateral_valuation': Secured loan product where valuation has not been completed.
    """
    if not is_secured:
        return None, "not_applicable"
        
    if collateral_value is None or collateral_value <= 0:
        return None, "pending_collateral_valuation"
        
    if loan_amount <= 0:
        return 0.0, "computed"
        
    ltv = (loan_amount / collateral_value) * 100.0
    return round(ltv, 2), "computed"
