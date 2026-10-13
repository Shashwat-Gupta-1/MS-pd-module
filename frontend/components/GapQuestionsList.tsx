'use client';

import React, { useState } from 'react';
import { Card, Badge } from './ui/primitives';
import { Icons } from './ui/Icons';
import { useCaseContext } from '../lib/CaseContext';
import type { Question, QuestionStatus } from '../lib/types';

interface GapQuestionsListProps {
    liveState?: any;
}

export function getInferredDataForQuestion(q: any, extractedFields: Record<string, any> = {}): any | null {
    if (!extractedFields || typeof extractedFields !== 'object') return null;

    const candidateKeys = [
        q.fieldName,
        q.field_name,
        q.target_field,
        q.id,
        q.id ? String(q.id).replace(/^t[123]_/, '') : null,
        q.reason ? q.reason.replace(/verifies:\s*/i, '').trim().toLowerCase().replace(/\s+/g, '_') : null,
    ].filter(Boolean) as string[];

    // Add keyword based aliases
    const textLower = (q.text || '').toLowerCase();
    if (textLower.includes('monthly expense') || textLower.includes('kharcha') || textLower.includes('rashan') || textLower.includes('bijli')) {
        candidateKeys.push('monthly_household_expenses', 'monthly_expenses', 'monthly_business_expenses');
    }
    if (textLower.includes('bachhe') || textLower.includes('school') || textLower.includes('college') || textLower.includes('padhai')) {
        candidateKeys.push('dependents_education_cost', 'education_expenses', 'school_expenses', 'children_education');
    }
    if (textLower.includes('loan amount') || textLower.includes('kitna loan') || textLower.includes('amount chahiye') || textLower.includes('loan ka upyog')) {
        candidateKeys.push('requested_amount', 'loan_amount_requested', 'loan_amount');
    }
    if (textLower.includes('aur loan') || textLower.includes('koi aur loan') || textLower.includes('chal raha hai') || textLower.includes('emi kitni')) {
        candidateKeys.push('existing_obligations', 'existing_loan_emi', 'existing_emis', 'other_loan_emi');
    }
    if (textLower.includes('pehle koi loan') || textLower.includes('band ho chuka')) {
        candidateKeys.push('past_loan_history');
    }
    if (textLower.includes('emi bhar') || textLower.includes('emi comfort')) {
        candidateKeys.push('emi_comfort_range');
    }
    if (textLower.includes('turnover') || textLower.includes('sales')) {
        candidateKeys.push('monthly_turnover', 'annual_turnover');
    }
    if (textLower.includes('household income') || textLower.includes('family income') || textLower.includes('aamdani') || textLower.includes('bachat') || textLower.includes('saving')) {
        candidateKeys.push('monthly_savings', 'household_surplus', 'household_income');
    }
    if (textLower.includes('margin') || textLower.includes('munafa') || textLower.includes('profit')) {
        candidateKeys.push('net_margin_pct', 'net_profit_margin', 'gross_margin_pct');
    }
    if (textLower.includes('order') || textLower.includes('pending')) {
        candidateKeys.push('pending_orders_count', 'order_pipeline_and_advance_terms', 'typical_order_size');
    }
    if (textLower.includes('rented') || textLower.includes('ownership') || textLower.includes('kiraya') || textLower.includes('apna hai')) {
        candidateKeys.push('residence_ownership', 'premises_ownership', 'premises_ownership_status');
    }
    if (textLower.includes('pan') || textLower.includes('aadhaar')) candidateKeys.push('pan_number', 'pan');
    if (textLower.includes('full name') || textLower.includes('poora naam') || textLower.includes('naam')) candidateKeys.push('full_name', 'name');
    if (textLower.includes('occupation') || textLower.includes('business activity') || textLower.includes('mukhya kaam') || textLower.includes('vyavsay') || textLower.includes('trade')) {
        candidateKeys.push('exact_occupation_details', 'occupation_description', 'business_activity', 'business_category');
    }
    if (textLower.includes('machine') || textLower.includes('welding') || textLower.includes('cutting')) {
        candidateKeys.push('machinery_type_count', 'machinery_condition', 'machinery_inventory_and_condition');
    }
    if (textLower.includes('bonus') || textLower.includes('variable')) candidateKeys.push('variable_bonus_and_benefits', 'bonus_pay');
    if (textLower.includes('pf') || textLower.includes('esi')) candidateKeys.push('statutory_benefits', 'pf_esi');
    if (textLower.includes('offer letter') || textLower.includes('appointment')) candidateKeys.push('employment_documentation');
    if (textLower.includes('experience') || textLower.includes('years')) candidateKeys.push('total_work_experience');
    if (textLower.includes('delay') || textLower.includes('salary ever delayed')) candidateKeys.push('salary_delay_history');
    if (textLower.includes('salary slip') || textLower.includes('bank transfer') || textLower.includes('kaise milti')) candidateKeys.push('salary_payment_method', 'salary_payment_consistency');
    if (textLower.includes('service delivery') || textLower.includes('service model')) candidateKeys.push('service_model', 'service_delivery_model');
    if (textLower.includes('price range') || textLower.includes('minimum aur maximum') || textLower.includes('pricing')) candidateKeys.push('pricing', 'job_pricing_range');
    if (textLower.includes('season') || textLower.includes('festival') || textLower.includes('tyohaar')) candidateKeys.push('seasonal_demand', 'seasonal_demand_spikes');
    if (textLower.includes('supplier') || textLower.includes('credit terms')) candidateKeys.push('raw_material_supplier', 'supplier_payment_terms', 'supplier_sourcing_terms');
    if (textLower.includes('ledger') || textLower.includes('recovery')) candidateKeys.push('credit_ledger_recovery_cycle');

    // 1. Direct exact matches
    for (const key of candidateKeys) {
        if (!key) continue;
        const normalized = key.toLowerCase().replace(/[^a-z0-9]/g, '_');
        for (const [efKey, efVal] of Object.entries(extractedFields)) {
            const normEfKey = efKey.toLowerCase().replace(/[^a-z0-9]/g, '_');
            if (normEfKey === normalized) {
                if (efVal && efVal.value !== undefined && efVal.value !== null && efVal.value !== '') {
                    return efVal;
                }
            }
        }
    }

    // 2. Token overlap and substring matches
    for (const key of candidateKeys) {
        if (!key) continue;
        const normalized = key.toLowerCase().replace(/[^a-z0-9]/g, '_');
        const keyTokens = normalized.split('_').filter(t => t.length > 2);
        for (const [efKey, efVal] of Object.entries(extractedFields)) {
            const normEfKey = efKey.toLowerCase().replace(/[^a-z0-9]/g, '_');
            if (normEfKey.includes(normalized) || normalized.includes(normEfKey)) {
                if (efVal && efVal.value !== undefined && efVal.value !== null && efVal.value !== '') {
                    return efVal;
                }
            }
            // Check significant tokens (e.g. monthly + expenses matching monthly_household_expenses)
            if (keyTokens.length >= 2) {
                const matchCount = keyTokens.filter(t => normEfKey.includes(t)).length;
                if (matchCount >= 2 && efVal && efVal.value !== undefined && efVal.value !== null && efVal.value !== '') {
                    return efVal;
                }
            }
        }
    }
    return null;
}

export default function GapQuestionsList({ liveState }: GapQuestionsListProps) {
    const { questions } = useCaseContext();
    const [filterTab, setFilterTab] = useState<'all' | 'inferred' | 'gaps' | 'ai'>('all');

    const extractedFields = liveState?.extracted_fields || {};
    const aiFollowups = liveState?.active_followup_questions || [];

    const isAiQuestion = (q: any) =>
        Boolean(
            q.inferredByAi ||
            (q.tag && q.tag.toLowerCase().includes('ai')) ||
            (q.id && (q.id.startsWith('ai_') || q.id.startsWith('gq_') || q.id.startsWith('gap_')))
        );

    // Merge dynamic active AI follow-ups from liveState
    const existingTexts = new Set(questions.map(q => (q.text || '').trim().toLowerCase()));
    const additionalAiQuestions: Question[] = [];

    // 1. Add active follow-ups
    aiFollowups.forEach((afq: any, idx: number) => {
        const text = (afq.text || afq.question_text || '').trim();
        if (!text || existingTexts.has(text.toLowerCase())) return;

        const cat = (afq.category || 'AI Follow-up').replace(/_/g, ' ').toUpperCase();
        additionalAiQuestions.push({
            id: afq.id || `gq_live_${idx}`,
            tag: `AI Follow-up: ${cat}`,
            text: text,
            reason: afq.reason || `RAG trade benchmark probe: ${cat}`,
            status: 'pending',
            isNumeric: false,
            inferredByAi: true,
            fieldName: afq.target_field,
        });
        existingTexts.add(text.toLowerCase());
    });

    // 2. Add resolved follow-ups with their extracted answers
    const resolvedFollowups = liveState?.resolved_followup_questions || [];
    resolvedFollowups.forEach((rfq: any, idx: number) => {
        const text = (rfq.text || rfq.question_text || '').trim();
        if (!text || existingTexts.has(text.toLowerCase())) return;

        const cat = (rfq.category || 'AI Follow-up').replace(/_/g, ' ').toUpperCase();
        additionalAiQuestions.push({
            id: rfq.id || `gq_resolved_${idx}`,
            tag: `AI Follow-up: ${cat}`,
            text: text,
            reason: rfq.reason || `RAG trade benchmark probe: ${cat}`,
            status: 'asked',
            isNumeric: false,
            inferredByAi: true,
            inferredValue: rfq.answer,
            answer: rfq.answer,
            fieldName: rfq.target_field,
        });
        existingTexts.add(text.toLowerCase());
    });

    const combinedQuestions = [...additionalAiQuestions, ...questions];

    // Correlate with extracted fields
    const enrichedQuestions = combinedQuestions.map(q => {
        let inferredData = getInferredDataForQuestion(q, extractedFields);
        if (!inferredData && (q.inferredValue || q.answer)) {
            inferredData = {
                value: q.inferredValue || q.answer,
                status: 'STATED',
                reasoning: 'Extracted from transcript response',
            };
        }
        const isAi = isAiQuestion(q);
        const isInferred = Boolean(inferredData);
        return {
            ...q,
            inferredData,
            isInferred,
            isAi,
        };
    });

    const inferredQuestions = enrichedQuestions.filter(q => q.isInferred);
    const pendingGapQuestions = enrichedQuestions.filter(q => !q.isInferred && !q.isAi);
    const aiProbeQuestions = enrichedQuestions.filter(q => q.isAi && !q.isInferred);

    const displayedItems = filterTab === 'inferred'
        ? inferredQuestions
        : filterTab === 'gaps'
            ? pendingGapQuestions
            : filterTab === 'ai'
                ? aiProbeQuestions
                : enrichedQuestions;

    const renderCard = (q: any, index: number) => {
        const inferredData = q.inferredData;
        const isAi = q.isAi;
        const isInferred = Boolean(inferredData);

        return (
            <Card 
                key={q.id || index} 
                className={`overflow-visible transition-all ${
                    isInferred
                        ? 'border-2 border-emerald-400 bg-emerald-50/25 shadow-sm'
                        : isAi 
                            ? 'border-2 border-amber-300 bg-amber-50/20 shadow-sm' 
                            : 'border-slate-200 shadow-sm'
                }`}
            >
                <div className="p-5 space-y-3.5">
                    {/* Header: Question Type Badge & Extracted Status Badge */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2 flex-wrap">
                            <Badge variant={isAi ? "warning" : "primary"}>
                                {isAi ? '💡 AI Follow-up Question' : '📋 Predefined Questionnaire'}
                            </Badge>
                            
                            {isInferred ? (
                                <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center gap-1">
                                    <Icons.CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                                    Answer Extracted by AI
                                </span>
                            ) : (
                                <span className="text-xs font-medium px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                                    ⏳ Not Captured Yet
                                </span>
                            )}
                        </div>

                        <span className="text-xs font-mono font-bold text-slate-400">
                            #{index + 1}
                        </span>
                    </div>

                    {/* 1. The Question */}
                    <div>
                        <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-0.5">Question</p>
                        <h3 className="text-base font-bold text-slate-900 leading-snug">
                            {q.text}
                        </h3>
                    </div>

                    {/* 2. What Answer Was Extracted for that Question by AI */}
                    <div className="pt-1">
                        <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Answer Extracted by AI</p>
                        {isInferred && inferredData ? (
                            <div className="p-3.5 bg-white border-2 border-emerald-300 rounded-xl space-y-2 shadow-xs">
                                <div className="flex items-center justify-between flex-wrap gap-2 text-xs">
                                    <span className="font-bold text-emerald-800 uppercase flex items-center gap-1.5">
                                        <Icons.Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                                        Extracted Dialogue Answer
                                    </span>
                                    <span className="font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 capitalize">
                                        Status: {inferredData.status || 'Stated by Borrower'}
                                    </span>
                                </div>

                                <div className="text-base font-bold text-slate-900 font-mono">
                                    {typeof inferredData.value === 'number'
                                        ? '₹' + Number(inferredData.value).toLocaleString('en-IN')
                                        : String(inferredData.value)}
                                </div>

                                {inferredData.reasoning && (
                                    <p className="text-xs text-slate-600 italic bg-emerald-50/50 p-2 rounded border border-emerald-100">
                                        <span className="font-semibold text-emerald-800 not-italic">Dialogue Evidence:</span> {inferredData.reasoning}
                                    </p>
                                )}
                            </div>
                        ) : (
                            <div className="p-3 bg-slate-50 border border-dashed border-slate-300 rounded-xl text-xs text-slate-500 italic">
                                No answer extracted yet from the audio discussion.
                            </div>
                        )}
                    </div>
                </div>
            </Card>
        );
    };

    return (
        <div className="space-y-6">
            {/* Top Summary Banner */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 bg-slate-900 text-white rounded-2xl shadow-md">
                <div>
                    <h3 className="text-base font-bold flex items-center gap-2">
                        <Icons.ClipboardCheck className="w-5 h-5 text-teal-400" />
                        Verification Agenda &amp; AI Analysis Audit
                    </h3>
                    <p className="text-xs text-slate-300 mt-0.5">
                        Real-time correlation of policy questions against LangGraph extracted entities &amp; gaps
                    </p>
                </div>

                {/* Metric Counters */}
                <div className="flex items-center gap-2.5">
                    <div className="px-3 py-1.5 bg-emerald-950/80 border border-emerald-600/50 rounded-xl text-center">
                        <span className="block text-xs font-medium text-emerald-300">Answered &amp; Inferred</span>
                        <span className="text-lg font-bold text-emerald-400">{inferredQuestions.length}</span>
                    </div>
                    <div className="px-3 py-1.5 bg-amber-950/80 border border-amber-600/50 rounded-xl text-center">
                        <span className="block text-xs font-medium text-amber-300">Pending Gaps</span>
                        <span className="text-lg font-bold text-amber-400">{pendingGapQuestions.length}</span>
                    </div>
                    {aiProbeQuestions.length > 0 && (
                        <div className="px-3 py-1.5 bg-indigo-950/80 border border-indigo-600/50 rounded-xl text-center">
                            <span className="block text-xs font-medium text-indigo-300">AI Probes</span>
                            <span className="text-lg font-bold text-indigo-400">{aiProbeQuestions.length}</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Filter Tabs */}
            <div className="flex flex-wrap items-center gap-2 pb-2 border-b border-slate-200">
                <button
                    onClick={() => setFilterTab('all')}
                    className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                        filterTab === 'all'
                            ? 'bg-slate-900 text-white shadow-sm'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                >
                    All Items ({enrichedQuestions.length})
                </button>
                <button
                    onClick={() => setFilterTab('inferred')}
                    className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 ${
                        filterTab === 'inferred'
                            ? 'bg-emerald-600 text-white shadow-sm'
                            : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
                    }`}
                >
                    <Icons.CheckCircle className="w-3.5 h-3.5" />
                    Answered &amp; Inferred by AI ({inferredQuestions.length})
                </button>
                <button
                    onClick={() => setFilterTab('gaps')}
                    className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 ${
                        filterTab === 'gaps'
                            ? 'bg-amber-600 text-white shadow-sm'
                            : 'bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200'
                    }`}
                >
                    <Icons.AlertCircle className="w-3.5 h-3.5" />
                    Pending Gaps ({pendingGapQuestions.length})
                </button>
                {aiProbeQuestions.length > 0 && (
                    <button
                        onClick={() => setFilterTab('ai')}
                        className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 ${
                            filterTab === 'ai'
                                ? 'bg-indigo-600 text-white shadow-sm'
                                : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200'
                        }`}
                    >
                        <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span>
                        AI Dynamic Probes ({aiProbeQuestions.length})
                    </button>
                )}
            </div>

            {/* List of items */}
            <div className="space-y-4">
                {displayedItems.map((q, idx) => renderCard(q, idx))}
            </div>

            {displayedItems.length === 0 && (
                <div className="text-center py-12 bg-slate-50 border border-dashed border-slate-300 rounded-xl">
                    <Icons.CheckCircle className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                    <p className="text-base font-semibold text-slate-700">No questions in this filter</p>
                    <p className="text-xs text-slate-400 mt-1">Select "All Items" to view the complete verification agenda.</p>
                </div>
            )}
        </div>
    );
}
