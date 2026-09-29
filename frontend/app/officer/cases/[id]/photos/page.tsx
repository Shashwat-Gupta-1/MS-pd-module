'use client';

import React, { useState } from 'react';
import { Card, Badge } from '../../../../../components/ui/primitives';
import { Icons } from '../../../../../components/ui/Icons';
import CameraCapture from '../../../../../components/CameraCapture';
import { useCaseContext } from '../../../../../lib/CaseContext';

export default function PhotosPage() {
    const { photos, setPhotos, navigate } = useCaseContext();
    const [selectedCat, setSelectedCat] = useState<string>(photos[0].category);

    const handleCapture = (url: string, gps: string, ts: string) => {
        setPhotos(prev => prev.map(p => p.category === selectedCat ? { ...p, status: 'done', url, gps, timestamp: ts } : p));
        // Auto advance to next missing
        const nextMissing = photos.find(p => p.status === 'missing' && p.category !== selectedCat);
        if (nextMissing) setSelectedCat(nextMissing.category);
    };

    const allDone = photos.every(p => p.status === 'done');

    return (
        <div className="max-w-4xl mx-auto animate-fadeIn pb-24">
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Required Photography</h2>
            <p className="text-slate-600 mb-6">Capture live photos. GPS and Timestamps will be automatically embedded.</p>

            <div className="flex flex-wrap gap-2 mb-8">
                {photos.map(p => (
                    <button
                        key={p.id} onClick={() => setSelectedCat(p.category)}
                        className={`px-4 py-2 rounded-full text-sm font-medium border flex items-center gap-2 transition-colors
                            ${selectedCat === p.category ? 'ring-2 ring-teal-500 ring-offset-2' : ''}
                            ${p.status === 'done' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-white border-slate-300 text-slate-700'}
                        `}
                    >
                        {p.status === 'done' ? <Icons.CheckCircle className="w-4 h-4"/> : <Icons.AlertTriangle className="w-4 h-4 text-amber-500"/>}
                        {p.category}
                    </button>
                ))}
            </div>

            <Card className="p-6 mb-8">
                <h3 className="font-bold text-slate-800 mb-4 flex justify-between">
                    <span>Capture: {selectedCat}</span>
                    {photos.find(p => p.category === selectedCat)?.status === 'done' && <Badge variant="success">Completed</Badge>}
                </h3>
                <CameraCapture onCapture={handleCapture} />

                {photos.find(p => p.category === selectedCat)?.status === 'done' && (
                    <div className="mt-4 p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-500 font-mono flex flex-col gap-1">
                        <span>📸 File: {photos.find(p => p.category === selectedCat)?.url}</span>
                        <span>📍 GPS: {photos.find(p => p.category === selectedCat)?.gps}</span>
                        <span>🕒 Time: {photos.find(p => p.category === selectedCat)?.timestamp}</span>
                    </div>
                )}
            </Card>

            <div className="flex justify-end">
                <button
                    onClick={() => navigate('/officer/cases/APP-2026-9823/review')}
                    className={`px-6 py-3 rounded-xl font-semibold shadow-sm transition-colors ${allDone ? 'bg-slate-900 text-white hover:bg-slate-800' : 'bg-slate-900 text-white opacity-90'}`}
                >
                    {allDone ? 'Continue to Final Review' : 'Skip Remaining (Not Recommended)'}
                </button>
            </div>
        </div>
    );
}
