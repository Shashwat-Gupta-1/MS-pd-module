'use client';

import React from 'react';
import { Card, Badge, CircularGauge } from '../../../../../components/ui/primitives';
import GapQuestionsList from '../../../../../components/GapQuestionsList';
import { useCaseContext } from '../../../../../lib/CaseContext';

export default function GapQuestionsPage() {
    const { questions, navigate } = useCaseContext();

    const allHandled = questions.every(q => q.status !== 'pending');

    return (
        <div className="max-w-4xl mx-auto animate-fadeIn pb-24">
            <h2 className="text-2xl font-bold text-slate-800 mb-6">AI Follow-up Suggestions</h2>

            <Card className="p-5 border-l-4 border-l-teal-600 mb-6">
                <div className="flex justify-between items-start">
                    <div>
                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Detected Profile</p>
                        <h3 className="text-lg font-bold text-slate-800">Self-employed {'>'} Retail {'>'} Grocery Shop</h3>
                    </div>
                    <Badge variant="success">92% Confidence</Badge>
                </div>
            </Card>

            <GapQuestionsList />

            {allHandled && (
                <div className="mt-12 animate-fadeIn">
                    <h2 className="text-2xl font-bold text-slate-800 mb-6">PD Quality Assessment</h2>
                    <Card className="p-6">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-center">
                            <div className="col-span-1 flex justify-center">
                                <CircularGauge value={82} label="Overall Score" size={160} colorClass="text-teal-600" />
                            </div>
                            <div className="col-span-2 space-y-5">
                                <div>
                                    <div className="flex justify-between text-sm font-medium mb-1"><span>Question Coverage</span><span>90%</span></div>
                                    <div className="w-full bg-slate-100 rounded-full h-2"><div className="bg-emerald-500 h-2 rounded-full" style={{width: `90%`}}></div></div>
                                </div>
                                <div>
                                    <div className="flex justify-between text-sm font-medium mb-1"><span>Suggestion Uptake</span><span>75%</span></div>
                                    <div className="w-full bg-slate-100 rounded-full h-2"><div className="bg-amber-400 h-2 rounded-full" style={{width: `75%`}}></div></div>
                                </div>
                                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 mt-4 text-sm text-slate-700">
                                    <span className="font-semibold text-slate-800 block mb-1">Coaching Notes:</span>
                                    Good coverage of core questions. Skipped items marked as "Already covered" do not penalize your score. Next step: explicitly reconfirm numerical values.
                                </div>
                            </div>
                        </div>
                    </Card>
                    <div className="flex justify-end mt-8">
                        <button onClick={() => navigate('/officer/cases/APP-2026-9823/reconfirm')} className="bg-slate-900 hover:bg-slate-800 text-white px-6 py-3 rounded-xl font-semibold shadow-sm transition-colors">
                            Continue to Reconfirmations
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
