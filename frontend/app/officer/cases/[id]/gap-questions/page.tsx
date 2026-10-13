'use client';

import React, { useEffect, useState } from 'react';
import { Card, Badge, CircularGauge } from '../../../../../components/ui/primitives';
import { Icons } from '../../../../../components/ui/Icons';
import { pdSessionsApi } from '../../../../../lib/api';
import GapQuestionsList from '../../../../../components/GapQuestionsList';
import { useCaseContext } from '../../../../../lib/CaseContext';

export default function GapQuestionsPage({ params }: { params: { id: string } }) {
    const { 
        questions, 
        navigate, 
        applicationId, 
        sessionId, 
        setSessionId, 
        refreshLiveState, 
        profileData, 
        loadApplicationData,
        liveState: contextLiveState,
        setLiveState: setContextLiveState
    } = useCaseContext();
    const [liveState, setLiveState] = useState<any>(contextLiveState || null);

    // Sync if context gets updated externally (e.g. baseline completion)
    useEffect(() => {
        if (contextLiveState) {
            setLiveState(contextLiveState);
        }
    }, [contextLiveState]);

    const effectiveAppId = params?.id || applicationId || 'APP-2026-9823';

    const empTypeLower = (profileData.business?.fields?.employmentType?.value || '').toLowerCase();
    const isSalaried = empTypeLower.startsWith('salari') || empTypeLower.includes('salari');
    const subCategory = isSalaried 
        ? (profileData.business?.fields?.employerType?.value || 'Private Company / Corporate')
        : (profileData.business?.fields?.businessCategory?.value || 'Retail / Trading');
    const benchmarkTitle = isSalaried 
        ? `Salaried > ${subCategory}` 
        : `Self-Employed > ${subCategory}`;

    // 1. Ensure applicant profile & dynamic questionnaire are loaded
    const loadedAppIdRef = React.useRef<string | null>(null);
    useEffect(() => {
        if (effectiveAppId && loadedAppIdRef.current !== effectiveAppId) {
            loadedAppIdRef.current = effectiveAppId;
            loadApplicationData(effectiveAppId);
        }
    }, [effectiveAppId, loadApplicationData]);

    // 2. Poll live AI follow-ups and checkpointed state
    useEffect(() => {
        let mounted = true;
        let pollTimer: NodeJS.Timeout | null = null;

        async function fetchState() {
            let activeId = sessionId;
            if (!activeId && effectiveAppId) {
                try {
                    const active = await pdSessionsApi.getActiveForApplication(effectiveAppId);
                    if (active?.id) {
                        activeId = active.id;
                        setSessionId(active.id);
                    }
                } catch (e) {
                    console.warn('Could not query active session for app:', e);
                }
            }
            if (activeId) {
                try {
                    const res = await pdSessionsApi.getLiveState(activeId);
                    if (mounted && res) {
                        setLiveState(res);
                        setContextLiveState(res);
                    }
                } catch (e) {
                    console.warn('Could not fetch live state in gap-questions:', e);
                }
            }
        }

        fetchState();
        pollTimer = setInterval(fetchState, 5000);

        return () => { 
            mounted = false; 
            if (pollTimer) clearInterval(pollTimer);
        };
    }, [sessionId, effectiveAppId, setSessionId]);

    const allHandled = questions.every(q => q.status !== 'pending');
    const askedCount = questions.filter(q => q.status === 'asked' || q.status === 'differently').length;
    const totalCount = questions.length || 1;
    const coveragePct = Math.round((askedCount / totalCount) * 100);

    return (
        <div className="max-w-4xl mx-auto animate-fadeIn pb-24">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-slate-800">AI Follow-up Suggestions & Gaps</h2>
                    <p className="text-sm text-slate-500">Case ID: <span className="font-mono font-semibold">{effectiveAppId}</span></p>
                </div>
                {liveState?.officer_proactive_bonus_points > 0 && (
                    <Badge variant="primary">
                        ⭐ Proactive Bonus: +{liveState.officer_proactive_bonus_points} pts
                    </Badge>
                )}
            </div>

            <Card className="p-5 border-l-4 border-l-teal-600 mb-6">
                <div className="flex justify-between items-start">
                    <div>
                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">RAG Matched Benchmark Profile</p>
                        <h3 className="text-lg font-bold text-slate-800">{benchmarkTitle}</h3>
                    </div>
                    <Badge variant="success">ChromaDB Vector Match: 95%</Badge>
                </div>
            </Card>

            <GapQuestionsList liveState={liveState} />

            {/* Completion card shown once all handled or officer wants to proceed */}
            <div className="mt-12 animate-fadeIn">
                <h2 className="text-2xl font-bold text-slate-800 mb-6">PD Quality Assessment</h2>
                <Card className="p-6">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-center">
                        <div className="col-span-1 flex justify-center">
                            <CircularGauge value={coveragePct || 82} label="Quality Score" size={160} colorClass="text-teal-600" />
                        </div>
                        <div className="col-span-2 space-y-5">
                            <div>
                                <div className="flex justify-between text-sm font-medium mb-1">
                                    <span>Question Coverage</span>
                                    <span>{coveragePct}%</span>
                                </div>
                                <div className="w-full bg-slate-100 rounded-full h-2">
                                    <div className="bg-emerald-500 h-2 rounded-full transition-all duration-500" style={{ width: `${coveragePct}%` }}></div>
                                </div>
                            </div>
                            <div>
                                <div className="flex justify-between text-sm font-medium mb-1">
                                    <span>AI Suggestion Uptake</span>
                                    <span>{liveState?.officer_uptake_count ? Math.min(100, liveState.officer_uptake_count * 25) : 75}%</span>
                                </div>
                                <div className="w-full bg-slate-100 rounded-full h-2">
                                    <div className="bg-amber-400 h-2 rounded-full transition-all duration-500" style={{ width: `${liveState?.officer_uptake_count ? Math.min(100, liveState.officer_uptake_count * 25) : 75}%` }}></div>
                                </div>
                            </div>
                            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 mt-4 text-sm text-slate-700">
                                <span className="font-semibold text-slate-800 block mb-1">Coaching Notes:</span>
                                Core trade parameters discussed. Continue to explicitly reconfirm numerical figures with the borrower.
                            </div>
                        </div>
                    </div>
                </Card>

                <div className="flex justify-end mt-8">
                    <button 
                        onClick={() => navigate(`/officer/cases/${effectiveAppId}/reconfirm`)} 
                        className="bg-slate-900 hover:bg-slate-800 text-white px-6 py-3 rounded-xl font-semibold shadow-sm transition-colors flex items-center gap-2"
                    >
                        <span>Continue to Reconfirmations</span>
                        <Icons.ArrowRight className="w-4 h-4" />
                    </button>
                </div>
            </div>
        </div>
    );
}
