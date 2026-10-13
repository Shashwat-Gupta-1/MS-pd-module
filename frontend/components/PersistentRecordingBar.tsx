'use client';

import React from 'react';
import { Icons } from './ui/Icons';
import { useCaseContext } from '../lib/CaseContext';

export default function PersistentRecordingBar() {
    const {
        recState,
        questionnaireCompleted,
        recordingTime,
        completedChunks,
        isStreamingChunk,
        pauseRecording,
        resumeRecording,
        stopRecording,
        completePredefinedQuestionnaire,
        applicationId,
        currentRoute,
        navigate,
    } = useCaseContext();

    if (recState === 'idle') {
        return null;
    }

    const formatTime = (secs: number) => {
        const mins = Math.floor(secs / 60).toString().padStart(2, '0');
        const remSecs = (secs % 60).toString().padStart(2, '0');
        return `${mins}:${remSecs}`;
    };

    const isGapPage = currentRoute.includes('/gap-questions');

    return (
        <div className="sticky top-0 z-50 mb-6 bg-slate-900/95 backdrop-blur-md text-white border-b-2 border-teal-500 shadow-xl rounded-xl p-3 md:px-5 md:py-3.5 transition-all animate-fadeIn">
            <div className="flex flex-wrap items-center justify-between gap-3">
                {/* Left: Recording Status & Timer */}
                <div className="flex items-center gap-3">
                    <div className="relative flex items-center justify-center">
                        {recState === 'recording' ? (
                            <span className="flex h-3.5 w-3.5">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-red-500"></span>
                            </span>
                        ) : recState === 'paused' ? (
                            <span className="inline-flex rounded-full h-3.5 w-3.5 bg-amber-400"></span>
                        ) : (
                            <span className="inline-flex rounded-full h-3.5 w-3.5 bg-teal-400 animate-pulse"></span>
                        )}
                    </div>

                    <div>
                        <div className="flex items-center gap-2">
                            <span className="font-mono text-base font-bold tracking-wider">
                                {formatTime(recordingTime)}
                            </span>
                            <span className={`text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                                recState === 'recording' ? 'bg-red-500/20 text-red-300 border border-red-500/40' :
                                recState === 'paused' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' :
                                'bg-teal-500/20 text-teal-300 border border-teal-500/40'
                            }`}>
                                {recState === 'recording' ? 'LIVE REC' : recState === 'paused' ? 'PAUSED' : 'PROCESSING'}
                            </span>

                            {/* Status Indicator */}
                            <span className={`text-[11px] font-medium px-2.5 py-0.5 rounded-full border ${
                                !questionnaireCompleted
                                    ? 'bg-sky-500/15 text-sky-300 border-sky-500/40'
                                    : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
                            }`}>
                                {!questionnaireCompleted ? 'Predefined Questionnaire' : 'AI Follow-ups Active'}
                            </span>
                        </div>
                    </div>
                </div>

                {/* Center: Live Streaming Feedback */}
                <div className="hidden lg:flex items-center gap-3 text-xs text-slate-300">
                    <div className="flex items-center gap-2">
                        <span className="flex items-center gap-1 bg-slate-800 px-2.5 py-1 rounded-md border border-slate-700">
                            <span className={`w-2 h-2 rounded-full ${completedChunks > 0 ? 'bg-emerald-400' : 'bg-slate-500'}`}></span>
                            15s Slices: <strong className="font-mono text-white ml-1">{completedChunks}</strong>
                        </span>
                        {isStreamingChunk && (
                            <span className="flex items-center gap-1.5 text-teal-300 font-semibold animate-pulse">
                                <div className="w-1.5 h-1.5 rounded-full bg-teal-400"></div>
                                Streaming to LangGraph...
                            </span>
                        )}
                    </div>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-2 flex-wrap">
                    {/* Action: Completed Predefined Questionnaire Button */}
                    {!questionnaireCompleted && (
                        <button
                            onClick={async () => {
                                await completePredefinedQuestionnaire();
                            }}
                            className="flex items-center gap-1.5 bg-gradient-to-r from-teal-500 to-emerald-600 hover:from-teal-600 hover:to-emerald-700 text-white font-semibold text-xs px-3.5 py-2 rounded-lg shadow-md transition-all transform active:scale-95 border border-teal-400/30"
                            title="Reveal AI follow-up questions"
                        >
                            <Icons.CheckCircle className="w-3.5 h-3.5" />
                            Completed Predefined Questionnaire
                        </button>
                    )}

                    {/* Quick navigation to AI Gaps if not already there */}
                    {!isGapPage && questionnaireCompleted && (
                        <button
                            onClick={() => navigate(`/officer/cases/${applicationId}/gap-questions`)}
                            className="flex items-center gap-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 font-semibold text-xs px-3 py-2 rounded-lg transition-colors"
                        >
                            <span>View Full AI Gap Analysis</span>
                            <Icons.ArrowRight className="w-3.5 h-3.5" />
                        </button>
                    )}

                    {/* Pause / Resume */}
                    {recState === 'recording' ? (
                        <button
                            onClick={pauseRecording}
                            className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs px-2.5 py-2 rounded-lg border border-slate-700 transition-colors"
                            title="Pause recording"
                        >
                            <Icons.Pause className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">Pause</span>
                        </button>
                    ) : recState === 'paused' ? (
                        <button
                            onClick={resumeRecording}
                            className="flex items-center gap-1 bg-amber-500 hover:bg-amber-600 text-slate-900 font-bold text-xs px-2.5 py-2 rounded-lg transition-colors"
                            title="Resume recording"
                        >
                            <Icons.Play className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">Resume</span>
                        </button>
                    ) : null}

                    {/* Stop Recording */}
                    <button
                        onClick={stopRecording}
                        className="flex items-center gap-1 bg-red-600/80 hover:bg-red-600 text-white text-xs px-2.5 py-2 rounded-lg transition-colors"
                        title="Stop and release microphone"
                    >
                        <Icons.MicOff className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Stop</span>
                    </button>
                </div>
            </div>
        </div>
    );
}
