'use client';

import React, { useState, useEffect } from 'react';
import { Card, Badge } from '../../../../../components/ui/primitives';
import { Icons } from '../../../../../components/ui/Icons';
import CameraCapture from '../../../../../components/CameraCapture';
import { useCaseContext } from '../../../../../lib/CaseContext';
import type { Photo, ApplicationGroundPDSummary, VisionItem } from '../../../../../lib/types';

export default function PhotosPage() {
    const { photos, setPhotos, navigate, caseId, selectedOccupationCode } = useCaseContext();
    const [selectedCat, setSelectedCat] = useState<string>(photos[0]?.category || 'Stock & Shelf Inventory');
    const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const [appSummary, setAppSummary] = useState<ApplicationGroundPDSummary | null>(null);

    const [showResetMenu, setShowResetMenu] = useState<boolean>(false);
    const [isResetting, setIsResetting] = useState<boolean>(false);

    // Ensure selectedCat stays valid when photos array updates dynamically from occupation switch
    useEffect(() => {
        if (photos.length > 0 && (!selectedCat || !photos.some(p => p.category === selectedCat))) {
            setSelectedCat(photos[0].category);
        }
    }, [photos, selectedCat]);

    const activePhoto = photos.find(p => p.category === selectedCat);

    // Fetch initial / updated application summary
    const fetchSummary = async () => {
        try {
            const occParam = selectedOccupationCode || 'kirana';
            const res = await fetch(`http://localhost:8000/api/ground-pd/${caseId}/summary?occupation_code=${occParam}`);
            if (res.ok) {
                const data = await res.json();
                setAppSummary(data);

                // Synchronize uploaded photo records with active occupation tabs
                if (data.photos && Array.isArray(data.photos)) {
                    setPhotos(prev => prev.map(p => {
                        const matched = data.photos.find((sp: any) => sp.category?.toLowerCase() === p.category.toLowerCase());
                        if (matched) {
                            return {
                                ...p,
                                id: matched.id || p.id,
                                status: 'done',
                                url: matched.photo_url || p.url,
                                flags: matched.flags || [],
                                extraction: matched.extraction || p.extraction,
                                gps_status: matched.gps_status,
                                is_live_capture: matched.is_live_capture,
                                is_duplicate: matched.is_duplicate,
                            };
                        }
                        return p;
                    }));
                }
            }
        } catch (err) {
            console.warn("Could not fetch application Ground PD summary:", err);
        }
    };

    useEffect(() => {
        fetchSummary();
    }, [caseId, selectedOccupationCode]);

    // Reset single active category
    const handleResetCategory = async () => {
        setIsResetting(true);
        try {
            const res = await fetch(`http://localhost:8000/api/ground-pd/${caseId}/reset?category=${encodeURIComponent(selectedCat)}`, {
                method: 'POST',
            });
            if (res.ok) {
                setPhotos(prev => prev.map(p => p.category === selectedCat ? { id: p.id, category: p.category, status: 'missing' } : p));
                await fetchSummary();
                setShowResetMenu(false);
            }
        } catch (err) {
            console.error("Failed to reset category:", err);
        } finally {
            setIsResetting(false);
        }
    };

    // Reset all categories across loan case
    const handleResetAll = async () => {
        setIsResetting(true);
        try {
            const res = await fetch(`http://localhost:8000/api/ground-pd/${caseId}/reset`, {
                method: 'POST',
            });
            if (res.ok) {
                setPhotos(prev => prev.map(p => ({ id: p.id, category: p.category, status: 'missing' })));
                setAppSummary(null);
                await fetchSummary();
                setShowResetMenu(false);
            }
        } catch (err) {
            console.error("Failed to reset all categories:", err);
        } finally {
            setIsResetting(false);
        }
    };

    // Handle Live Photo Upload & AI Vision Trigger
    const handleCapture = async (
        file: File,
        gpsData: { lat: number; lng: number; accuracy: number; formatted: string },
        ts: string
    ) => {
        setIsAnalyzing(true);
        setErrorMsg(null);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('application_id', caseId || 'APP-2026-9823');
        formData.append('category', selectedCat);
        formData.append('lat', String(gpsData.lat));
        formData.append('lng', String(gpsData.lng));
        formData.append('accuracy_m', String(gpsData.accuracy));
        formData.append('site_lat', '26.9124');
        formData.append('site_lng', '75.7873');
        formData.append('occupation_code', selectedOccupationCode || 'kirana');

        try {
            const response = await fetch('http://localhost:8000/api/ground-pd/photos', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errText = await response.text();
                throw new Error(`Upload failed (${response.status}): ${errText}`);
            }

            const data = await response.json();
            const photoUrl = data.photo_url || URL.createObjectURL(file);

            // Update photo entry in CaseContext
            const updatedPhoto: Photo = {
                id: data.photo_id || `photo_${Date.now()}`,
                category: selectedCat,
                status: 'done',
                url: photoUrl,
                timestamp: ts,
                gps: gpsData.formatted,
                gps_status: data.gps_status,
                distance_to_site_m: data.distance_to_site_m,
                is_live_capture: data.is_live_capture,
                is_duplicate: data.is_duplicate,
                flags: data.flags || [],
                extraction: data.extraction || {},
            };

            setPhotos(prev => prev.map(p => p.category === selectedCat ? updatedPhoto : p));

            // Refresh aggregated summary
            await fetchSummary();

            // Auto-advance to next missing category
            const nextMissing = photos.find(p => p.status === 'missing' && p.category !== selectedCat);
            if (nextMissing) {
                setSelectedCat(nextMissing.category);
            }

        } catch (err: any) {
            console.error("Vision Analysis Error:", err);
            setErrorMsg(err.message || "Failed to analyze photo with Gemini Vision. Please check backend connection.");
        } finally {
            setIsAnalyzing(false);
        }
    };

    const allDone = photos.filter(p => p.status === 'done').length >= 4;
    const completedCount = photos.filter(p => p.status === 'done').length;

    // Helper format INR currency
    const formatINR = (val?: number | null) => {
        if (val === undefined || val === null) return '₹0';
        return '₹' + Number(val).toLocaleString('en-IN');
    };

    return (
        <div className="max-w-5xl mx-auto animate-fadeIn pb-28">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
                        <Icons.Camera className="w-7 h-7 text-teal-600" />
                        Ground PD Photography & Asset Vision Agent
                    </h2>
                    <p className="text-slate-600 text-sm mt-1">
                        Capture geo-tagged on-site photos. Gemini Multimodal Vision automatically detects stock, equipment, condition grades, and computes itemized INR valuations.
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    {/* Reset Dropdown Button */}
                    <div className="relative">
                        <button
                            type="button"
                            onClick={() => setShowResetMenu(!showResetMenu)}
                            className="px-3.5 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-2 shadow-sm transition-all"
                        >
                            <Icons.RotateCcw className="w-3.5 h-3.5 text-slate-500" />
                            <span>Reset Photos</span>
                            <Icons.ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                        </button>

                        {/* Dropdown Popup Menu */}
                        {showResetMenu && (
                            <div className="absolute right-0 mt-2 w-72 bg-white rounded-2xl shadow-xl border border-slate-200 z-50 p-2 animate-fadeIn">
                                <div className="p-2 border-b border-slate-100">
                                    <p className="text-xs font-bold text-slate-800">Reset Photo Data</p>
                                    <p className="text-[11px] text-slate-500">Choose which photos to delete from DB</p>
                                </div>

                                <div className="py-1 space-y-1">
                                    {/* Option 1: Reset Current Category */}
                                    <button
                                        type="button"
                                        onClick={handleResetCategory}
                                        disabled={isResetting || activePhoto?.status !== 'done'}
                                        className={`w-full text-left p-2.5 rounded-xl text-xs transition-colors flex items-start gap-2.5 ${
                                            activePhoto?.status === 'done'
                                                ? 'hover:bg-amber-50 text-slate-800 cursor-pointer'
                                                : 'opacity-50 text-slate-400 cursor-not-allowed'
                                        }`}
                                    >
                                        <div className="w-7 h-7 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center shrink-0 font-bold">
                                            1
                                        </div>
                                        <div>
                                            <p className="font-semibold text-slate-900">
                                                Reset Active Category
                                            </p>
                                            <p className="text-[10px] text-slate-500">
                                                Delete photo for "{selectedCat}" only
                                            </p>
                                        </div>
                                    </button>

                                    {/* Option 2: Reset All Categories */}
                                    <button
                                        type="button"
                                        onClick={handleResetAll}
                                        disabled={isResetting}
                                        className="w-full text-left p-2.5 rounded-xl text-xs hover:bg-red-50 text-red-700 transition-colors flex items-start gap-2.5 cursor-pointer"
                                    >
                                        <div className="w-7 h-7 rounded-lg bg-red-100 text-red-700 flex items-center justify-center shrink-0">
                                            <Icons.AlertTriangle className="w-4 h-4 text-red-700" />
                                        </div>
                                        <div>
                                            <p className="font-bold text-red-800">
                                                Reset All Categories (Clean Start)
                                            </p>
                                            <p className="text-[10px] text-red-600">
                                                Wipe all 6 photos & start fresh from scratch
                                            </p>
                                        </div>
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="bg-white px-4 py-2 rounded-xl border border-slate-200 shadow-sm flex items-center gap-3">
                        <div className="text-right">
                            <span className="text-xs text-slate-500 font-medium">Completion Progress</span>
                            <p className="text-sm font-bold text-slate-800">{completedCount} of {photos.length} Captured</p>
                        </div>
                        <div className="w-10 h-10 rounded-full bg-teal-50 border border-teal-200 flex items-center justify-center font-bold text-teal-700 text-sm">
                            {Math.round((completedCount / photos.length) * 100)}%
                        </div>
                    </div>
                </div>
            </div>

            {/* Category Selector Tabs */}
            <div className="flex flex-wrap gap-2 mb-6">
                {photos.map(p => {
                    const isSelected = selectedCat === p.category;
                    const isDone = p.status === 'done';
                    const hasFlags = p.flags && p.flags.length > 0;
                    return (
                        <button
                            key={p.id}
                            onClick={() => setSelectedCat(p.category)}
                            className={`px-4 py-2.5 rounded-xl text-sm font-medium border flex items-center gap-2.5 transition-all shadow-sm ${
                                isSelected
                                    ? 'bg-slate-900 text-white border-slate-900 ring-2 ring-teal-500 ring-offset-2'
                                    : isDone
                                    ? 'bg-emerald-50/80 border-emerald-200 text-emerald-800 hover:bg-emerald-100'
                                    : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                            }`}
                        >
                            {isDone ? (
                                hasFlags ? (
                                    <Icons.AlertTriangle className="w-4 h-4 text-amber-500" />
                                ) : (
                                    <Icons.CheckCircle className="w-4 h-4 text-emerald-600" />
                                )
                            ) : (
                                <span className="w-2 h-2 rounded-full bg-slate-300"></span>
                            )}
                            <span>{p.category}</span>
                            {isDone && p.extraction?.estimated_total_value_max ? (
                                <span className={`text-xs px-2 py-0.5 rounded-md font-mono ${isSelected ? 'bg-slate-800 text-teal-300' : 'bg-emerald-100 text-emerald-800'}`}>
                                    {formatINR(p.extraction.estimated_total_value_max)}
                                </span>
                            ) : null}
                        </button>
                    );
                })}
            </div>

            {/* Error Message Toast */}
            {errorMsg && (
                <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-2xl flex items-start gap-3 text-red-800 text-sm">
                    <Icons.AlertTriangle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                    <div>
                        <p className="font-bold">Vision Analysis Error</p>
                        <p className="text-xs text-red-700 mt-0.5">{errorMsg}</p>
                    </div>
                </div>
            )}

            {/* Main Section: Camera & Live Vision Details */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-8">
                {/* Left: Camera Capture Box */}
                <div className="lg:col-span-6 flex flex-col">
                    <Card className="p-5 flex-1 flex flex-col justify-between">
                        <div>
                            <div className="flex items-center justify-between mb-3">
                                <div>
                                    <h3 className="font-bold text-slate-800 text-base">
                                        Capture: <span className="text-teal-700">{selectedCat}</span>
                                    </h3>
                                    <p className="text-xs text-slate-500">
                                        Frame business assets clearly with adequate lighting.
                                    </p>
                                </div>
                                {activePhoto?.status === 'done' && (
                                    <Badge variant="success">Photo Saved & Analyzed</Badge>
                                )}
                            </div>

                            <CameraCapture
                                key={selectedCat}
                                onCapture={handleCapture}
                                isUploading={isAnalyzing}
                                categoryName={selectedCat}
                                existingPhotoUrl={activePhoto?.status === 'done' ? activePhoto.url : undefined}
                            />
                        </div>

                        {/* Active Photo Metadata Strip */}
                        {activePhoto?.status === 'done' && (
                            <div className="mt-4 p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono text-slate-600 flex flex-wrap items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                    <span className="flex items-center gap-1">
                                        <Icons.MapPin className="w-3.5 h-3.5 text-slate-500" />
                                        {activePhoto.gps || '26.9124° N, 75.7873° E'}
                                    </span>
                                    <span className="text-slate-300">|</span>
                                    <span className="flex items-center gap-1">
                                        <Icons.Clock className="w-3.5 h-3.5 text-slate-500" />
                                        {activePhoto.timestamp || 'Just now'}
                                    </span>
                                </div>
                                <div className="flex items-center gap-1.5">
                                    {activePhoto.is_live_capture ? (
                                        <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded text-[10px] font-semibold">
                                            <Icons.ShieldCheck className="w-3 h-3 text-emerald-600" />
                                            Live Capture
                                        </span>
                                    ) : (
                                        <span className="inline-flex items-center gap-1 text-amber-700 bg-amber-100 px-2 py-0.5 rounded text-[10px] font-semibold">
                                            <Icons.AlertTriangle className="w-3 h-3 text-amber-600" />
                                            No EXIF
                                        </span>
                                    )}
                                    {activePhoto.is_duplicate && (
                                        <span className="inline-flex items-center gap-1 text-red-700 bg-red-100 px-2 py-0.5 rounded text-[10px] font-semibold">
                                            <Icons.AlertTriangle className="w-3 h-3 text-red-600" />
                                            Duplicate pHash
                                        </span>
                                    )}
                                </div>
                            </div>
                        )}
                    </Card>
                </div>

                {/* Right: Gemini Vision AI Extraction Card */}
                <div className="lg:col-span-6 flex flex-col">
                    <Card className="p-5 flex-1 flex flex-col bg-white border border-slate-200 shadow-sm relative overflow-hidden">
                        {/* Shimmer loading overlay during analysis */}
                        {isAnalyzing && (
                            <div className="absolute inset-0 bg-white/90 backdrop-blur-sm z-30 flex flex-col items-center justify-center p-6 text-center animate-fadeIn">
                                <div className="relative w-20 h-20 mb-4 flex items-center justify-center">
                                    <div className="absolute inset-0 rounded-full border-4 border-teal-200 border-t-teal-600 animate-spin"></div>
                                    <Icons.Camera className="w-8 h-8 text-teal-600 animate-pulse" />
                                </div>
                                <h4 className="font-bold text-slate-800 text-lg mb-1">
                                    Gemini Multimodal Vision Analyzing...
                                </h4>
                                <p className="text-xs text-slate-500 max-w-xs mb-3">
                                    Detecting physical inventory, equipment models, condition grading, and computing Indian Market valuations.
                                </p>
                                <div className="flex items-center gap-2 text-[11px] font-mono text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
                                    <span className="w-2 h-2 rounded-full bg-teal-500 animate-ping"></span>
                                    Running EXIF, GPS & pHash Anti-Fraud Checks
                                </div>
                            </div>
                        )}

                        <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
                            <div className="flex items-center gap-2">
                                <div className="w-8 h-8 rounded-lg bg-teal-500/10 text-teal-600 flex items-center justify-center">
                                    <Icons.Sparkles className="w-4 h-4 text-teal-600" />
                                </div>
                                <div>
                                    <h3 className="font-bold text-slate-800 text-sm">
                                        Gemini Vision Asset Extraction
                                    </h3>
                                    <p className="text-[11px] text-slate-500">
                                        Ground PD Physical Verification Analysis
                                    </p>
                                </div>
                            </div>
                            {activePhoto?.extraction?.estimated_total_value_max ? (
                                <div className="text-right">
                                    <span className="text-[10px] text-slate-400 uppercase font-semibold">Subtotal Valuation</span>
                                    <p className="text-sm font-bold text-teal-700 font-mono">
                                        {formatINR(activePhoto.extraction.estimated_total_value_min)} – {formatINR(activePhoto.extraction.estimated_total_value_max)}
                                    </p>
                                </div>
                            ) : null}
                        </div>

                        {activePhoto?.status === 'done' && activePhoto.extraction ? (
                            <div className="space-y-4 flex-1 flex flex-col justify-between">
                                {/* Overview Badges */}
                                <div className="grid grid-cols-3 gap-2">
                                    <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100 text-center">
                                        <span className="text-[10px] text-slate-400 block font-medium">Premises Type</span>
                                        <span className="text-xs font-bold text-slate-800 capitalize">
                                            {activePhoto.extraction.premises_type?.replace('_', ' ') || 'Retail Shop'}
                                        </span>
                                    </div>
                                    <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100 text-center">
                                        <span className="text-[10px] text-slate-400 block font-medium">Stock Density</span>
                                        <span className={`text-xs font-bold capitalize ${
                                            activePhoto.extraction.stock_level === 'high' ? 'text-emerald-700' :
                                            activePhoto.extraction.stock_level === 'medium' ? 'text-teal-700' : 'text-amber-700'
                                        }`}>
                                            {activePhoto.extraction.stock_level || 'Normal'}
                                        </span>
                                    </div>
                                    <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100 text-center">
                                        <span className="text-[10px] text-slate-400 block font-medium">Condition</span>
                                        <span className="text-xs font-bold text-slate-800 capitalize">
                                            {activePhoto.extraction.overall_condition || 'Good'}
                                        </span>
                                    </div>
                                </div>

                                {/* Detected Items Table */}
                                <div>
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="text-xs font-bold text-slate-700">Detected Assets & Inventory:</span>
                                        <span className="text-[11px] text-slate-500 font-mono">
                                            {activePhoto.extraction.items?.length || 0} items identified
                                        </span>
                                    </div>

                                    <div className="border border-slate-200 rounded-xl overflow-hidden max-h-48 overflow-y-auto">
                                        <table className="w-full text-left text-xs">
                                            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium sticky top-0">
                                                <tr>
                                                    <th className="py-2 px-3">Item / Asset</th>
                                                    <th className="py-2 px-2 text-center">Qty</th>
                                                    <th className="py-2 px-2 text-center">Grade</th>
                                                    <th className="py-2 px-3 text-right">Est. Valuation</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-slate-100">
                                                {activePhoto.extraction.items && activePhoto.extraction.items.length > 0 ? (
                                                    activePhoto.extraction.items.map((item: VisionItem, idx: number) => (
                                                        <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                                                            <td className="py-2 px-3 text-slate-800 font-medium">
                                                                {item.name}
                                                            </td>
                                                            <td className="py-2 px-2 text-center font-mono text-slate-600">
                                                                {item.count}
                                                            </td>
                                                            <td className="py-2 px-2 text-center">
                                                                <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold capitalize ${
                                                                    item.condition === 'new' || item.condition === 'good'
                                                                        ? 'bg-emerald-100 text-emerald-800'
                                                                        : 'bg-amber-100 text-amber-800'
                                                                }`}>
                                                                    {item.condition}
                                                                </span>
                                                            </td>
                                                            <td className="py-2 px-3 text-right font-mono text-slate-700 font-semibold">
                                                                {formatINR(item.total_value_min_inr)} – {formatINR(item.total_value_max_inr)}
                                                            </td>
                                                        </tr>
                                                    ))
                                                ) : (
                                                    <tr>
                                                        <td colSpan={4} className="py-4 text-center text-slate-400">
                                                            No specific items detected. General premises captured.
                                                        </td>
                                                    </tr>
                                                )}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>

                                {/* Gemini Observation Summary */}
                                {activePhoto.extraction.summary && (
                                    <div className="p-3 bg-teal-50/60 border border-teal-100 rounded-xl">
                                        <p className="text-[11px] font-bold text-teal-900 mb-1 flex items-center gap-1.5">
                                            <Icons.Lightbulb className="w-3.5 h-3.5 text-teal-600 shrink-0" />
                                            <span>AI Vision Field Note:</span>
                                        </p>
                                        <p className="text-xs text-slate-700 leading-relaxed italic">
                                            "{activePhoto.extraction.summary}"
                                        </p>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400">
                                <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center mb-3">
                                    <Icons.Image className="w-6 h-6 text-slate-300" />
                                </div>
                                <p className="text-sm font-medium text-slate-600 mb-1">
                                    No photo captured yet for {selectedCat}
                                </p>
                                <p className="text-xs text-slate-400 max-w-xs">
                                    Take or upload a photo using the left panel. Gemini Multimodal AI will extract asset records instantly.
                                </p>
                            </div>
                        )}
                    </Card>
                </div>
            </div>

            {/* Aggregated Application Asset Valuation Summary */}
            {appSummary && (
                <Card className="p-6 mb-8 bg-gradient-to-br from-slate-900 via-slate-800 to-teal-950 text-white border-0 shadow-xl rounded-2xl">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 border-b border-white/10 pb-4">
                        <div>
                            <div className="flex items-center gap-2 mb-1">
                                <span className="bg-teal-500/20 text-teal-300 text-xs px-2.5 py-0.5 rounded-full font-mono border border-teal-400/30">
                                    Ground PD Synthesis
                                </span>
                                <span className="text-xs text-slate-400 font-mono">
                                    App ID: {caseId}
                                </span>
                            </div>
                            <h3 className="text-xl font-bold text-white">
                                Total Aggregated Asset Valuation Summary
                            </h3>
                        </div>

                        {/* Completion Gate Tag */}
                        <div className="flex items-center gap-2">
                            {appSummary.completion_gate?.is_complete ? (
                                <span className="inline-flex items-center gap-1.5 bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 px-3 py-1.5 rounded-xl text-xs font-semibold">
                                    <Icons.CheckCircle className="w-4 h-4" />
                                    Mandatory Categories Gate: Passed
                                </span>
                            ) : (
                                <span className="inline-flex items-center gap-1.5 bg-amber-500/20 text-amber-300 border border-amber-500/40 px-3 py-1.5 rounded-xl text-xs font-semibold">
                                    <Icons.AlertTriangle className="w-4 h-4" />
                                    {appSummary.completion_gate?.total_mandatory_uploaded || 0} / {appSummary.completion_gate?.total_mandatory_required || 3} Mandatory Categories Uploaded
                                </span>
                            )}
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                        <div className="bg-white/5 border border-white/10 p-4 rounded-xl backdrop-blur-sm">
                            <span className="text-xs text-slate-400 block mb-1">Aggregated Asset Value (INR)</span>
                            <p className="text-xl font-extrabold text-teal-300 font-mono">
                                {formatINR(appSummary.total_asset_value_min_inr)} – {formatINR(appSummary.total_asset_value_max_inr)}
                            </p>
                            <span className="text-[10px] text-slate-400 mt-1 block">
                                Combined shelf stock + machinery
                            </span>
                        </div>

                        <div className="bg-white/5 border border-white/10 p-4 rounded-xl backdrop-blur-sm">
                            <span className="text-xs text-slate-400 block mb-1">Total Verified Photos</span>
                            <p className="text-xl font-extrabold text-white font-mono">
                                {appSummary.total_photos} Verified
                            </p>
                            <span className="text-[10px] text-slate-400 mt-1 block">
                                GPS & pHash validated
                            </span>
                        </div>

                        <div className="bg-white/5 border border-white/10 p-4 rounded-xl backdrop-blur-sm">
                            <span className="text-xs text-slate-400 block mb-1">Audit & Risk Flags</span>
                            <p className={`text-xl font-extrabold font-mono ${
                                appSummary.audit_flags?.length > 0 ? 'text-amber-300' : 'text-emerald-400'
                            }`}>
                                {appSummary.audit_flags?.length || 0} Flags
                            </p>
                            <span className="text-[10px] text-slate-400 mt-1 block">
                                {appSummary.audit_flags?.length > 0 ? 'Review flagged items' : 'Zero fraud flags'}
                            </span>
                        </div>
                    </div>

                    {/* Audit Flags Alert if any */}
                    {appSummary.audit_flags && appSummary.audit_flags.length > 0 && (
                        <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-2.5 text-xs text-amber-200">
                            <Icons.AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                            <div>
                                <span className="font-bold text-amber-300">Audit Flags Detected: </span>
                                <span className="font-mono text-[11px]">
                                    {appSummary.audit_flags.join(' • ')}
                                </span>
                            </div>
                        </div>
                    )}
                </Card>
            )}

            {/* Bottom Navigation */}
            <div className="flex items-center justify-between pt-4 border-t border-slate-200">
                <button
                    onClick={() => navigate('/officer/new-case')}
                    className="px-6 py-2.5 rounded-xl font-medium border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors text-sm"
                >
                    ← Back to Profile
                </button>

                <div className="flex items-center gap-3">
                    <button
                        onClick={() => navigate(`/officer/cases/${caseId || 'APP-2026-9823'}/review`)}
                        className="px-8 py-3 rounded-xl font-bold shadow-md transition-all text-sm flex items-center gap-2 bg-slate-900 text-white hover:bg-slate-800"
                    >
                        <span>Continue to Final Review</span>
                        <span className="text-xs bg-slate-700 px-2 py-0.5 rounded-md">
                            Step 6 →
                        </span>
                    </button>
                </div>
            </div>
        </div>
    );
}
