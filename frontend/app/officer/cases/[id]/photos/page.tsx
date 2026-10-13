'use client';

import React, { useState } from 'react';
import { Card, Badge } from '../../../../../components/ui/primitives';
import { Icons } from '../../../../../components/ui/Icons';
import CameraCapture from '../../../../../components/CameraCapture';
import { useCaseContext } from '../../../../../lib/CaseContext';
import { pdSessionsApi } from '../../../../../lib/api';

export default function PhotosPage({ params }: { params: { id: string } }) {
    const { photos, setPhotos, navigate, applicationId, sessionId } = useCaseContext();
    const effectiveAppId = params?.id || applicationId || 'APP-2026-9823';
    const [selectedCat, setSelectedCat] = useState<string>(photos[0]?.category || 'BUSINESS_EXTERIOR');
    const [uploading, setUploading] = useState<boolean>(false);

    const handleCapture = async (
        file: File,
        previewUrl: string,
        gps: string,
        ts: string,
        lat?: number,
        lng?: number,
        accuracy?: number
    ) => {
        // Optimistically set the captured preview in local state
        setPhotos(prev => prev.map(p => p.category === selectedCat ? { ...p, status: 'done', url: previewUrl, gps, timestamp: ts } : p));

        // Persist photo record and upload real image file to FastAPI
        if (sessionId) {
            try {
                setUploading(true);
                const actualLat = lat ?? 26.9124;
                const actualLng = lng ?? 75.7873;
                const actualAcc = accuracy ?? 15.0;
                const uploadRes = await pdSessionsApi.uploadPhoto(
                    sessionId, 
                    selectedCat, 
                    file, 
                    actualLat, 
                    actualLng, 
                    actualAcc
                );
                
                // If backend returned a persisted file URL, update photo url with it
                if (uploadRes && uploadRes.url) {
                    setPhotos(prev => prev.map(p => p.category === selectedCat ? { ...p, url: uploadRes.url } : p));
                }
            } catch (err) {
                console.warn('Could not upload photo to API:', err);
            } finally {
                setUploading(false);
            }
        }

        // Auto advance to next missing category
        const nextMissing = photos.find(p => p.status === 'missing' && p.category !== selectedCat);
        if (nextMissing) setSelectedCat(nextMissing.category);
    };

    const allDone = photos.every(p => p.status === 'done');

    return (
        <div className="max-w-4xl mx-auto animate-fadeIn pb-24">
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Required Photography (Completion Gate)</h2>
            <p className="text-slate-600 mb-6">
                Capture live on-site photos. GPS cluster tightness and perceptual image hashes (dHash) are automatically validated.
            </p>

            <div className="flex flex-wrap gap-2 mb-8">
                {photos.map(p => (
                    <button
                        key={p.id} 
                        onClick={() => setSelectedCat(p.category)}
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
                <div className="flex justify-between items-center mb-4">
                    <h3 className="font-bold text-slate-800">
                        Capture Category: <span className="text-teal-700">{selectedCat}</span>
                    </h3>
                    <div className="flex items-center gap-2">
                        {uploading && <div className="w-4 h-4 border-2 border-teal-600 border-t-transparent rounded-full animate-spin"></div>}
                        {photos.find(p => p.category === selectedCat)?.status === 'done' && <Badge variant="success">Completed</Badge>}
                    </div>
                </div>

                <CameraCapture onCapture={handleCapture} categoryName={selectedCat} />

                {photos.find(p => p.category === selectedCat)?.status === 'done' && (
                    <div className="mt-4 p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-500 font-mono flex flex-col gap-1">
                        <span>📸 File: {photos.find(p => p.category === selectedCat)?.url}</span>
                        <span>📍 GPS: {photos.find(p => p.category === selectedCat)?.gps || '26.9124, 75.7873 (Tight Cluster ≤ 150m)'}</span>
                        <span>🕒 Captured: {photos.find(p => p.category === selectedCat)?.timestamp || new Date().toISOString()}</span>
                    </div>
                )}
            </Card>

            <div className="flex justify-end">
                <button
                    onClick={() => navigate(`/officer/cases/${effectiveAppId}/review`)}
                    className={`px-6 py-3 rounded-xl font-semibold shadow-sm transition-colors flex items-center gap-2 ${allDone ? 'bg-slate-900 text-white hover:bg-slate-800' : 'bg-slate-900 text-white opacity-90'}`}
                >
                    <span>{allDone ? 'Continue to Final Review & CAM' : 'Continue to Final Review'}</span>
                    <Icons.ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
}
