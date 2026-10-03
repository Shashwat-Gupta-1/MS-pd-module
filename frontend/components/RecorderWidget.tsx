'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card } from './ui/primitives';
import { Icons } from './ui/Icons';
import { useCaseContext } from '../lib/CaseContext';

export type RecState = 'idle' | 'recording' | 'paused' | 'ready' | 'processing';

interface RecorderWidgetProps {
    recState: RecState;
    setRecState: React.Dispatch<React.SetStateAction<RecState>>;
    onAudioReady: (file: File | Blob, filename: string) => void;
}

export default function RecorderWidget({ recState, setRecState, onAudioReady }: RecorderWidgetProps) {
    const { consentTimestamp, setConsentTimestamp } = useCaseContext();
    const [time, setTime] = useState(0);
    const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
    const [audioUrl, setAudioUrl] = useState<string | null>(null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [recordingMode, setRecordingMode] = useState<'mic' | 'upload'>('mic');
    const [audioError, setAudioError] = useState<string | null>(null);

    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioChunksRef = useRef<Blob[]>([]);
    const fileInputRef = useRef<HTMLInputElement | null>(null);

    // Timer logic
    useEffect(() => {
        if (recState === 'recording') {
            timerRef.current = setInterval(() => setTime(t => t + 1), 1000);
        } else if (timerRef.current) {
            clearInterval(timerRef.current);
        }
        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, [recState]);

    const formatTime = (secs: number) =>
        `${Math.floor(secs / 60).toString().padStart(2, '0')}:${(secs % 60).toString().padStart(2, '0')}`;

    // Start Microphone Recording
    const startRecording = async () => {
        setAudioError(null);
        audioChunksRef.current = [];
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : 'audio/webm';
            
            const mediaRecorder = new MediaRecorder(stream, { mimeType });
            mediaRecorderRef.current = mediaRecorder;

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                setRecordedBlob(blob);
                const url = URL.createObjectURL(blob);
                setAudioUrl(url);
                setRecState('ready');
                // Stop all tracks to release mic
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start(250); // collect 250ms chunks
            setTime(0);
            setRecState('recording');
        } catch (err: any) {
            console.error('Error accessing microphone:', err);
            setAudioError('Microphone access denied or not available. Please allow mic permissions or upload an audio file below.');
            setRecState('idle');
        }
    };

    // Pause / Resume Recording
    const pauseRecording = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
            mediaRecorderRef.current.pause();
            setRecState('paused');
        }
    };

    const resumeRecording = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'paused') {
            mediaRecorderRef.current.resume();
            setRecState('recording');
        }
    };

    // Stop Recording
    const stopRecording = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            mediaRecorderRef.current.stop();
        }
    };

    // Handle File Upload
    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        setAudioError(null);
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            setSelectedFile(file);
            const url = URL.createObjectURL(file);
            setAudioUrl(url);
            setRecState('ready');
        }
    };

    // Trigger analysis
    const handleAnalyze = () => {
        if (selectedFile) {
            onAudioReady(selectedFile, selectedFile.name);
        } else if (recordedBlob) {
            onAudioReady(recordedBlob, `recording_${Date.now()}.webm`);
        }
    };

    // Reset recorder
    const handleReset = () => {
        if (audioUrl) URL.revokeObjectURL(audioUrl);
        setRecordedBlob(null);
        setSelectedFile(null);
        setAudioUrl(null);
        setTime(0);
        setRecState('idle');
    };

    return (
        <div className="w-full flex flex-col items-center">
            {/* 1. Borrower Consent Card */}
            <Card className="mb-6 p-4 max-w-lg w-full border-slate-200 bg-white shadow-sm">
                <label className="flex items-start gap-3 cursor-pointer">
                    <input
                        type="checkbox"
                        className="mt-1 w-5 h-5 rounded border-slate-300 text-teal-600 focus:ring-teal-500 cursor-pointer"
                        checked={!!consentTimestamp}
                        onChange={(e) => setConsentTimestamp(e.target.checked ? new Date() : null)}
                        disabled={recState === 'recording' || recState === 'processing'}
                    />
                    <div>
                        <span className="font-semibold text-slate-800 block">
                            Borrower has agreed to audio recording & Personal Discussion verification
                        </span>
                        {consentTimestamp ? (
                            <span className="text-xs text-emerald-600 font-medium flex items-center gap-1 mt-0.5">
                                <Icons.CheckCircle className="w-3.5 h-3.5" /> Consent captured: {consentTimestamp.toLocaleTimeString()}
                            </span>
                        ) : (
                            <span className="text-xs text-amber-600 font-medium block mt-0.5">
                                * Mandatory compliance consent required before recording
                            </span>
                        )}
                    </div>
                </label>
            </Card>

            {/* Mode Switcher Tabs */}
            {recState === 'idle' && (
                <div className="flex gap-2 p-1 bg-slate-100 rounded-xl mb-6">
                    <button
                        onClick={() => setRecordingMode('mic')}
                        className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors flex items-center gap-2 ${
                            recordingMode === 'mic' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'
                        }`}
                    >
                        <Icons.Mic className="w-4 h-4" /> Live Microphone
                    </button>
                    <button
                        onClick={() => setRecordingMode('upload')}
                        className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors flex items-center gap-2 ${
                            recordingMode === 'upload' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'
                        }`}
                    >
                        <Icons.Upload className="w-4 h-4" /> Upload Audio File
                    </button>
                </div>
            )}

            {/* Error Banner */}
            {audioError && (
                <div className="mb-6 p-3 max-w-lg w-full bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center gap-2">
                    <Icons.AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>{audioError}</span>
                </div>
            )}

            {/* 2. Recording / Upload Interface */}
            {recordingMode === 'mic' && recState !== 'ready' && (
                <div className="relative mb-6 flex flex-col items-center">
                    {recState === 'idle' ? (
                        <button
                            onClick={startRecording}
                            disabled={!consentTimestamp}
                            className="w-32 h-32 rounded-full flex flex-col items-center justify-center text-white bg-slate-900 hover:bg-slate-800 shadow-xl transition-transform transform hover:scale-105 disabled:opacity-40 disabled:hover:scale-100 disabled:cursor-not-allowed"
                            title={!consentTimestamp ? "Please capture consent first" : "Start Recording"}
                        >
                            <Icons.Mic className="w-10 h-10 mb-1 text-teal-400" />
                            <span className="text-xs font-semibold tracking-wide">START REC</span>
                        </button>
                    ) : (
                        <div className="flex flex-col items-center">
                            <div
                                className={`w-32 h-32 rounded-full flex flex-col items-center justify-center text-white shadow-2xl transition-all ${
                                    recState === 'recording'
                                        ? 'bg-red-600 animate-pulse ring-8 ring-red-100'
                                        : 'bg-amber-500 ring-8 ring-amber-100'
                                }`}
                            >
                                <span className="font-mono text-2xl font-bold tracking-wider">{formatTime(time)}</span>
                                <span className="text-[10px] uppercase font-bold tracking-widest mt-1 opacity-90">
                                    {recState === 'recording' ? 'RECORDING' : 'PAUSED'}
                                </span>
                            </div>

                            {/* Action Controls */}
                            <div className="flex items-center gap-4 mt-6">
                                {recState === 'recording' ? (
                                    <button
                                        onClick={pauseRecording}
                                        className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-sm font-semibold flex items-center gap-1.5 transition-colors"
                                    >
                                        <Icons.Pause className="w-4 h-4" /> Pause
                                    </button>
                                ) : (
                                    <button
                                        onClick={resumeRecording}
                                        className="px-4 py-2 bg-amber-50 hover:bg-amber-100 text-amber-700 rounded-lg text-sm font-semibold flex items-center gap-1.5 transition-colors"
                                    >
                                        <Icons.Play className="w-4 h-4" /> Resume
                                    </button>
                                )}
                                <button
                                    onClick={stopRecording}
                                    className="px-5 py-2.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-bold flex items-center gap-2 shadow-sm transition-colors"
                                >
                                    <Icons.Stop className="w-4 h-4" /> Stop & Finish
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Upload Mode */}
            {recordingMode === 'upload' && recState === 'idle' && (
                <div className="w-full max-w-lg mb-6">
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileSelect}
                        accept="audio/*,.mp3,.wav,.m4a,.webm,.ogg,.aac"
                        className="hidden"
                    />
                    <div
                        onClick={() => consentTimestamp && fileInputRef.current?.click()}
                        className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all ${
                            consentTimestamp
                                ? 'border-teal-300 hover:border-teal-500 bg-teal-50/30 hover:bg-teal-50/60 cursor-pointer'
                                : 'border-slate-200 bg-slate-50 opacity-50 cursor-not-allowed'
                        }`}
                    >
                        <div className="w-12 h-12 rounded-full bg-teal-100 text-teal-600 flex items-center justify-center mx-auto mb-3">
                            <Icons.Upload className="w-6 h-6" />
                        </div>
                        <h4 className="font-semibold text-slate-800 text-sm mb-1">Click to select an audio file</h4>
                        <p className="text-xs text-slate-500">Supports MP3, WAV, M4A, AAC, WebM (e.g. test audio)</p>
                    </div>
                </div>
            )}

            {/* Audio Ready Preview State */}
            {recState === 'ready' && audioUrl && (
                <Card className="w-full max-w-lg p-5 mb-6 border-slate-200 bg-white shadow-sm flex flex-col items-center">
                    <div className="flex items-center gap-3 w-full mb-4">
                        <div className="w-10 h-10 rounded-xl bg-teal-50 text-teal-600 flex items-center justify-center flex-shrink-0">
                            <Icons.FileText className="w-5 h-5" />
                        </div>
                        <div className="flex-1 min-w-0">
                            <h4 className="text-sm font-semibold text-slate-800 truncate">
                                {selectedFile ? selectedFile.name : `Live Recording (${formatTime(time)})`}
                            </h4>
                            <p className="text-xs text-slate-500">Audio ready for speech-to-text and AI analysis</p>
                        </div>
                        <button
                            onClick={handleReset}
                            className="text-xs text-slate-400 hover:text-red-500 font-medium px-2 py-1 rounded hover:bg-slate-50 transition-colors"
                        >
                            Reset
                        </button>
                    </div>

                    <audio src={audioUrl} controls className="w-full mb-5 rounded-lg" />

                    <button
                        onClick={handleAnalyze}
                        className="w-full py-3.5 bg-teal-600 hover:bg-teal-700 text-white rounded-xl font-bold flex items-center justify-center gap-2 shadow-md hover:shadow-lg transition-all"
                    >
                        <Icons.CheckCircle className="w-5 h-5" />
                        Run Agent 1 (Transcribe & Tag Dialogue)
                    </button>
                </Card>
            )}

            <p className="text-xs text-slate-400 flex items-center gap-1.5 mt-2">
                <Icons.Info className="w-4 h-4 text-slate-400 flex-shrink-0" />
                Audio is processed securely with faster-whisper and Gemini 3.5 dialogue turn parsing.
            </p>
        </div>
    );
}
