'use client';

import React from 'react';
import { Icons } from '../../../../../components/ui/Icons';
import { useCaseContext } from '../../../../../lib/CaseContext';

export default function ReconfirmPage() {
    const { questions, setQuestions, navigate } = useCaseContext();

    const reconfirmQs = questions.filter(q => q.isNumeric || q.lowConfidence);
    const allReconfirmed = reconfirmQs.every(q => q.isReconfirmed);

    const toggleConfirm = (id: string) => {
        setQuestions(prev => prev.map(q => q.id === id ? { ...q, isReconfirmed: !q.isReconfirmed } : q));
    };

    return (
        <div className="max-w-4xl mx-auto animate-fadeIn pb-24">
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Value Reconfirmation</h2>
            <p className="text-slate-600 mb-6">Please verbally confirm these critical figures with the borrower based on AI transcription.</p>

            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3 mb-6">
                <Icons.AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <div>
                    <h4 className="font-semibold text-amber-800 text-sm">Low Confidence Audio Flag</h4>
                    <p className="text-sm text-amber-700 mt-1">Audio was unclear for rent values. Please pay special attention to Expense fields below.</p>
                </div>
            </div>

            <div className="space-y-4">
                {reconfirmQs.map(q => (
                    <div key={q.id} className={`p-4 rounded-xl border-2 transition-colors ${q.isReconfirmed ? 'bg-emerald-50 border-emerald-200' : 'bg-white border-slate-200 shadow-sm'}`}>
                        <div className="flex justify-between items-start">
                            <div>
                                <p className="text-xs font-semibold text-slate-500 uppercase">{q.tag}</p>
                                <h3 className="text-lg font-bold text-slate-800 mt-1">{q.text}</h3>
                                {q.answer ? <p className="text-sm text-slate-600 mt-2 bg-slate-100 px-3 py-2 rounded-lg border border-slate-200">Transcribed Answer: <strong>{q.answer}</strong></p> : null}
                            </div>
                            <label className="flex items-center gap-2 cursor-pointer bg-white px-4 py-2 rounded-full border shadow-sm hover:bg-slate-50">
                                <input type="checkbox" checked={!!q.isReconfirmed} onChange={() => toggleConfirm(q.id)} className="w-5 h-5 text-teal-600 rounded border-slate-300 focus:ring-teal-500" />
                                <span className="font-semibold text-sm text-slate-700">Confirmed</span>
                            </label>
                        </div>
                    </div>
                ))}
            </div>

            <div className="flex justify-end mt-8 gap-4">
                <button onClick={() => navigate('/officer/cases/APP-2026-9823/gap-questions')} className="text-slate-600 font-medium px-4">Back</button>
                <button
                    onClick={() => navigate('/officer/cases/APP-2026-9823/photos')}
                    disabled={!allReconfirmed}
                    className={`px-6 py-3 rounded-xl font-semibold shadow-sm transition-colors ${allReconfirmed ? 'bg-slate-900 text-white hover:bg-slate-800' : 'bg-slate-200 text-slate-400 cursor-not-allowed'}`}
                >
                    Continue to Photos
                </button>
            </div>
        </div>
    );
}
