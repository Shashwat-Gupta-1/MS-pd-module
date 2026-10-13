'use client';

import React, { useState, useEffect } from 'react';
import { Icons } from '../../../../../components/ui/Icons';
import { useCaseContext } from '../../../../../lib/CaseContext';
import { pdSessionsApi } from '../../../../../lib/api';
import { Question } from '../../../../../lib/types';
import { getInferredDataForQuestion } from '../../../../../components/GapQuestionsList';

// Helper to clean trailing .0 from string numbers
function cleanNumericValue(val: any): string {
    if (val === undefined || val === null) return '';
    const s = String(val).trim();
    if (/^\d+\.0$/.test(s)) {
        return s.slice(0, -2);
    }
    return s;
}

// Helper to determine if a question is strictly numeric
function isNumericQuestion(q: Question): boolean {
    if (q.isNumeric) return true;

    const text = (q.text || '').toLowerCase();
    const tag = (q.tag || '').toLowerCase();
    const field = (q.fieldName || '').toLowerCase();
    const combined = `${text} ${tag} ${field}`;

    // Negative filters: purely qualitative questions
    if (/^(what is your business activity|what is the name|who is the reference|describe|power backup|infrastructure|delivery model|ownership status)/i.test(text)) {
        return false;
    }
    if (field === 'past_loan_history' || /pehle koi loan liya tha jo ab band/i.test(text)) {
        return false;
    }

    // Positive numeric keywords
    const numericKeywords = /(amount|turnover|sales|income|salary|revenue|cost|expense|emi|margin|profit|rent|price|units|litres|cows|buffaloes|acres|years|months|balance|obligation|requested_amount|dependents_education)/i;
    if (numericKeywords.test(combined)) {
        return true;
    }

    // Check if the current value is purely numeric
    const val = q.inferredValue ?? q.answer;
    if (val !== undefined && val !== null && String(val).trim().length > 0) {
        const valStr = String(val).replace(/₹|,|\s/g, '');
        if (!isNaN(Number(valStr)) && valStr.length > 0) {
            return true;
        }
    }

    return false;
}

export default function ReconfirmPage({ params }: { params: { id: string } }) {
    const { questions, setQuestions, navigate, applicationId, sessionId, setSessionId, loadApplicationData } = useCaseContext();

    const effectiveAppId = params?.id || applicationId || 'APP-2026-9823';

    const [liveState, setLiveState] = useState<any>(null);
    // Local edits map for field values before/during confirmation
    const [editedValues, setEditedValues] = useState<Record<string, string>>({});

    // 1. One-shot load of case profile and dynamic tiered questionnaire
    const loadedAppIdRef = React.useRef<string | null>(null);
    useEffect(() => {
        if (effectiveAppId && loadedAppIdRef.current !== effectiveAppId) {
            loadedAppIdRef.current = effectiveAppId;
            loadApplicationData(effectiveAppId);
        }
    }, [effectiveAppId, loadApplicationData]);

    // 2. Fetch active session and poll live state smoothly without re-rendering loops
    useEffect(() => {
        let mounted = true;

        async function fetchLive() {
            let activeId = sessionId;
            if (!activeId && effectiveAppId) {
                try {
                    const act = await pdSessionsApi.getActiveForApplication(effectiveAppId);
                    if (act?.id) {
                        activeId = act.id;
                        if (mounted) {
                            setSessionId(act.id);
                        }
                    }
                } catch (e) {
                    console.warn('Could not query active session:', e);
                }
            }
            if (activeId) {
                try {
                    const st = await pdSessionsApi.getLiveState(activeId);
                    if (mounted && st) {
                        setLiveState(st);
                    }
                } catch (e) {
                    console.warn('Could not fetch live state in reconfirm:', e);
                }
            }
        }

        fetchLive();
        const poll = setInterval(fetchLive, 4000);
        return () => {
            mounted = false;
            clearInterval(poll);
        };
    }, [sessionId, effectiveAppId, setSessionId]);

    // Strictly filter for numeric questions that are either inferred, answered, or designated as numeric
    const reconfirmQs = questions.filter(q => isNumericQuestion(q));

    const getQuestionDisplayValue = (q: Question) => {
        if (editedValues[q.id] !== undefined) return editedValues[q.id];
        if (q.inferredValue !== undefined && q.inferredValue !== null && String(q.inferredValue).trim() !== '') {
            return cleanNumericValue(q.inferredValue);
        }
        const inferredData = getInferredDataForQuestion(q, liveState?.extracted_fields);
        if (inferredData && inferredData.value !== undefined && inferredData.value !== null && String(inferredData.value).trim() !== '') {
            return cleanNumericValue(inferredData.value);
        }
        if (q.answer !== undefined && q.answer !== null && String(q.answer).trim() !== '') {
            return cleanNumericValue(q.answer);
        }
        return '';
    };

    const isQuestionConfirmed = (q: Question) => {
        if (q.isReconfirmed) return true;
        const inferredData = getInferredDataForQuestion(q, liveState?.extracted_fields);
        return Boolean(inferredData?.officer_confirmed);
    };

    const allReconfirmed = reconfirmQs.length === 0 || reconfirmQs.every(q => isQuestionConfirmed(q));

    const handleValueChange = (id: string, val: string) => {
        setEditedValues(prev => ({ ...prev, [id]: val }));
        setQuestions(prev => prev.map(q => q.id === id ? { ...q, answer: val, inferredValue: val } : q));
    };

    const toggleConfirm = async (q: Question) => {
        const currentlyConfirmed = isQuestionConfirmed(q);
        const nextState = !currentlyConfirmed;
        const currentVal = getQuestionDisplayValue(q);
        const inferredData = getInferredDataForQuestion(q, liveState?.extracted_fields);

        setQuestions(prev => prev.map(item => item.id === q.id ? { 
            ...item, 
            isReconfirmed: nextState,
            inferredValue: currentVal || item.inferredValue,
            answer: currentVal || item.answer 
        } : item));

        if (sessionId) {
            try {
                const fieldName = q.fieldName || inferredData?.field_name || (q.id ? q.id.replace(/^(t1_|t2_|t3_)/, '') : 'numeric_turnover');
                await pdSessionsApi.reconfirmField(sessionId, fieldName, currentVal || 'Confirmed by officer', nextState);
                
                // Update local liveState copy for instant reactive UI feedback
                setLiveState((prev: any) => {
                    if (!prev || !prev.extracted_fields) return prev;
                    return {
                        ...prev,
                        extracted_fields: {
                            ...prev.extracted_fields,
                            [fieldName]: {
                                ...(prev.extracted_fields[fieldName] || {}),
                                value: currentVal,
                                officer_confirmed: nextState
                            }
                        }
                    };
                });
            } catch (err) {
                console.warn('Could not persist reconfirmation to API:', err);
            }
        }
    };

    return (
        <div className="max-w-4xl mx-auto animate-fadeIn pb-24">
            <div className="flex items-center justify-between mb-2">
                <div>
                    <h2 className="text-2xl font-bold text-slate-800">Numeric Value Reconfirmation</h2>
                    <p className="text-slate-600">
                        Strictly verify all pure numerical values (inferred and stated) with the borrower before calculations.
                    </p>
                </div>
                <span className="text-xs bg-slate-100 text-slate-600 font-bold px-3 py-1.5 rounded-full border border-slate-300">
                    {reconfirmQs.filter(q => isQuestionConfirmed(q)).length} / {reconfirmQs.length} Confirmed
                </span>
            </div>

            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3 mb-6">
                <Icons.AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <div>
                    <h4 className="font-semibold text-amber-800 text-sm">Deterministic Underwriting Rule (D-02)</h4>
                    <p className="text-sm text-amber-700 mt-1">
                        Only numeric financial metrics feed into pure EMI, FOIR, and LTV calculation engines. Non-numeric questions are excluded here. Values inferred or stated by the AI are pre-filled below for officer verification.
                    </p>
                </div>
            </div>

            <div className="space-y-4">
                {reconfirmQs.map(q => {
                    const displayValue = getQuestionDisplayValue(q);
                    const isConfirmed = isQuestionConfirmed(q);
                    const inferredData = getInferredDataForQuestion(q, liveState?.extracted_fields);
                    const rawStatus = String(inferredData?.status || inferredData?.source || q.inferredStatus || '').toLowerCase();
                    const hasAiValue = Boolean(
                        (inferredData && inferredData.value !== undefined && inferredData.value !== null && String(inferredData.value).trim() !== '') ||
                        (q.inferredValue !== undefined && q.inferredValue !== null && String(q.inferredValue).trim() !== '') ||
                        q.inferredByAi
                    );
                    const isStated = Boolean(hasAiValue && rawStatus === 'stated');
                    const isInferred = Boolean(hasAiValue && !isStated);

                    return (
                        <div 
                            key={q.id} 
                            className={`p-5 rounded-xl border-2 transition-all ${
                                isConfirmed 
                                    ? 'bg-emerald-50/70 border-emerald-300 shadow-sm' 
                                    : 'bg-white border-slate-200 shadow-sm hover:border-slate-300'
                            }`}
                        >
                            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                                <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                                        <span className="text-xs font-bold text-slate-500 uppercase tracking-wide bg-slate-100 px-2 py-0.5 rounded">
                                            {q.tag || 'Financial Metric'}
                                        </span>
                                        {isInferred ? (
                                            <span className="flex items-center gap-1 text-xs font-semibold text-purple-700 bg-purple-100 px-2.5 py-0.5 rounded-full border border-purple-200">
                                                <Icons.Sparkles className="w-3.5 h-3.5 text-purple-600" />
                                                <span>AI Inferred</span>
                                            </span>
                                        ) : isStated ? (
                                            <span className="flex items-center gap-1 text-xs font-semibold text-blue-700 bg-blue-100 px-2.5 py-0.5 rounded-full border border-blue-200">
                                                <Icons.Sparkles className="w-3.5 h-3.5 text-blue-600" />
                                                <span>AI Inferred (Stated)</span>
                                            </span>
                                        ) : (
                                            <span className="text-xs font-semibold text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">
                                                Discussion Metric
                                            </span>
                                        )}
                                        {isConfirmed && (
                                            <span className="text-xs font-semibold text-emerald-700 bg-emerald-100 px-2.5 py-0.5 rounded-full border border-emerald-200 flex items-center gap-1">
                                                <Icons.Check className="w-3 h-3 text-emerald-600" />
                                                <span>Audited by Officer</span>
                                            </span>
                                        )}
                                    </div>
                                    <h3 className="text-base font-bold text-slate-800">{q.text}</h3>
                                    {(q.confidenceNote || inferredData?.reasoning || inferredData?.confidence_note) && (
                                        <p className="text-xs text-slate-500 mt-1 italic">
                                            Evidence / Reason: {q.confidenceNote || inferredData?.reasoning || inferredData?.confidence_note}
                                        </p>
                                    )}
                                </div>

                                <div className="flex items-center gap-3 shrink-0">
                                    <div className="flex flex-col items-end">
                                        <label className="text-[11px] font-semibold text-slate-500 mb-1">
                                            Verified Value {displayValue ? '(Pre-filled)' : ''}
                                        </label>
                                        <input
                                            type="text"
                                            value={displayValue}
                                            onChange={(e) => handleValueChange(q.id, e.target.value)}
                                            placeholder="Enter numeric value"
                                            className="w-40 text-right px-3 py-1.5 border border-slate-300 rounded-lg font-bold text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white"
                                        />
                                    </div>

                                    <button
                                        type="button"
                                        onClick={() => toggleConfirm(q)}
                                        className={`mt-4 px-4 py-2 rounded-xl text-sm font-bold flex items-center gap-1.5 transition-all border ${
                                            isConfirmed
                                                ? 'bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-600 shadow-sm'
                                                : 'bg-white hover:bg-slate-50 text-slate-700 border-slate-300 shadow-sm'
                                        }`}
                                    >
                                        {isConfirmed ? (
                                            <>
                                                <Icons.Check className="w-4 h-4" />
                                                <span>Confirmed</span>
                                            </>
                                        ) : (
                                            <span>Confirm</span>
                                        )}
                                    </button>
                                </div>
                            </div>
                        </div>
                    );
                })}

                {reconfirmQs.length === 0 && (
                    <div className="p-8 text-center bg-slate-50 rounded-xl border border-slate-200">
                        <Icons.CheckCircle className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                        <p className="text-sm font-semibold text-slate-700">All mandatory numeric fields have already been satisfied.</p>
                    </div>
                )}
            </div>

            <div className="flex justify-end mt-8 gap-4">
                <button onClick={() => navigate(`/officer/cases/${effectiveAppId}/gap-questions`)} className="text-slate-600 font-medium px-4">
                    Back
                </button>
                <button
                    onClick={() => navigate(`/officer/cases/${effectiveAppId}/photos`)}
                    disabled={!allReconfirmed}
                    className={`px-6 py-3 rounded-xl font-semibold shadow-sm transition-colors flex items-center gap-2 ${allReconfirmed ? 'bg-slate-900 text-white hover:bg-slate-800' : 'bg-slate-200 text-slate-400 cursor-not-allowed'}`}
                >
                    <span>Continue to Photos</span>
                    <Icons.ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
}
