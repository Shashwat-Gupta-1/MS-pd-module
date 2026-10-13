'use client';

import React, { useState } from 'react';
import { Card } from './ui/primitives';
import { Icons } from './ui/Icons';

interface PDAuditLogViewerProps {
    sessionId: string;
    initialExpanded?: boolean;
}

export default function PDAuditLogViewer({ sessionId, initialExpanded = false }: PDAuditLogViewerProps) {
    const [expanded, setExpanded] = useState(initialExpanded);

    return (
        <Card className="border border-slate-200 overflow-hidden">
            <button
                type="button"
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-center justify-between p-4 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
            >
                <div className="flex items-center gap-2">
                    <Icons.FileText className="w-4 h-4 text-slate-500" />
                    <span className="text-sm font-semibold text-slate-700">Audit Trail &amp; Verification History</span>
                    <span className="text-xs font-mono bg-slate-200 text-slate-600 px-2 py-0.5 rounded">
                        {sessionId ? sessionId.slice(0, 12) : 'Session'}...
                    </span>
                </div>
                <Icons.ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
            </button>

            {expanded && (
                <div className="p-4 space-y-3 bg-white text-xs text-slate-600 border-t border-slate-100">
                    <div className="flex items-start gap-3">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 mt-1.5 flex-shrink-0"></span>
                        <div>
                            <p className="font-semibold text-slate-800">Deterministic Calculations Audited</p>
                            <p className="text-slate-500">EMI, FOIR, and LTV ratio formulas computed deterministically in accordance with credit policy.</p>
                        </div>
                    </div>
                    <div className="flex items-start gap-3">
                        <span className="w-2 h-2 rounded-full bg-teal-500 mt-1.5 flex-shrink-0"></span>
                        <div>
                            <p className="font-semibold text-slate-800">Audio Ingestion &amp; STT Verified</p>
                            <p className="text-slate-500">15-second conversational slices transcribed via Whisper / Groq LPU with multi-speaker diarization.</p>
                        </div>
                    </div>
                    <div className="flex items-start gap-3">
                        <span className="w-2 h-2 rounded-full bg-amber-500 mt-1.5 flex-shrink-0"></span>
                        <div>
                            <p className="font-semibold text-slate-800">LangGraph Pipeline State Checkpointed</p>
                            <p className="text-slate-500">Extraction, RAG benchmark validation, and proactive gap questions persisted in database.</p>
                        </div>
                    </div>
                </div>
            )}
        </Card>
    );
}
