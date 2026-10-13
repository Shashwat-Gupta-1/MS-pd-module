import pytest
from app.calculations.emi_foir_ltv import calculate_emi, calculate_foir, calculate_ltv


class TestCalculateEMI:
    def test_standard_emi_case(self):
        # 5 Lakhs at 14% for 36 months: Exact reducing balance EMI = 17088.81
        emi = calculate_emi(principal=500000.0, annual_rate_pct=14.0, tenure_months=36)
        assert emi == 17088.81

    def test_one_year_personal_loan(self):
        # 1 Lakh at 12% for 12 months
        emi = calculate_emi(principal=100000.0, annual_rate_pct=12.0, tenure_months=12)
        assert emi == 8884.88

    def test_zero_interest_rate(self):
        # 60,000 at 0% for 12 months = 5,000/month
        emi = calculate_emi(principal=60000.0, annual_rate_pct=0.0, tenure_months=12)
        assert emi == 5000.0

    def test_zero_principal(self):
        emi = calculate_emi(principal=0.0, annual_rate_pct=14.0, tenure_months=36)
        assert emi == 0.0

    def test_invalid_tenure_raises(self):
        with pytest.raises(ValueError, match="Tenure months must be greater than 0"):
            calculate_emi(principal=100000.0, annual_rate_pct=12.0, tenure_months=0)

        with pytest.raises(ValueError, match="Tenure months must be greater than 0"):
            calculate_emi(principal=100000.0, annual_rate_pct=12.0, tenure_months=-12)

    def test_negative_interest_raises(self):
        with pytest.raises(ValueError, match="Annual interest rate cannot be negative"):
            calculate_emi(principal=100000.0, annual_rate_pct=-5.0, tenure_months=12)


class TestCalculateFOIR:
    def test_standard_foir_case(self):
        # Obligations 25k on 50k income = 50%
        foir = calculate_foir(total_obligations_incl_new_emi=25000.0, net_monthly_income=50000.0)
        assert foir == 50.0

    def test_foir_precision(self):
        # Obligations 17,088.73 on 45,000 income
        foir = calculate_foir(total_obligations_incl_new_emi=17088.73, net_monthly_income=45000.0)
        assert foir == 37.97

    def test_zero_obligations(self):
        foir = calculate_foir(total_obligations_incl_new_emi=0.0, net_monthly_income=45000.0)
        assert foir == 0.0

    def test_zero_income_raises(self):
        with pytest.raises(ValueError, match="Net monthly income must be greater than zero"):
            calculate_foir(total_obligations_incl_new_emi=15000.0, net_monthly_income=0.0)

    def test_negative_income_raises(self):
        with pytest.raises(ValueError, match="Net monthly income must be greater than zero"):
            calculate_foir(total_obligations_incl_new_emi=15000.0, net_monthly_income=-20000.0)

    def test_negative_obligations_raises(self):
        with pytest.raises(ValueError, match="Obligations cannot be negative"):
            calculate_foir(total_obligations_incl_new_emi=-500.0, net_monthly_income=40000.0)


class TestCalculateLTV:
    def test_standard_secured_ltv(self):
        # Loan 5 Lakhs on 10 Lakhs property = 50%
        ltv, status = calculate_ltv(loan_amount=500000.0, collateral_value=1000000.0, is_secured=True)
        assert ltv == 50.0
        assert status == "computed"

    def test_unsecured_loan_not_applicable(self):
        # Clean personal loan without collateral
        ltv, status = calculate_ltv(loan_amount=200000.0, collateral_value=None, is_secured=False)
        assert ltv is None
        assert status == "not_applicable"

    def test_secured_pending_valuation(self):
        # Secured loan but collateral has not been valued yet
        ltv, status = calculate_ltv(loan_amount=500000.0, collateral_value=None, is_secured=True)
        assert ltv is None
        assert status == "pending_collateral_valuation"

    def test_secured_zero_valuation_pending(self):
        ltv, status = calculate_ltv(loan_amount=500000.0, collateral_value=0.0, is_secured=True)
        assert ltv is None
        assert status == "pending_collateral_valuation"
