'use client';

import React, { useState, useMemo } from 'react';
import { Card } from './ui/primitives';
import { Icons } from './ui/Icons';

export default function EMICalculator({ principal, tenureMonths, declaredIncome }: { principal: number, tenureMonths: number, declaredIncome: number }) {
    const [rate, setRate] = useState(18.5); // Default interest rate

    const emi = useMemo(() => {
        const r = rate / 12 / 100;
        const n = tenureMonths;
        if (r === 0) return principal / n;
        return Math.round((principal * r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1));
    }, [principal, rate, tenureMonths]);

    const foir = declaredIncome > 0 ? ((emi / declaredIncome) * 100).toFixed(1) : 'N/A';

    return (
        <Card className="p-5 bg-teal-50 border-teal-100">
            <h3 className="font-bold text-teal-900 mb-4 flex items-center gap-2"><Icons.Briefcase className="w-5 h-5"/> Quick Affordability Check</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 items-end">
                <div>
                    <label className="block text-xs font-semibold text-teal-700 mb-1">Loan Amount</label>
                    <div className="text-sm font-semibold text-slate-800">₹{principal.toLocaleString()}</div>
                </div>
                <div>
                    <label className="block text-xs font-semibold text-teal-700 mb-1">Tenure</label>
                    <div className="text-sm font-semibold text-slate-800">{tenureMonths} Months</div>
                </div>
                <div>
                    <label className="block text-xs font-semibold text-teal-700 mb-1">Interest Rate (%)</label>
                    <input type="number" step="0.1" value={rate} onChange={(e) => setRate(Number(e.target.value))} className="w-full text-sm border-teal-200 rounded-md py-1.5 px-3 focus:ring-teal-500" />
                </div>
                <div className="bg-white p-3 rounded-lg border border-teal-100 shadow-sm">
                    <label className="block text-[10px] font-bold text-teal-600 uppercase tracking-wider mb-1">Estimated EMI</label>
                    <div className="text-xl font-bold text-slate-800">₹{emi.toLocaleString()}</div>
                    <div className="text-xs text-slate-500 mt-1">FOIR: <span className={Number(foir) > 50 ? 'text-red-600 font-bold' : 'text-emerald-600 font-bold'}>{foir}%</span></div>
                </div>
            </div>
        </Card>
    );
}
