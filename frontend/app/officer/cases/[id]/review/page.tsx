'use client';

import React, { useState, useMemo } from 'react';
import { Card } from '../../../../../components/ui/primitives';
import { Icons } from '../../../../../components/ui/Icons';
import ConsistencyFlagBanner from '../../../../../components/ConsistencyFlagBanner';
import EMICalculator from '../../../../../components/EMICalculator';
import OfficerRemarksForm from '../../../../../components/OfficerRemarksForm';
import { useCaseContext } from '../../../../../lib/CaseContext';
import { mockCaseDetails } from '../../../../../lib/mockData';

export default function ReviewPage() {
    const { inconsistencies, observations, generalRemarks, questions } = useCaseContext();
    const [isSubmitted, setIsSubmitted] = useState(false);

    const openIncCount = inconsistencies.filter(i => i.status === 'open').length;

    // Blockers Logic
    const blockers = useMemo(() => {
        const issues = [];
        if (openIncCount > 0) issues.push(`${openIncCount} inconsistencies unresolved.`);
        const pendingQs = questions.filter(q => q.status === 'pending').length;
        if (pendingQs > 0) issues.push(`Unanswered questions in Step 1.`);
        if (generalRemarks.trim().length < 10) issues.push("Final assessment remarks are too short.");
        return issues;
    }, [openIncCount, questions, generalRemarks]);

    if (isSubmitted) {
        return (
            <div className="min-h-[80vh] flex flex-col items-center justify-center animate-fadeIn">
                <Card className="p-8 max-w-md w-full text-center">
                    <div className="w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6">
                        <Icons.CheckCircle className="w-10 h-10 text-emerald-600" />
                    </div>
                    <h1 className="text-2xl font-bold text-slate-800 mb-2">PD Successfully Submitted</h1>
                    <p className="text-slate-600 mb-6">Case ID: {mockCaseDetails.id}</p>
                    <div className="bg-slate-50 rounded-xl p-4 text-left mb-8 space-y-3 border border-slate-100">
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Officer Score</span><span className="font-bold text-slate-800">82/100</span></div>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Consistency Risk</span><span className="font-bold text-amber-600">Medium</span></div>
                        <div className="flex justify-between text-sm"><span className="text-slate-500">Observations</span><span className="font-bold text-slate-800">{observations.length}</span></div>
                    </div>
                    <button onClick={() => window.location.reload()} className="w-full bg-slate-900 hover:bg-slate-800 text-white py-3 rounded-xl font-semibold transition-colors">
                        Return to Dashboard
                    </button>
                </Card>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto animate-fadeIn pb-32">
            <h2 className="text-2xl font-bold text-slate-800 mb-6">Final Review & Submission</h2>

            <ConsistencyFlagBanner />

            <div className="mb-8">
                <EMICalculator principal={mockCaseDetails.amount} tenureMonths={mockCaseDetails.tenure} declaredIncome={45000} />
            </div>

            <OfficerRemarksForm />

            {/* Sticky Footer */}
            <div className="fixed bottom-0 left-0 md:left-72 right-0 bg-white border-t border-slate-200 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)] z-50 p-4">
                <div className="max-w-4xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
                    <div className="flex-1">
                        {blockers.length === 0 ? (
                            <div className="flex items-center gap-2 text-emerald-600"><Icons.CheckCircle className="w-5 h-5" /><span className="font-semibold text-sm">All checks passed. Ready to submit.</span></div>
                        ) : (
                            <div className="text-sm"><span className="font-semibold text-red-600 flex items-center gap-1 mb-1"><Icons.AlertTriangle className="w-4 h-4"/> Cannot submit yet. Fix:</span>
                                <ul className="list-disc list-inside text-slate-600 text-xs">{blockers.map((b, i) => <li key={i}>{b}</li>)}</ul>
                            </div>
                        )}
                    </div>
                    <button onClick={() => setIsSubmitted(true)} disabled={blockers.length > 0} className={`px-8 py-3 rounded-xl font-bold shadow-sm transition-all whitespace-nowrap ${blockers.length === 0 ? 'bg-slate-900 hover:bg-slate-800 text-white' : 'bg-slate-200 text-slate-400 cursor-not-allowed'}`}>
                        Submit PD Report
                    </button>
                </div>
            </div>
        </div>
    );
}
