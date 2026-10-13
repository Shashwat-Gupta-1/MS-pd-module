'use client';

import React from 'react';
import { Card } from './ui/primitives';
import { Icons } from './ui/Icons';
import { useCaseContext } from '../lib/CaseContext';

interface RecorderWidgetProps {
    onStop?: () => void;
    sessionId?: string | null;
    onQuestionsUpdate?: (questions: any[]) => void;
    onBatchSuccess?: (seq: number) => void;
}

export default function RecorderWidget({
    onStop,
}: RecorderWidgetProps = {}) {
    const {
        recState,
        questionnaireCompleted,
        recordingTime,
        completedChunks,
        isStreamingChunk,
        consentTimestamp,
        setConsentTimestamp,
        startRecording,
        pauseRecording,
        resumeRecording,
        stopRecording,
        completePredefinedQuestionnaire,
        applicationId,
        navigate,
    } = useCaseContext();

    const formatTime = (secs: number) => {
        const mins = Math.floor(secs / 60).toString().padStart(2, '0');
        const remSecs = (secs % 60).toString().padStart(2, '0');
        return `${mins}:${remSecs}`;
    };

    const handleMicButtonClick = async () => {
        if (recState === 'idle') {
            await startRecording();
        } else if (recState === 'recording') {
            pauseRecording();
        } else if (recState === 'paused') {
            resumeRecording();
        }
    };

    const handleStopClick = () => {
        stopRecording();
        if (onStop) {
            onStop();
        } else {
            navigate(`/officer/cases/${applicationId}/gap-questions`);
        }
    };

    return (
        <div className="flex flex-col items-center w-full max-w-xl mx-auto">
            {/* Consent Card */}
            <Card className="mb-6 p-4 w-full border-slate-200 shadow-sm bg-white">
                <label className="flex items-start gap-3 cursor-pointer">
                    <input
                        type="checkbox"
                        className="mt-1 w-5 h-5 rounded border-slate-300 text-teal-600 focus:ring-teal-500 cursor-pointer"
                        checked={!!consentTimestamp}
                        onChange={(e) => setConsentTimestamp(e.target.checked ? new Date() : null)}
                        disabled={recState !== 'idle'}
                    />
                    <div>
                        <span className="font-semibold text-slate-800 block">
                            Borrower has agreed to audio recording &amp; AI co-pilot assistance
                        </span>
                        {consentTimestamp ? (
                            <span className="text-xs text-emerald-600 font-medium">
                                ✓ Consent recorded at: {consentTimestamp.toLocaleTimeString()}
                            </span>
                        ) : (
                            <span className="text-xs text-slate-500">
                                Required before initiating audio capture
                            </span>
                        )}
                    </div>
                </label>
            </Card>

            {/* Central Microphone Button */}
            <div className="relative mb-6 flex flex-col items-center">
                <button
                    onClick={handleMicButtonClick}
                    disabled={!consentTimestamp}
                    className={`w-32 h-32 rounded-full flex flex-col items-center justify-center text-white shadow-xl transition-all transform hover:scale-105 active:scale-95 disabled:opacity-50 disabled:hover:scale-100 disabled:cursor-not-allowed cursor-pointer
                        ${recState === 'recording' ? 'bg-red-500 mic-recording ring-8 ring-red-500/20' : 
                          recState === 'paused' ? 'bg-amber-500 ring-8 ring-amber-500/20' : 
                          'bg-slate-900 hover:bg-slate-800 ring-8 ring-slate-900/10'}
                    `}
                    title={
                        recState === 'recording' ? 'Click to Pause Recording' :
                        recState === 'paused' ? 'Click to Resume Recording' :
                        'Click to Start Recording'
                    }
                >
                    {recState === 'idle' ? (
                        <Icons.Mic className="w-10 h-10 mb-1" />
                    ) : recState === 'paused' ? (
                        <Icons.Play className="w-10 h-10 mb-1" />
                    ) : (
                        <Icons.Pause className="w-10 h-10 mb-1" />
                    )}
                    <span className="font-mono text-xl font-bold tracking-wider">
                        {formatTime(recordingTime)}
                    </span>
                </button>

                {recState === 'recording' && (
                    <div className="absolute -bottom-8 left-1/2 transform -translate-x-1/2 flex items-end gap-1 h-6">
                        <div className="bar"></div>
                        <div className="bar"></div>
                        <div className="bar"></div>
                        <div className="bar"></div>
                        <div className="bar"></div>
                    </div>
                )}
            </div>

            {/* Predefined Questionnaire vs AI Follow-up Mode */}
            {recState !== 'idle' && (
                <div className="w-full mt-4 mb-6 animate-fadeIn">
                    {!questionnaireCompleted ? (
                        <div className="bg-gradient-to-br from-sky-50 to-indigo-50 border-2 border-sky-300 rounded-2xl p-5 shadow-sm text-center space-y-4">
                            <div className="flex items-center justify-center gap-2">
                                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-sky-600 text-white font-bold text-xs">
                                    📋
                                </span>
                                <h4 className="font-bold text-sky-950 text-base">
                                    Predefined Questionnaire Stage
                                </h4>
                            </div>

                            <p className="text-xs text-sky-800 max-w-md mx-auto leading-relaxed">
                                Interview the applicant using the predefined questions below. Audio is streaming in 15-second slices to LangGraph. Once finished with these baseline questions, click below to reveal AI follow-up questions right here.
                            </p>

                            {/* THE REQUESTED BUTTON: Completed Predefined Questionnaire */}
                            <div className="pt-1">
                                <button
                                    onClick={async () => {
                                        await completePredefinedQuestionnaire();
                                    }}
                                    className="w-full sm:w-auto px-6 py-3.5 bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-700 hover:to-emerald-700 text-white font-bold text-sm rounded-xl shadow-lg transition-all transform hover:scale-[1.02] active:scale-95 flex items-center justify-center gap-2.5 mx-auto"
                                >
                                    <Icons.CheckCircle className="w-5 h-5 text-teal-200" />
                                    <span>Completed Predefined Questionnaire</span>
                                </button>
                                <p className="text-[11px] text-slate-500 mt-2">
                                    Reveals dynamic AI follow-up questions while recording continues streaming uninterrupted.
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div className="bg-gradient-to-br from-emerald-50 to-teal-50 border-2 border-emerald-300 rounded-2xl p-5 shadow-sm space-y-3">
                            <div className="flex items-center justify-between flex-wrap gap-2">
                                <div className="flex items-center gap-2">
                                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-600 text-white font-bold text-xs">
                                        ✨
                                    </span>
                                    <h4 className="font-bold text-emerald-950 text-sm">
                                        AI Follow-up Questions Active
                                    </h4>
                                </div>
                                <span className="text-xs bg-emerald-100 text-emerald-800 font-bold px-2.5 py-0.5 rounded-full border border-emerald-300">
                                    {completedChunks} Slices Processed Live
                                </span>
                            </div>

                            <p className="text-xs text-emerald-800">
                                Predefined questions completed! Dynamic AI follow-up questions are revealed below and update live as the borrower speaks.
                            </p>

                            {isStreamingChunk && (
                                <div className="flex items-center gap-2 text-xs text-teal-700 font-semibold animate-pulse pt-1">
                                    <div className="w-2 h-2 rounded-full bg-teal-500"></div>
                                    Streaming slice to LangGraph...
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Direct Hardware Recording Controls */}
            {recState !== 'idle' && (
                <div className="flex flex-wrap items-center justify-center gap-3">
                    <button
                        onClick={stopRecording}
                        className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl font-semibold shadow-sm transition-colors text-xs cursor-pointer"
                        title="Immediately stop microphone hardware and end audio capture"
                    >
                        <Icons.MicOff className="w-4 h-4" /> Stop Recording / Turn Off Mic
                    </button>
                    <button
                        onClick={handleStopClick}
                        className="flex items-center gap-2 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-semibold shadow-sm transition-colors text-xs cursor-pointer"
                        title="Finalize discussion and review all AI follow-up gaps"
                    >
                        <Icons.Stop className="w-4 h-4" /> Finalize &amp; Review Gaps →
                    </button>
                </div>
            )}
        </div>
    );
}
