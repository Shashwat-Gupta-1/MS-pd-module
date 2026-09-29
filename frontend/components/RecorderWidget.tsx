'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card } from './ui/primitives';
import { Icons } from './ui/Icons';
import { useCaseContext } from '../lib/CaseContext';

export type RecState = 'idle' | 'recording' | 'paused' | 'processing';

interface RecorderWidgetProps {
    recState: RecState;
    setRecState: React.Dispatch<React.SetStateAction<RecState>>;
    onStop: () => void;
}

export default function RecorderWidget({ recState, setRecState, onStop }: RecorderWidgetProps) {
    const { consentTimestamp, setConsentTimestamp } = useCaseContext();
    const [time, setTime] = useState(0);
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        if (recState === 'recording') timerRef.current = setInterval(() => setTime(t => t + 1), 1000);
        else if (timerRef.current) clearInterval(timerRef.current);
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }, [recState]);

    const formatTime = (secs: number) => `${Math.floor(secs / 60).toString().padStart(2, '0')}:${(secs % 60).toString().padStart(2, '0')}`;

    return (
        <>
            <Card className="mb-8 p-4 max-w-md w-full border-slate-200">
                <label className="flex items-start gap-3 cursor-pointer">
                    <input type="checkbox" className="mt-1 w-5 h-5 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                        checked={!!consentTimestamp}
                        onChange={(e) => setConsentTimestamp(e.target.checked ? new Date() : null)}
                        disabled={recState !== 'idle'}
                    />
                    <div>
                        <span className="font-semibold text-slate-800 block">Borrower has agreed to audio recording</span>
                        {consentTimestamp && <span className="text-xs text-slate-500">Timestamp: {consentTimestamp.toLocaleTimeString()}</span>}
                    </div>
                </label>
            </Card>

            <div className="relative mb-8">
                <button
                    onClick={() => setRecState(s => s === 'recording' ? 'paused' : 'recording')}
                    disabled={!consentTimestamp}
                    className={`w-32 h-32 rounded-full flex flex-col items-center justify-center text-white shadow-lg transition-transform transform hover:scale-105 disabled:opacity-50 disabled:hover:scale-100 disabled:cursor-not-allowed
                        ${recState === 'recording' ? 'bg-red-500 mic-recording' : recState === 'paused' ? 'bg-amber-500' : 'bg-slate-900'}
                    `}
                >
                    {recState === 'idle' ? <Icons.Mic className="w-10 h-10 mb-1" /> : recState === 'paused' ? <Icons.Play className="w-10 h-10 mb-1" /> : <Icons.Pause className="w-10 h-10 mb-1" />}
                    <span className="font-mono text-xl">{formatTime(time)}</span>
                </button>

                {recState === 'recording' && (
                    <div className="absolute -bottom-12 left-1/2 transform -translate-x-1/2 flex items-end gap-1 h-8">
                        <div className="bar"></div><div className="bar"></div><div className="bar"></div><div className="bar"></div><div className="bar"></div>
                    </div>
                )}
            </div>

            <p className="text-sm text-slate-500 mb-8 flex items-center gap-1"><Icons.Info className="w-4 h-4" /> Conversation is recorded for AI analysis.</p>

            {recState !== 'idle' && (
                <button onClick={onStop} className="flex items-center gap-2 px-6 py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-semibold transition-colors">
                    <Icons.Stop className="w-5 h-5" /> Stop & Analyze
                </button>
            )}
        </>
    );
}
