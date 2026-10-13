'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { Card, Badge } from './ui/primitives';
import { Icons } from './ui/Icons';

export interface EMICalculatorProps {
    principal?: number;
    tenureMonths?: number;
    declaredIncome?: number;
    interestRate?: number;
    existingObligations?: number;
    collateralValue?: number;
    isSecured?: boolean;
    onValuesChange?: (values: {
        principal: number;
        tenure: number;
        rate: number;
        emi: number;
        foir: number;
        ltc: number | null;
    }) => void;
}

export default function EMICalculator({
    principal = 500000,
    tenureMonths = 24,
    declaredIncome = 45000,
    interestRate = 18.5,
    existingObligations = 0,
    collateralValue = 750000,
    isSecured = true,
    onValuesChange,
}: EMICalculatorProps) {
    // Interactive State
    const [loanAmount, setLoanAmount] = useState<number>(principal);
    const [tenure, setTenure] = useState<number>(tenureMonths);
    const [rate, setRate] = useState<number>(interestRate);
    const [income, setIncome] = useState<number>(declaredIncome);
    const [obligations, setObligations] = useState<number>(existingObligations);
    const [collateral, setCollateral] = useState<number>(collateralValue);
    const [securedLoan, setSecuredLoan] = useState<boolean>(isSecured);
    const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

    // Sync if parent props change
    useEffect(() => {
        if (principal && principal !== loanAmount) setLoanAmount(principal);
    }, [principal]);

    useEffect(() => {
        if (tenureMonths && tenureMonths !== tenure) setTenure(tenureMonths);
    }, [tenureMonths]);

    useEffect(() => {
        if (declaredIncome && declaredIncome !== income) setIncome(declaredIncome);
    }, [declaredIncome]);

    // 1. Deterministic EMI Calculation
    const { emi, totalRepayment, totalInterest } = useMemo(() => {
        if (loanAmount <= 0 || tenure <= 0) {
            return { emi: 0, totalRepayment: 0, totalInterest: 0 };
        }
        if (rate <= 0) {
            const e = Math.round(loanAmount / tenure);
            return { emi: e, totalRepayment: loanAmount, totalInterest: 0 };
        }
        const monthlyRate = rate / 12 / 100;
        const growth = Math.pow(1 + monthlyRate, tenure);
        const calculatedEmi = Math.round((loanAmount * monthlyRate * growth) / (growth - 1));
        const total = calculatedEmi * tenure;
        return {
            emi: calculatedEmi,
            totalRepayment: total,
            totalInterest: Math.max(0, total - loanAmount),
        };
    }, [loanAmount, rate, tenure]);

    // 2. Deterministic FOIR Calculation (%)
    const foir = useMemo(() => {
        if (income <= 0) return 0;
        const totalMonthlyDebt = emi + obligations;
        return Number(((totalMonthlyDebt / income) * 100).toFixed(1));
    }, [emi, obligations, income]);

    // 3. Deterministic LTC / LTV Calculation (%)
    const ltc = useMemo(() => {
        if (!securedLoan) return null;
        if (collateral <= 0) return null;
        return Number(((loanAmount / collateral) * 100).toFixed(1));
    }, [securedLoan, loanAmount, collateral]);

    // Notify parent if callback provided
    useEffect(() => {
        if (onValuesChange) {
            onValuesChange({
                principal: loanAmount,
                tenure,
                rate,
                emi,
                foir,
                ltc,
            });
        }
    }, [loanAmount, tenure, rate, emi, foir, ltc, onValuesChange]);

    // FOIR policy risk level
    const foirStatus = useMemo(() => {
        if (income <= 0) return { label: 'Income Required', color: 'text-slate-500', bg: 'bg-slate-100', badge: 'neutral' };
        if (foir <= 50) return { label: 'Low Risk (≤50%)', color: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200', badge: 'success' };
        if (foir <= 60) return { label: 'Moderate Risk (50-60%)', color: 'text-amber-700', bg: 'bg-amber-50 border-amber-200', badge: 'warning' };
        return { label: 'High Risk (>60% Stretched)', color: 'text-red-700', bg: 'bg-red-50 border-red-200', badge: 'critical' };
    }, [foir, income]);

    // LTC policy risk level
    const ltcStatus = useMemo(() => {
        if (!securedLoan) return { label: 'Unsecured Product', color: 'text-slate-600', bg: 'bg-slate-50 border-slate-200', badge: 'neutral' };
        if (ltc === null) return { label: 'Pending Valuation', color: 'text-amber-700', bg: 'bg-amber-50 border-amber-200', badge: 'warning' };
        if (ltc <= 75) return { label: 'Adequate Coverage (≤75%)', color: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200', badge: 'success' };
        if (ltc <= 90) return { label: 'Borderline Cushion (75-90%)', color: 'text-amber-700', bg: 'bg-amber-50 border-amber-200', badge: 'warning' };
        return { label: 'Under-collateralized (>90%)', color: 'text-red-700', bg: 'bg-red-50 border-red-200', badge: 'critical' };
    }, [securedLoan, ltc]);

    return (
        <Card className="p-6 bg-gradient-to-br from-white to-slate-50 border-slate-200 shadow-md">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 mb-5 border-b border-slate-200 gap-3">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-teal-600/10 text-teal-700 flex items-center justify-center font-bold">
                        <Icons.Briefcase className="w-5 h-5" />
                    </div>
                    <div>
                        <h3 className="font-bold text-slate-800 text-base flex items-center gap-2">
                            <span>Prudential Underwriting Calculator</span>
                            <span className="text-xs px-2 py-0.5 rounded-full font-semibold bg-teal-100 text-teal-800">
                                EMI • FOIR • LTC
                            </span>
                        </h3>
                        <p className="text-xs text-slate-500">
                            Pure deterministic credit math adhering to prudential micro-enterprise lending norms.
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className="text-xs font-semibold text-teal-700 hover:text-teal-800 px-3 py-1.5 rounded-lg border border-teal-200 hover:bg-teal-50 transition flex items-center gap-1.5"
                    >
                        <Icons.Edit className="w-3.5 h-3.5" />
                        <span>{showAdvanced ? 'Simple View' : 'Adjust Debt & Collateral'}</span>
                    </button>
                </div>
            </div>

            {/* 3 Major Metric Result Cards (EMI, FOIR, LTC) */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                {/* 1. EMI Card */}
                <div className="bg-white p-4 rounded-xl border border-teal-200/80 shadow-sm relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-24 h-24 bg-teal-50 rounded-bl-full -z-0 opacity-60"></div>
                    <div className="relative z-10">
                        <div className="flex items-center justify-between mb-1">
                            <span className="text-[11px] font-bold uppercase tracking-wider text-teal-700">Estimated EMI</span>
                            <span className="text-[10px] font-semibold text-slate-400">Monthly</span>
                        </div>
                        <div className="text-2xl font-black text-slate-900 tracking-tight">
                            ₹{emi.toLocaleString('en-IN')}
                        </div>
                        <div className="mt-2 pt-2 border-t border-slate-100 flex justify-between text-[11px] text-slate-500 font-medium">
                            <span>Total Repayment:</span>
                            <span className="font-semibold text-slate-700">₹{totalRepayment.toLocaleString('en-IN')}</span>
                        </div>
                        <div className="flex justify-between text-[11px] text-slate-500 font-medium">
                            <span>Total Interest:</span>
                            <span className="font-semibold text-teal-700">₹{totalInterest.toLocaleString('en-IN')}</span>
                        </div>
                    </div>
                </div>

                {/* 2. FOIR Card */}
                <div className={`p-4 rounded-xl border shadow-sm relative overflow-hidden ${foirStatus.bg}`}>
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                            FOIR (Fixed Obligation)
                        </span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            foir <= 50 ? 'bg-emerald-100 text-emerald-800' :
                            foir <= 60 ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'
                        }`}>
                            {foirStatus.label}
                        </span>
                    </div>
                    <div className={`text-2xl font-black tracking-tight ${foirStatus.color}`}>
                        {income > 0 ? `${foir}%` : 'N/A'}
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full bg-slate-200 rounded-full h-1.5 mt-2.5 overflow-hidden">
                        <div
                            className={`h-1.5 rounded-full transition-all duration-300 ${
                                foir <= 50 ? 'bg-emerald-500' : foir <= 60 ? 'bg-amber-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${Math.min(100, foir)}%` }}
                        ></div>
                    </div>

                    <div className="mt-2 flex justify-between text-[11px] text-slate-500 font-medium">
                        <span>Net Monthly Income:</span>
                        <span className="font-semibold text-slate-700">₹{income.toLocaleString('en-IN')}</span>
                    </div>
                </div>

                {/* 3. LTC / LTV Card */}
                <div className={`p-4 rounded-xl border shadow-sm relative overflow-hidden ${ltcStatus.bg}`}>
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                            LTC / LTV (Collateral Cover)
                        </span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            !securedLoan ? 'bg-slate-200 text-slate-700' :
                            ltc === null ? 'bg-amber-100 text-amber-800' :
                            ltc <= 75 ? 'bg-emerald-100 text-emerald-800' :
                            ltc <= 90 ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'
                        }`}>
                            {ltcStatus.label}
                        </span>
                    </div>
                    <div className={`text-2xl font-black tracking-tight ${ltcStatus.color}`}>
                        {securedLoan ? (ltc !== null ? `${ltc}%` : 'Pending') : 'Unsecured'}
                    </div>

                    {/* Progress Bar for LTC */}
                    {securedLoan && ltc !== null && (
                        <div className="w-full bg-slate-200 rounded-full h-1.5 mt-2.5 overflow-hidden">
                            <div
                                className={`h-1.5 rounded-full transition-all duration-300 ${
                                    ltc <= 75 ? 'bg-emerald-500' : ltc <= 90 ? 'bg-amber-500' : 'bg-red-500'
                                }`}
                                style={{ width: `${Math.min(100, ltc)}%` }}
                            ></div>
                        </div>
                    )}

                    <div className="mt-2 flex justify-between text-[11px] text-slate-500 font-medium">
                        <span>Collateral Valuation:</span>
                        <span className="font-semibold text-slate-700">
                            {securedLoan ? `₹${collateral.toLocaleString('en-IN')}` : 'Not Applicable'}
                        </span>
                    </div>
                </div>
            </div>

            {/* Interactive Inputs Grid */}
            <div className="bg-slate-50/70 p-4 rounded-xl border border-slate-200/80">
                <div className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-3">
                    Underwriting Scenario Parameters
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {/* Loan Amount */}
                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">
                            Loan Amount (Principal ₹)
                        </label>
                        <div className="relative">
                            <span className="absolute left-3 top-2 text-sm text-slate-400 font-bold">₹</span>
                            <input
                                type="number"
                                step="10000"
                                min="10000"
                                value={loanAmount}
                                onChange={(e) => setLoanAmount(Math.max(0, Number(e.target.value)))}
                                className="w-full pl-7 pr-3 py-1.5 text-sm font-semibold text-slate-800 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
                            />
                        </div>
                    </div>

                    {/* Tenure */}
                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">
                            Tenure (Months)
                        </label>
                        <div className="flex items-center gap-1.5">
                            <input
                                type="number"
                                min="3"
                                max="120"
                                value={tenure}
                                onChange={(e) => setTenure(Math.max(1, Number(e.target.value)))}
                                className="w-20 px-3 py-1.5 text-sm font-semibold text-slate-800 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500"
                            />
                            <div className="flex items-center gap-1 flex-1">
                                {[12, 24, 36, 60].map((t) => (
                                    <button
                                        key={t}
                                        type="button"
                                        onClick={() => setTenure(t)}
                                        className={`px-2 py-1.5 text-xs font-bold rounded border transition ${
                                            tenure === t
                                                ? 'bg-teal-600 text-white border-teal-600'
                                                : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-100'
                                        }`}
                                    >
                                        {t}M
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Interest Rate */}
                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">
                            Interest Rate (% per annum)
                        </label>
                        <div className="relative">
                            <input
                                type="number"
                                step="0.25"
                                min="0"
                                max="40"
                                value={rate}
                                onChange={(e) => setRate(Number(e.target.value))}
                                className="w-full pr-8 pl-3 py-1.5 text-sm font-semibold text-slate-800 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
                            />
                            <span className="absolute right-3 top-2 text-xs text-slate-400 font-bold">%</span>
                        </div>
                    </div>
                </div>

                {/* Advanced Parameters: Income, Obligations, Collateral (Shown if toggled) */}
                {showAdvanced && (
                    <div className="mt-4 pt-4 border-t border-slate-200 grid grid-cols-1 sm:grid-cols-3 gap-4 animate-fadeIn">
                        {/* Monthly Income */}
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">
                                Net Monthly Income (₹)
                            </label>
                            <div className="relative">
                                <span className="absolute left-3 top-2 text-sm text-slate-400 font-bold">₹</span>
                                <input
                                    type="number"
                                    step="5000"
                                    min="0"
                                    value={income}
                                    onChange={(e) => setIncome(Math.max(0, Number(e.target.value)))}
                                    className="w-full pl-7 pr-3 py-1.5 text-sm font-semibold text-slate-800 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500"
                                />
                            </div>
                            <span className="text-[10px] text-slate-500 mt-0.5 block">Denominator for FOIR</span>
                        </div>

                        {/* Existing Monthly Debt Obligations */}
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">
                                Other Monthly EMIs / Obligations (₹)
                            </label>
                            <div className="relative">
                                <span className="absolute left-3 top-2 text-sm text-slate-400 font-bold">₹</span>
                                <input
                                    type="number"
                                    step="1000"
                                    min="0"
                                    value={obligations}
                                    onChange={(e) => setObligations(Math.max(0, Number(e.target.value)))}
                                    className="w-full pl-7 pr-3 py-1.5 text-sm font-semibold text-slate-800 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500"
                                />
                            </div>
                            <span className="text-[10px] text-slate-500 mt-0.5 block">Existing bank/NBFC loans</span>
                        </div>

                        {/* Collateral / Security Valuation */}
                        <div>
                            <div className="flex items-center justify-between mb-1">
                                <label className="block text-xs font-semibold text-slate-700">
                                    Collateral / Asset Valuation (₹)
                                </label>
                                <label className="flex items-center gap-1 text-[11px] font-semibold text-slate-600 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={securedLoan}
                                        onChange={(e) => setSecuredLoan(e.target.checked)}
                                        className="rounded text-teal-600 focus:ring-teal-500 h-3.5 w-3.5"
                                    />
                                    <span>Secured</span>
                                </label>
                            </div>
                            <div className="relative">
                                <span className="absolute left-3 top-2 text-sm text-slate-400 font-bold">₹</span>
                                <input
                                    type="number"
                                    step="25000"
                                    min="0"
                                    disabled={!securedLoan}
                                    value={securedLoan ? collateral : 0}
                                    onChange={(e) => setCollateral(Math.max(0, Number(e.target.value)))}
                                    className={`w-full pl-7 pr-3 py-1.5 text-sm font-semibold rounded-lg border ${
                                        securedLoan
                                            ? 'text-slate-800 bg-white border-slate-300 focus:ring-2 focus:ring-teal-500'
                                            : 'text-slate-400 bg-slate-100 border-slate-200 cursor-not-allowed'
                                    }`}
                                />
                            </div>
                            <span className="text-[10px] text-slate-500 mt-0.5 block">Denominator for LTC / LTV</span>
                        </div>
                    </div>
                )}
            </div>
        </Card>
    );
}
