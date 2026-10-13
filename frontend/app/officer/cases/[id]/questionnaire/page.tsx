'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Icons } from '../../../../../components/ui/Icons';
import { Card, Badge } from '../../../../../components/ui/primitives';
import RecorderWidget from '../../../../../components/RecorderWidget';
import { useCaseContext, RecState } from '../../../../../lib/CaseContext';
import { pdSessionsApi, questionnaireApi, getStoredOfficer } from '../../../../../lib/api';
import { Question } from '../../../../../lib/types';
import { getInferredDataForQuestion } from '../../../../../components/GapQuestionsList';

function formatFieldName(fieldName?: string): string {
    if (!fieldName) return '';
    const specialMap: Record<string, string> = {
        emi_comfort_range: 'Comfortable Monthly EMI',
        pan_number: 'PAN Card Number',
        kyc_status: 'KYC Status',
        gps_lat: 'GPS Latitude',
        gps_lng: 'GPS Longitude',
        foir: 'FOIR Ratio',
        ltv: 'LTV Ratio',
    };
    if (specialMap[fieldName.toLowerCase()]) {
        return specialMap[fieldName.toLowerCase()];
    }
    return fieldName
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function QuestionnairePage({ params }: { params: { id: string } }) {
    const { 
        applicationId, 
        sessionId, 
        setSessionId, 
        officer, 
        questions, 
        setQuestions, 
        loadApplicationData, 
        refreshLiveState,
        recState,
        setRecState,
        questionnaireCompleted,
        completedChunks,
        navigate 
    } = useCaseContext();

    const [loadingInit, setLoadingInit] = useState(true);
    const [liveState, setLiveState] = useState<any>(null);
    const [activeTab, setActiveTab] = useState<'recorder' | 'agenda'>('recorder');

    const [slicesRecorded, setSlicesRecorded] = useState<number>(0);
    const [questionFilter, setQuestionFilter] = useState<'all' | 'ai' | 'inferred' | 'policy'>('all');
    const [copiedId, setCopiedId] = useState<string | null>(null);

    const effectiveAppId = params?.id || applicationId || 'APP-2026-9823';

    const handleCopyPrompt = (id: string, text: string) => {
        if (typeof navigator !== 'undefined' && navigator.clipboard) {
            navigator.clipboard.writeText(text);
            setCopiedId(id);
            setTimeout(() => setCopiedId(null), 2000);
        }
    };

    // 2. Load real application questions on mount dynamically
    const loadedAppIdRef = React.useRef<string | null>(null);
    useEffect(() => {
        let mounted = true;
        async function init() {
            if (!effectiveAppId) {
                setLoadingInit(false);
                return;
            }
            if (loadedAppIdRef.current === effectiveAppId) {
                setLoadingInit(false);
                return;
            }
            loadedAppIdRef.current = effectiveAppId;
            setLoadingInit(true);
            try {
                // Trigger context loader
                await loadApplicationData(effectiveAppId);

                // Direct API fetch to guarantee 100% dynamic loading
                let qData = await questionnaireApi.getForCase(effectiveAppId);
                if (!qData || (!qData.tier1_universal?.length && !qData.tier2_branch?.length && !qData.tier3_trade_specific?.length)) {
                    qData = await questionnaireApi.getAllTiers();
                }

                if (mounted && qData) {
                    const mapped: Question[] = [];
                    (qData.tier1_universal || []).forEach((q: any) => {
                        mapped.push({
                            id: `t1_${q.id}`,
                            tag: 'Universal KYC',
                            text: q.question_text,
                            reason: q.field_name ? `Verifies: ${formatFieldName(q.field_name)}` : 'Mandatory baseline question',
                            status: 'pending',
                            isNumeric: q.data_type === 'number',
                            fieldName: q.field_name,
                        });
                    });
                    (qData.tier2_branch || []).forEach((q: any) => {
                        mapped.push({
                            id: `t2_${q.id}`,
                            tag: q.employment_type === 'salaried' ? 'Salaried' : 'Self-Employed',
                            text: q.question_text,
                            reason: q.field_name ? `Verifies: ${formatFieldName(q.field_name)}` : 'Employment/Business verification',
                            status: 'pending',
                            isNumeric: q.data_type === 'number',
                            fieldName: q.field_name,
                        });
                    });
                    (qData.tier3_trade_specific || []).forEach((q: any) => {
                        mapped.push({
                            id: `t3_${q.id}`,
                            tag: 'Trade Benchmark',
                            text: q.question_text,
                            reason: q.field_name ? `Verifies: ${formatFieldName(q.field_name)}` : 'Industry-specific operational check',
                            status: 'pending',
                            isNumeric: q.data_type === 'number',
                            fieldName: q.field_name,
                        });
                    });

                    if (mapped.length > 0) {
                        setQuestions(mapped);
                    }
                }
            } catch (err) {
                console.warn('Could not load case questionnaire data:', err);
            } finally {
                setLoadingInit(false);
            }
        }
        init();
        return () => { mounted = false; };
    }, [effectiveAppId, loadApplicationData]);

    // 3. Ensure a valid active session exists for this application and immediately hydrate liveState
    useEffect(() => {
        let mounted = true;
        async function ensureSession() {
            if (!effectiveAppId) return;

            let activeId = sessionId;
            try {
                // Check if active session already exists in DB
                const active = await pdSessionsApi.getActiveForApplication(effectiveAppId);
                if (active?.id) {
                    activeId = active.id;
                    if (mounted) setSessionId(active.id);
                }
            } catch (err) {
                console.warn('Could not query active session for application:', err);
            }

            if (!activeId) {
                try {
                    const storedOff = getStoredOfficer();
                    const offId = officer?.id || storedOff?.id || storedOff?.officer_id || undefined;
                    const session = await pdSessionsApi.start(effectiveAppId, offId, true);
                    if (mounted && session?.id) {
                        activeId = session.id;
                        setSessionId(session.id);
                    }
                } catch (err) {
                    console.error('Failed to start PD session in API:', err);
                }
            }

            // Immediately load liveState for active session to show all AI follow-up questions!
            if (activeId) {
                try {
                    const st = await pdSessionsApi.getLiveState(activeId);
                    if (mounted && st) {
                        setLiveState(st);
                    }
                } catch (err) {
                    console.warn('Could not fetch initial live state:', err);
                }
            }
        }

        ensureSession();
        return () => { mounted = false; };
    }, [effectiveAppId, officer, sessionId, setSessionId]);


    // 3. Poll live state when recording is active (or periodically for updates)
    useEffect(() => {
        if (!sessionId) return;

        const interval = setInterval(async () => {
            try {
                const updated = await pdSessionsApi.getLiveState(sessionId);
                if (updated) setLiveState(updated);
            } catch (err) {
                // Ignore transient network errors
            }
        }, recState === 'recording' ? 4000 : 8000);

        return () => clearInterval(interval);
    }, [recState, sessionId]);

    const handleStop = () => {
        setRecState('processing');
        setTimeout(() => {
            navigate(`/officer/cases/${effectiveAppId}/gap-questions`);
        }, 3000);
    };

    // Memoized batch handlers to prevent re-renders in child widget
    const handleQuestionsUpdate = useCallback((qs: any[]) => {
        if (Array.isArray(qs)) {
            setLiveState((prev: any) => ({
                ...(prev || {}),
                active_followup_questions: qs
            }));
        }
    }, []);

    const handleBatchSuccess = useCallback((seq: number) => {
        setSlicesRecorded(prev => prev + 1);
    }, []);

    const aiFollowupQuestions = liveState?.active_followup_questions || [];
    const mappedAiQuestions: (Question & { inferredData?: any; isInferred?: boolean })[] = aiFollowupQuestions.map((aiQ: any, idx: number) => {
        const cat = (aiQ.category || 'AI Prompt').replace(/_/g, ' ').toUpperCase();
        const baseQ = {
            id: aiQ.id || `ai_gq_${idx}`,
            tag: `AI Follow-up: ${cat}`,
            text: aiQ.text || aiQ.question_text || '',
            reason: aiQ.reason || `RAG trade benchmark gap: ${cat}`,
            status: 'pending' as const,
            isNumeric: false,
            inferredByAi: true,
        };
        const inferredData = getInferredDataForQuestion(baseQ, liveState?.extracted_fields);
        return {
            ...baseQ,
            inferredData,
            isInferred: Boolean(inferredData)
        };
    });

    const enrichedPolicyQuestions: (Question & { inferredData?: any; isInferred?: boolean })[] = questions.map(pq => {
        const inferredData = getInferredDataForQuestion(pq, liveState?.extracted_fields);
        return {
            ...pq,
            inferredData,
            isInferred: Boolean(inferredData)
        };
    });

    const allCombinedQuestions = [
        ...mappedAiQuestions,
        ...enrichedPolicyQuestions.filter(pq => !mappedAiQuestions.some(ai => (ai.text || '').trim().toLowerCase() === (pq.text || '').trim().toLowerCase()))
    ];

    const inferredQuestionsList = allCombinedQuestions.filter(q => q.isInferred);

    const displayedQuestions = questionFilter === 'ai'
        ? mappedAiQuestions
        : questionFilter === 'inferred'
            ? inferredQuestionsList
            : questionFilter === 'policy'
                ? enrichedPolicyQuestions
                : allCombinedQuestions;

    return (
        <div className="max-w-4xl mx-auto animate-fadeIn py-8 px-4">
            {/* Header info */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8 pb-4 border-b border-slate-200">
                <div>
                    <span className="text-xs font-semibold text-teal-600 uppercase tracking-wider">Ground PD Session</span>
                    <h2 className="text-2xl font-bold text-slate-900 mt-0.5">Physical Discussion &amp; Recording</h2>
                    <p className="text-sm text-slate-500">Case ID: <span className="font-mono font-bold text-slate-700">{effectiveAppId}</span></p>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setActiveTab('recorder')}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === 'recorder' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                    >
                        Active Interview
                    </button>
                    <button
                        onClick={() => setActiveTab('agenda')}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === 'agenda' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                    >
                        Full Agenda ({questions.length})
                    </button>
                </div>
            </div>

            {loadingInit && questions.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20">
                    <div className="w-10 h-10 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mb-4"></div>
                    <p className="text-sm text-slate-500">Loading dynamic questionnaire from backend...</p>
                </div>
            ) : recState === 'processing' ? (
                <div className="flex flex-col items-center justify-center py-16">
                    <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-teal-600 mb-8"></div>
                    <h3 className="text-xl font-bold text-slate-800 mb-6">Processing LangGraph Analysis...</h3>
                    <div className="space-y-3 w-72">
                        <div className="flex items-center gap-3 text-slate-600"><Icons.CheckCircle className="w-5 h-5 text-emerald-500" /> Audio recorded &amp; indexed</div>
                        <div className="flex items-center gap-3 text-slate-600"><Icons.CheckCircle className="w-5 h-5 text-emerald-500" /> Extracting financial parameters</div>
                        <div className="flex items-center gap-3 text-slate-400 animate-pulse"><div className="w-5 h-5 rounded-full border-2 border-slate-300 border-t-teal-600 animate-spin"></div> Comparing against ChromaDB benchmarks</div>
                    </div>
                </div>
            ) : activeTab === 'recorder' ? (
                <div className="flex flex-col items-center justify-center py-2 space-y-6">
                    {/* Top Recorder Widget */}
                    <RecorderWidget 
                        onStop={handleStop}
                        sessionId={sessionId}
                        onQuestionsUpdate={handleQuestionsUpdate}
                        onBatchSuccess={handleBatchSuccess}
                    />

                    {/* LIVE INTERVIEW SECTION - APPARENT WHEN RECORDING STARTS OR IDLE */}
                    <div className="w-full space-y-6">
                        {/* Live AI Status Bar */}
                        {recState === 'recording' && (
                            <div className="bg-slate-900 text-white rounded-xl p-4 shadow-md flex flex-wrap items-center justify-between gap-3 animate-fadeIn">
                                <div className="flex items-center gap-3">
                                    <span className="w-3 h-3 bg-red-500 rounded-full animate-ping"></span>
                                    <div>
                                        <p className="text-sm font-bold flex items-center gap-2">
                                            {!questionnaireCompleted ? (
                                                <>
                                                    Predefined Questionnaire Stage
                                                    <span className="text-xs bg-sky-900/80 text-sky-300 border border-sky-600/50 px-2 py-0.5 rounded font-mono">Continuous 15s Slices</span>
                                                </>
                                            ) : (
                                                <>
                                                    AI Co-Pilot Follow-up Active
                                                    <span className="text-xs bg-emerald-900/80 text-emerald-300 border border-emerald-600/50 px-2 py-0.5 rounded font-mono">15s Slices</span>
                                                </>
                                            )}
                                        </p>
                                        <p className="text-xs text-slate-300">
                                            {!questionnaireCompleted
                                                ? `Streaming audio in 15-second slices to LangGraph (${completedChunks} slices processed). Predefined questions active.`
                                                : `Dynamic AI follow-ups active (${completedChunks} slices processed). AI suggestions populate live.`
                                            }
                                        </p>
                                    </div>
                                </div>
                                {sessionId && (
                                    <span className="text-xs font-mono bg-slate-800 text-slate-400 px-2.5 py-1 rounded">
                                        ID: {sessionId.slice(0, 8)}...
                                    </span>
                                )}
                            </div>
                        )}

                        {/* 1. DEDICATED TOP AI CO-PILOT FOLLOW-UP QUESTIONS SECTION - REVEALED ONCE QUESTIONNAIRE IS COMPLETED */}
                        {questionnaireCompleted && (
                            <div className="w-full bg-gradient-to-r from-amber-500/10 via-amber-500/5 to-teal-500/10 border-2 border-amber-300 rounded-2xl p-5 shadow-sm space-y-4 animate-fadeIn">
                                <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-amber-200">
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-amber-500 animate-pulse"></span>
                                        <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                                            💡 Live AI Co-Pilot Follow-up Questions
                                            <span className="text-xs font-mono font-bold bg-amber-200 text-amber-900 px-2.5 py-0.5 rounded-full">
                                                {mappedAiQuestions.length} Active
                                            </span>
                                        </h3>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs font-medium text-amber-800 bg-amber-100 border border-amber-300 px-2.5 py-1 rounded-lg">
                                            Generated dynamically from borrower audio
                                        </span>
                                        <button
                                            onClick={() => navigate(`/officer/cases/${effectiveAppId}/gap-questions`)}
                                            className="text-xs font-semibold px-2.5 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-lg flex items-center gap-1 transition-colors"
                                        >
                                            <span>Full Gap Analysis</span>
                                            <Icons.ArrowRight className="w-3 h-3" />
                                        </button>
                                    </div>
                                </div>

                                {mappedAiQuestions.length > 0 ? (
                                    <div className="grid grid-cols-1 gap-3">
                                        {aiFollowupQuestions.map((q: any, idx: number) => {
                                            const qText = q.text || q.question_text || '';
                                            const qId = q.id || `ai_card_${idx}`;
                                            const cat = (q.category || 'AI Follow-up').replace(/_/g, ' ').toUpperCase();
                                            return (
                                                <div 
                                                    key={qId} 
                                                    className="bg-white border-2 border-amber-300 hover:border-amber-400 p-4 rounded-xl shadow-sm transition-all space-y-2.5"
                                                >
                                                    <div className="flex items-center justify-between flex-wrap gap-2">
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-xs font-mono font-bold bg-amber-500 text-white px-2 py-0.5 rounded">
                                                                AI #{idx + 1}
                                                            </span>
                                                            <Badge variant="warning">{cat}</Badge>
                                                            {q.priority && (
                                                                <span className="text-xs font-semibold uppercase text-red-600 bg-red-50 border border-red-200 px-2 py-0.5 rounded">
                                                                    {q.priority}
                                                                </span>
                                                            )}
                                                        </div>
                                                        <button
                                                            onClick={() => handleCopyPrompt(qId, qText)}
                                                            className="text-xs font-semibold px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg flex items-center gap-1.5 transition-colors"
                                                        >
                                                            <Icons.Copy className="w-3.5 h-3.5" />
                                                            {copiedId === qId ? 'Copied!' : 'Copy Prompt'}
                                                        </button>
                                                    </div>

                                                    <p className="text-base font-semibold text-slate-900 leading-snug">
                                                        "{qText}"
                                                    </p>

                                                    {q.reason && (
                                                        <p className="text-xs text-slate-600 bg-amber-50/80 p-2 rounded-lg border border-amber-200">
                                                            <span className="font-bold text-amber-900 mr-1">Why ask:</span> {q.reason}
                                                        </p>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                ) : (
                                    <div className="p-4 bg-white/70 border border-dashed border-amber-300 rounded-xl text-center space-y-1">
                                        <p className="text-sm font-semibold text-slate-800">
                                            🎙️ AI Co-Pilot Listening for Missing Information
                                        </p>
                                        <p className="text-xs text-slate-500 max-w-lg mx-auto">
                                            As the applicant speaks, LangGraph evaluates remaining gaps against credit policy benchmarks. Any missing parameters will populate target follow-up questions right here.
                                        </p>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* 2. QUESTIONNAIRE SECTION - ALL QUESTIONS TOGETHER WITH FILTER PILLS */}
                        <div className="w-full space-y-4">
                            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                                <div>
                                    <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                                        <Icons.FileText className="w-4 h-4 text-teal-600" />
                                        Applicant Questionnaire &amp; Agenda
                                        <span className="text-xs bg-teal-50 text-teal-700 border border-teal-200 px-2.5 py-0.5 rounded-full font-semibold">
                                            {displayedQuestions.length} Questions
                                        </span>
                                    </h3>
                                    <p className="text-xs text-slate-500 mt-0.5">
                                        Combined credit policy checklist &amp; AI-suggested follow-up questions for case {effectiveAppId}
                                    </p>
                                </div>

                                {/* Filter Pills */}
                                <div className="flex flex-wrap items-center gap-1.5 bg-slate-100 p-1 rounded-lg text-xs font-semibold">
                                    <button
                                        onClick={() => setQuestionFilter('all')}
                                        className={`px-3 py-1.5 rounded-md transition-colors ${questionFilter === 'all' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
                                    >
                                        All ({allCombinedQuestions.length})
                                    </button>
                                    <button
                                        onClick={() => setQuestionFilter('ai')}
                                        className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-1.5 ${questionFilter === 'ai' ? 'bg-amber-500 text-white shadow-sm' : 'text-amber-700 hover:text-amber-900'}`}
                                    >
                                        <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                                        AI Follow-ups ({mappedAiQuestions.length})
                                    </button>
                                    <button
                                        onClick={() => setQuestionFilter('inferred')}
                                        className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-1.5 ${questionFilter === 'inferred' ? 'bg-emerald-600 text-white shadow-sm' : 'text-emerald-700 hover:text-emerald-900'}`}
                                    >
                                        <Icons.CheckCircle className="w-3 h-3" />
                                        Inferred ({inferredQuestionsList.length})
                                    </button>
                                    <button
                                        onClick={() => setQuestionFilter('policy')}
                                        className={`px-3 py-1.5 rounded-md transition-colors ${questionFilter === 'policy' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
                                    >
                                        Policy ({questions.length})
                                    </button>
                                </div>
                            </div>

                            {/* Dynamic Questions List */}
                            <div className="grid grid-cols-1 gap-2.5 max-h-[520px] overflow-y-auto pr-1">
                                {displayedQuestions.map((q, idx) => {
                                    const isAi = Boolean(q.inferredByAi || (q.tag && q.tag.toLowerCase().includes('ai')));
                                    const isInferred = Boolean(q.isInferred);
                                    const infData = q.inferredData;

                                    return (
                                        <Card 
                                            key={q.id || idx} 
                                            className={`p-3.5 flex flex-col gap-2 transition-all ${
                                                isInferred
                                                    ? 'border-2 border-emerald-400 bg-emerald-50/25 shadow-sm'
                                                    : isAi 
                                                        ? 'border-amber-300 bg-amber-50/20 hover:border-amber-400 shadow-sm ring-1 ring-amber-200' 
                                                        : 'border-slate-200 hover:border-teal-300'
                                            }`}
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="space-y-1 w-full">
                                                    <div className="flex items-center gap-2 flex-wrap">
                                                        <span className="text-xs font-mono font-bold text-slate-400">
                                                            #{idx + 1}
                                                        </span>
                                                        <Badge variant={isInferred ? "success" : isAi ? "warning" : "primary"}>
                                                            {isAi ? `⚡ ${q.tag}` : q.tag}
                                                        </Badge>
                                                        {isInferred && (
                                                            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center gap-1">
                                                                <Icons.CheckCircle className="w-3 h-3 text-emerald-600" />
                                                                Answered &amp; Inferred by AI
                                                            </span>
                                                        )}
                                                        {q.isNumeric && <Badge variant="warning">Numeric</Badge>}
                                                    </div>
                                                    <p className="text-sm font-medium text-slate-800 leading-snug">
                                                        {q.text}
                                                    </p>
                                                    {q.reason && (
                                                        <p className="text-xs text-slate-400">
                                                            {q.reason}
                                                        </p>
                                                    )}

                                                    {/* Inferred Extracted Value Pill */}
                                                    {isInferred && infData && (
                                                        <div className="mt-1.5 p-2 bg-white border border-emerald-200 rounded-lg flex items-center justify-between flex-wrap gap-2 text-xs">
                                                            <div className="flex items-center gap-1.5">
                                                                <span className="font-bold text-emerald-800">Inferred Value:</span>
                                                                <span className="font-mono font-bold text-slate-900 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                                                                    {typeof infData.value === 'number'
                                                                        ? '₹' + Number(infData.value).toLocaleString('en-IN')
                                                                        : String(infData.value)}
                                                                </span>
                                                            </div>
                                                            <span className="text-[11px] text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded capitalize">
                                                                Evidence: {infData.status || 'Stated by Borrower'}
                                                            </span>
                                                        </div>
                                                    )}
                                                </div>

                                                {isAi && (
                                                    <button
                                                        onClick={() => handleCopyPrompt(q.id, q.text)}
                                                        className="shrink-0 text-xs px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded font-medium flex items-center gap-1 transition-colors"
                                                        title="Copy prompt for interview reference"
                                                    >
                                                        <Icons.Copy className="w-3 h-3" />
                                                        {copiedId === q.id ? 'Copied' : 'Copy'}
                                                    </button>
                                                )}
                                            </div>
                                        </Card>
                                    );
                                })}
                            </div>
                        </div>

                        {recState === 'idle' && (
                            <div className="text-center pt-2">
                                <button 
                                    onClick={() => navigate(`/officer/cases/${effectiveAppId}/gap-questions`)} 
                                    className="text-sm font-medium text-slate-500 hover:text-slate-700 underline underline-offset-4"
                                >
                                    Skip recording — proceed to manual review
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            ) : (
                /* Full Conversational Agenda Tab */
                <div className="space-y-4">
                    <p className="text-sm text-slate-600 mb-2">
                        Complete compiled credit policy agenda &amp; AI probes ({allCombinedQuestions.length} items):
                    </p>
                    <div className="grid grid-cols-1 gap-3">
                        {allCombinedQuestions.map((q, idx) => {
                            const isAi = Boolean(q.inferredByAi || (q.tag && q.tag.toLowerCase().includes('ai')));
                            const isInferred = Boolean(q.isInferred);
                            const infData = q.inferredData;

                            return (
                                <Card 
                                    key={q.id || idx} 
                                    className={`p-4 flex flex-col gap-2 ${
                                        isInferred 
                                            ? 'border-2 border-emerald-400 bg-emerald-50/25 shadow-sm'
                                            : isAi 
                                                ? 'border-amber-300 bg-amber-50/20 shadow-sm' 
                                                : 'border-slate-200'
                                    }`}
                                >
                                    <div className="flex items-start justify-between gap-4">
                                        <div className="space-y-1">
                                            <div className="flex items-center gap-2 flex-wrap">
                                                <Badge variant={isInferred ? "success" : isAi ? "warning" : "primary"}>
                                                    {isAi ? `⚡ ${q.tag}` : q.tag}
                                                </Badge>
                                                {isInferred && (
                                                    <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center gap-1">
                                                        <Icons.CheckCircle className="w-3 h-3 text-emerald-600" />
                                                        Answered &amp; Inferred by AI
                                                    </span>
                                                )}
                                                {q.isNumeric && <Badge variant="warning">Numeric</Badge>}
                                            </div>
                                            <p className="text-sm font-semibold text-slate-800">{q.text}</p>
                                            <p className="text-xs text-slate-400">Context: {q.reason}</p>

                                            {isInferred && infData && (
                                                <div className="mt-1 flex items-center gap-2 text-xs">
                                                    <span className="font-bold text-emerald-800">Inferred Answer:</span>
                                                    <span className="font-mono font-bold text-slate-900 bg-white px-2 py-0.5 rounded border border-emerald-200">
                                                        {typeof infData.value === 'number'
                                                            ? '₹' + Number(infData.value).toLocaleString('en-IN')
                                                            : String(infData.value)}
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                        <span className="text-xs font-mono text-slate-300">#{idx + 1}</span>
                                    </div>
                                </Card>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
