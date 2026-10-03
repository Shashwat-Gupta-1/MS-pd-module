'use client';

import React, { useState } from 'react';
import { Icons } from '../../../../../components/ui/Icons';
import { Card, Badge } from '../../../../../components/ui/primitives';
import RecorderWidget, { RecState } from '../../../../../components/RecorderWidget';
import { useCaseContext } from '../../../../../lib/CaseContext';
import type { TranscriptSegmentData } from '../../../../../lib/types';

export default function QuestionnairePage() {
    const { navigate, pdSession, setPdSession, consentTimestamp } = useCaseContext();
    const [recState, setRecState] = useState<RecState>('idle');
    const [processingStep, setProcessingStep] = useState<number>(0);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [activeSpeakerFilter, setActiveSpeakerFilter] = useState<'all' | 'officer' | 'borrower'>('all');
    const [showRawDbTranscript, setShowRawDbTranscript] = useState(false);

    const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

    const handleAudioReady = async (audioFile: File | Blob, filename: string) => {
        setRecState('processing');
        setErrorMessage(null);
        setProcessingStep(1);

        const formData = new FormData();
        formData.append('file', audioFile, filename);
        formData.append('consent_captured', consentTimestamp ? 'true' : 'false');
        formData.append('session_id', 'APP-2026-9823');

        // Progress simulation ticks while network request is underway
        const timer1 = setTimeout(() => setProcessingStep(2), 1200);
        const timer2 = setTimeout(() => setProcessingStep(3), 3000);

        try {
            const response = await fetch(`${BACKEND_URL}/api/transcribe-audio`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Server error' }));
                throw new Error(errorData.detail || `Server returned ${response.status}`);
            }

            const data = await response.json();
            setProcessingStep(4);
            setPdSession(data);
            setRecState('idle');
        } catch (err: any) {
            console.error('Transcription error:', err);
            setErrorMessage(err.message || 'Failed to connect to backend server. Make sure FastAPI is running on port 8000.');
            setRecState('ready'); // allow retry
        } finally {
            clearTimeout(timer1);
            clearTimeout(timer2);
        }
    };

    const segments: TranscriptSegmentData[] = pdSession?.segments || [];
    const filteredSegments = segments.filter(seg => {
        if (activeSpeakerFilter === 'all') return true;
        return seg.speaker === activeSpeakerFilter;
    });

    const officerCount = segments.filter(s => s.speaker === 'officer').length;
    const borrowerCount = segments.filter(s => s.speaker === 'borrower').length;
    const avgConfidence = segments.length > 0
        ? (segments.reduce((acc, s) => acc + (s.confidence || 0), 0) / segments.length) * 100
        : 0;

    return (
        <div className="max-w-4xl mx-auto animate-fadeIn py-8 px-4">
            {/* Header */}
            <div className="text-center mb-8">
                <div className="inline-flex items-center gap-2 px-3 py-1 bg-teal-50 border border-teal-200 text-teal-700 rounded-full text-xs font-semibold mb-3">
                    <Icons.Mic className="w-3.5 h-3.5" /> Agent 1: Speech-to-Text & Diarization
                </div>
                <h1 className="text-2xl font-bold text-slate-900">Personal Discussion Audio Verification</h1>
                <p className="text-sm text-slate-500 mt-1 max-w-xl mx-auto">
                    Record the field interview or upload an audio file. The AI engine automatically transcribes, identifies speakers, and polishes the dialogue.
                </p>
            </div>

            {/* Error Notice */}
            {errorMessage && (
                <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm flex items-start gap-3">
                    <Icons.AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                        <p className="font-semibold">Processing Failed</p>
                        <p className="text-xs mt-1 text-red-600">{errorMessage}</p>
                    </div>
                </div>
            )}

            {/* Processing State */}
            {recState === 'processing' ? (
                <Card className="p-8 max-w-lg mx-auto text-center border-teal-100 bg-white shadow-xl">
                    <div className="relative w-20 h-20 mx-auto mb-6">
                        <div className="absolute inset-0 rounded-full border-4 border-teal-100"></div>
                        <div className="absolute inset-0 rounded-full border-4 border-teal-600 border-t-transparent animate-spin"></div>
                        <div className="absolute inset-0 flex items-center justify-center text-teal-600">
                            <Icons.Mic className="w-8 h-8" />
                        </div>
                    </div>

                    <h3 className="text-lg font-bold text-slate-900 mb-2">Processing Audio with Agent 1</h3>
                    <p className="text-xs text-slate-500 mb-6">Running faster-whisper ASR and Gemini dialogue turn parser...</p>

                    {/* Step-by-step progress checklist */}
                    <div className="space-y-3 text-left max-w-xs mx-auto">
                        <div className={`flex items-center gap-3 text-xs font-semibold ${processingStep >= 1 ? 'text-teal-700' : 'text-slate-400'}`}>
                            {processingStep > 1 ? (
                                <Icons.CheckCircle className="w-4 h-4 text-emerald-500" />
                            ) : (
                                <div className="w-4 h-4 rounded-full border-2 border-teal-600 border-t-transparent animate-spin" />
                            )}
                            1. Decoding to 16kHz mono WAV
                        </div>
                        <div className={`flex items-center gap-3 text-xs font-semibold ${processingStep >= 2 ? 'text-teal-700' : 'text-slate-400'}`}>
                            {processingStep > 2 ? (
                                <Icons.CheckCircle className="w-4 h-4 text-emerald-500" />
                            ) : processingStep === 2 ? (
                                <div className="w-4 h-4 rounded-full border-2 border-teal-600 border-t-transparent animate-spin" />
                            ) : (
                                <div className="w-4 h-4 rounded-full border-2 border-slate-200" />
                            )}
                            2. Running Faster-Whisper ASR & VAD
                        </div>
                        <div className={`flex items-center gap-3 text-xs font-semibold ${processingStep >= 3 ? 'text-teal-700' : 'text-slate-400'}`}>
                            {processingStep > 3 ? (
                                <Icons.CheckCircle className="w-4 h-4 text-emerald-500" />
                            ) : processingStep === 3 ? (
                                <div className="w-4 h-4 rounded-full border-2 border-teal-600 border-t-transparent animate-spin" />
                            ) : (
                                <div className="w-4 h-4 rounded-full border-2 border-slate-200" />
                            )}
                            3. Gemini Dialogue Parsing & Diarization
                        </div>
                        <div className={`flex items-center gap-3 text-xs font-semibold ${processingStep >= 4 ? 'text-teal-700' : 'text-slate-400'}`}>
                            {processingStep === 4 ? (
                                <Icons.CheckCircle className="w-4 h-4 text-emerald-500" />
                            ) : (
                                <div className="w-4 h-4 rounded-full border-2 border-slate-200" />
                            )}
                            4. Polishing Hindi & Confidence Scoring
                        </div>
                    </div>
                </Card>
            ) : pdSession && pdSession.segments && pdSession.segments.length > 0 ? (
                /* Results View */
                <div className="space-y-6">
                    {/* Session Overview Card */}
                    <Card className="p-6 bg-gradient-to-r from-slate-900 to-slate-800 text-white shadow-xl">
                        <div className="flex flex-wrap items-center justify-between gap-4">
                            <div>
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-xs font-semibold text-teal-400 uppercase tracking-wider">Interview Transcript Verified</span>
                                    <Badge variant="success">Transcribed</Badge>
                                </div>
                                <h3 className="text-xl font-bold">Case ID: {pdSession.session_id || 'APP-2026-9823'}</h3>
                            </div>
                            <div className="flex items-center gap-6">
                                <div className="text-center">
                                    <span className="text-xs text-slate-400 block">Duration</span>
                                    <span className="text-lg font-bold font-mono">{pdSession.duration_sec ? `${pdSession.duration_sec.toFixed(1)}s` : '—'}</span>
                                </div>
                                <div className="text-center">
                                    <span className="text-xs text-slate-400 block">Language</span>
                                    <span className="text-lg font-bold uppercase">{pdSession.language || 'hi'}</span>
                                </div>
                                <div className="text-center">
                                    <span className="text-xs text-slate-400 block">Avg Confidence</span>
                                    <span className="text-lg font-bold text-emerald-400 font-mono">{avgConfidence.toFixed(1)}%</span>
                                </div>
                            </div>
                        </div>
                    </Card>

                    {/* Filter & Controls Bar */}
                    <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
                        <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mr-1">Filter:</span>
                            <button
                                onClick={() => setActiveSpeakerFilter('all')}
                                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                                    activeSpeakerFilter === 'all'
                                        ? 'bg-slate-900 text-white shadow-sm'
                                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                }`}
                            >
                                All Turns ({segments.length})
                            </button>
                            <button
                                onClick={() => setActiveSpeakerFilter('officer')}
                                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                                    activeSpeakerFilter === 'officer'
                                        ? 'bg-indigo-600 text-white shadow-sm'
                                        : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
                                }`}
                            >
                                Officer ({officerCount})
                            </button>
                            <button
                                onClick={() => setActiveSpeakerFilter('borrower')}
                                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                                    activeSpeakerFilter === 'borrower'
                                        ? 'bg-emerald-600 text-white shadow-sm'
                                        : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                                }`}
                            >
                                Borrower ({borrowerCount})
                            </button>
                        </div>

                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => setShowRawDbTranscript(!showRawDbTranscript)}
                                className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                            >
                                {showRawDbTranscript ? 'Hide Raw DB View' : 'View Raw DB Transcript'}
                            </button>
                            <button
                                onClick={() => setPdSession(null)}
                                className="px-3 py-1.5 text-xs font-semibold text-slate-500 hover:text-red-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors flex items-center gap-1"
                            >
                                <Icons.RotateCcw className="w-3 h-3" /> Re-record
                            </button>
                        </div>
                    </div>

                    {/* Raw DB Transcript Accordion */}
                    {showRawDbTranscript && (
                        <Card className="p-4 bg-slate-900 text-slate-100 font-mono text-xs overflow-x-auto border-slate-800">
                            <p className="text-slate-400 font-bold mb-2 pb-1 border-b border-slate-700">
                                // Raw DB String (Stored in pd_sessions.transcript_raw)
                            </p>
                            <pre className="whitespace-pre-wrap leading-relaxed text-emerald-300">
                                {pdSession.transcript_raw || 'No raw transcript'}
                            </pre>
                        </Card>
                    )}

                    {/* Interactive Dialogue Turns List */}
                    <div className="space-y-3">
                        {filteredSegments.map((seg) => {
                            const isOfficer = seg.speaker === 'officer';
                            const confPct = (seg.confidence * 100).toFixed(1);

                            return (
                                <div
                                    key={seg.seq}
                                    className={`p-4 rounded-xl border transition-all flex flex-col md:flex-row md:items-start justify-between gap-3 shadow-sm ${
                                        isOfficer
                                            ? 'bg-indigo-50/40 border-indigo-200 hover:border-indigo-300'
                                            : 'bg-emerald-50/40 border-emerald-200 hover:border-emerald-300'
                                    }`}
                                >
                                    <div className="flex items-start gap-3 flex-1">
                                        <div
                                            className={`px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider flex-shrink-0 mt-0.5 ${
                                                isOfficer
                                                    ? 'bg-indigo-600 text-white'
                                                    : 'bg-emerald-600 text-white'
                                            }`}
                                        >
                                            {seg.speaker}
                                        </div>
                                        <div className="flex-1">
                                            <p className="text-sm font-medium text-slate-900 leading-relaxed">
                                                "{seg.text}"
                                            </p>
                                        </div>
                                    </div>

                                    {/* Metrics pill */}
                                    <div className="flex items-center gap-3 text-xs text-slate-500 flex-shrink-0 self-end md:self-center font-mono">
                                        <span className="bg-white/80 px-2 py-0.5 rounded border border-slate-200 text-slate-600">
                                            {seg.start_time.toFixed(1)}s → {seg.end_time.toFixed(1)}s
                                        </span>
                                        <span
                                            className={`px-2 py-0.5 rounded font-bold ${
                                                seg.low_confidence
                                                    ? 'bg-amber-100 text-amber-800'
                                                    : 'bg-emerald-100 text-emerald-800'
                                            }`}
                                        >
                                            {confPct}% {seg.low_confidence && '⚠ Low'}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    {/* Bottom Action CTA */}
                    <div className="flex justify-between items-center pt-6 border-t border-slate-200">
                        <button
                            onClick={() => setPdSession(null)}
                            className="text-sm font-semibold text-slate-500 hover:text-slate-800 px-4 py-2"
                        >
                            ← Re-record Audio
                        </button>
                        <button
                            onClick={() => navigate('/officer/cases/APP-2026-9823/gap-questions')}
                            className="px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-xl font-bold shadow-md hover:shadow-lg transition-all flex items-center gap-2"
                        >
                            Proceed to Gap Questions (Agent 2) →
                        </button>
                    </div>
                </div>
            ) : (
                /* Standard Recorder Card */
                <Card className="p-8 max-w-xl mx-auto border-slate-200 bg-white shadow-sm flex flex-col items-center">
                    <RecorderWidget
                        recState={recState}
                        setRecState={setRecState}
                        onAudioReady={handleAudioReady}
                    />

                    {recState === 'idle' && (
                        <button
                            onClick={() => navigate('/officer/cases/APP-2026-9823/gap-questions')}
                            className="mt-6 text-xs font-semibold text-slate-400 hover:text-slate-600 underline underline-offset-4"
                        >
                            Borrower declined recording — proceed in manual mode
                        </button>
                    )}
                </Card>
            )}
        </div>
    );
}
