'use client';

import React, { useState } from 'react';
import { Card, Badge } from './ui/primitives';
import { Icons } from './ui/Icons';
import { useCaseContext } from '../lib/CaseContext';
import type { QuestionStatus } from '../lib/types';

export default function GapQuestionsList() {
    const { questions, setQuestions } = useCaseContext();
    const [openDropdownId, setOpenDropdownId] = useState<string | null>(null);

    const handleAction = (id: string, action: QuestionStatus, skipReason: string | null = null) => {
        setQuestions(prev => prev.map(q => q.id === id ? { ...q, status: action, skipReason } : q));
        setOpenDropdownId(null);
    };

    const handleAnswer = (id: string, ans: string) => {
        setQuestions(prev => prev.map(q => q.id === id ? { ...q, answer: ans } : q));
    };

    return (
        <div className="space-y-4">
            {questions.map(q => (
                <Card key={q.id} className={`overflow-visible transition-all ${q.status !== 'pending' ? 'opacity-70 bg-slate-50' : 'border-teal-200 shadow-md'}`}>
                    <div className="p-5">
                        <div className="flex gap-2 items-center mb-3">
                            <Badge variant="primary"><Icons.Tag className="w-3 h-3 inline mr-1"/> {q.tag}</Badge>
                            {q.status === 'asked' && <Badge variant="success">Asked</Badge>}
                            {q.status === 'skipped' && <Badge variant="default">Skipped</Badge>}
                            {q.status === 'differently' && <Badge variant="warning">Asked Diff.</Badge>}
                        </div>

                        <h3 className="text-lg font-semibold text-slate-800 mb-1">{q.text}</h3>
                        <p className="text-sm text-slate-500 mb-4 bg-slate-100 p-2 rounded-lg border border-slate-200 inline-block">
                            <span className="font-semibold mr-1">Why ask:</span> {q.reason}
                        </p>

                        {q.status === 'pending' ? (
                            <div className="flex flex-wrap gap-2">
                                <button onClick={() => handleAction(q.id, 'asked')} className="px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-medium hover:bg-slate-800 transition-colors">Mark as Asked</button>
                                <button onClick={() => handleAction(q.id, 'differently')} className="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-200 transition-colors">Asked Differently</button>

                                <div className="relative">
                                    <button onClick={() => setOpenDropdownId(openDropdownId === q.id ? null : q.id)} className="px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors flex items-center gap-1">
                                        Skip <Icons.ChevronDown className="w-4 h-4" />
                                    </button>
                                    {openDropdownId === q.id && (
                                        <div className="absolute w-48 bg-white border border-slate-200 shadow-lg rounded-lg mt-1 z-50 left-0 py-1">
                                            <button onClick={() => handleAction(q.id, 'skipped', 'Already covered')} className="w-full text-left px-4 py-2 text-sm hover:bg-slate-50">Already covered</button>
                                            <button onClick={() => handleAction(q.id, 'skipped', 'Not applicable')} className="w-full text-left px-4 py-2 text-sm hover:bg-slate-50">Not applicable</button>
                                            <button onClick={() => handleAction(q.id, 'skipped', 'Forgot')} className="w-full text-left px-4 py-2 text-sm hover:bg-slate-50 text-red-600">Forgot to ask</button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ) : (
                            <div className="mt-4 pt-4 border-t border-slate-200">
                                {q.status === 'skipped' ? (
                                    <p className="text-sm text-slate-500 italic">Skipped reason: {q.skipReason}</p>
                                ) : (
                                    <div className="space-y-3">
                                        <label className="block text-sm font-medium text-slate-700">Borrower's Answer / Notes:</label>
                                        <textarea className="w-full p-3 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:outline-none" rows={2} value={q.answer} onChange={(e) => handleAnswer(q.id, e.target.value)}></textarea>
                                    </div>
                                )}
                                <button onClick={() => handleAction(q.id, 'pending')} className="mt-3 text-xs font-medium text-teal-700 hover:underline">Reset Action</button>
                            </div>
                        )}
                    </div>
                </Card>
            ))}
        </div>
    );
}
