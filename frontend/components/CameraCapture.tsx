'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Icons } from './ui/Icons';
import { Badge } from './ui/primitives';

interface CameraCaptureProps {
    onCapture: (file: File, gpsData: { lat: number; lng: number; accuracy: number; formatted: string }, timestamp: string) => void;
    isUploading?: boolean;
    categoryName?: string;
    existingPhotoUrl?: string;
}

export default function CameraCapture({ onCapture, isUploading = false, categoryName, existingPhotoUrl }: CameraCaptureProps) {
    const [mode, setMode] = useState<'upload' | 'camera'>('upload');
    const [previewUrl, setPreviewUrl] = useState<string | null>(existingPhotoUrl || null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [gps, setGps] = useState<{ lat: number; lng: number; accuracy: number; formatted: string }>({
        lat: 26.9124,
        lng: 75.7873,
        accuracy: 4.5,
        formatted: "26.9124° N, 75.7873° E"
    });
    const [gpsStatus, setGpsStatus] = useState<'acquiring' | 'locked' | 'fallback'>('acquiring');
    const [cameraActive, setCameraActive] = useState(false);
    const [cameraError, setCameraError] = useState<string | null>(null);

    // Sync previewUrl when category or existingPhotoUrl prop changes
    useEffect(() => {
        setPreviewUrl(existingPhotoUrl || null);
        if (!existingPhotoUrl) {
            setSelectedFile(null);
        }
    }, [existingPhotoUrl]);

    const videoRef = useRef<HTMLVideoElement | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const fileInputRef = useRef<HTMLInputElement | null>(null);

    // Acquire GPS Coordinates
    useEffect(() => {
        if ('geolocation' in navigator) {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    const lat = pos.coords.latitude;
                    const lng = pos.coords.longitude;
                    const acc = Math.round(pos.coords.accuracy * 10) / 10;
                    setGps({
                        lat,
                        lng,
                        accuracy: acc,
                        formatted: `${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E`
                    });
                    setGpsStatus('locked');
                },
                (err) => {
                    console.warn("GPS acquire error, using fallback location:", err.message);
                    setGpsStatus('fallback');
                },
                { enableHighAccuracy: true, timeout: 8000 }
            );
        } else {
            setGpsStatus('fallback');
        }
    }, []);

    // Camera Stream handler
    const startCamera = async () => {
        setCameraError(null);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
                audio: false
            });
            streamRef.current = stream;
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                await videoRef.current.play();
            }
            setCameraActive(true);
        } catch (err: any) {
            console.error("Camera access failed:", err);
            setCameraError(err?.message || "Could not access device camera. Please upload a photo file instead.");
            setCameraActive(false);
        }
    };

    const stopCamera = () => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(t => t.stop());
            streamRef.current = null;
        }
        setCameraActive(false);
    };

    useEffect(() => {
        if (mode === 'camera') {
            startCamera();
        } else {
            stopCamera();
        }
        return () => stopCamera();
    }, [mode]);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setSelectedFile(file);
        const url = URL.createObjectURL(file);
        setPreviewUrl(url);
    };

    const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        const file = e.dataTransfer.files?.[0];
        if (!file) return;

        setSelectedFile(file);
        const url = URL.createObjectURL(file);
        setPreviewUrl(url);
    };

    const captureCameraFrame = () => {
        if (!videoRef.current) return;
        const video = videoRef.current;
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth || 1280;
        canvas.height = video.videoHeight || 720;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob((blob) => {
            if (!blob) return;
            const file = new File([blob], `capture_${Date.now()}.jpg`, { type: 'image/jpeg' });
            setSelectedFile(file);
            setPreviewUrl(URL.createObjectURL(blob));
            stopCamera();
        }, 'image/jpeg', 0.95);
    };

    const handleConfirm = () => {
        if (!selectedFile) return;
        const ts = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
        onCapture(selectedFile, gps, ts);
    };

    const handleReset = () => {
        setSelectedFile(null);
        setPreviewUrl(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        if (mode === 'camera') {
            startCamera();
        }
    };

    return (
        <div className="w-full">
            {/* GPS & Status Top Banner */}
            <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-slate-50 rounded-xl border border-slate-200 mb-4 text-xs font-mono text-slate-600">
                <div className="flex items-center gap-2">
                    <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span className="font-semibold text-slate-700">GPS Status:</span>
                    <span className="text-slate-900 font-bold">{gps.formatted}</span>
                    <span className="text-slate-500">(±{gps.accuracy}m accuracy)</span>
                </div>
                <div className="flex items-center gap-2">
                    <Badge variant={gpsStatus === 'locked' ? 'success' : 'warning'}>
                        <span className="inline-flex items-center gap-1">
                            {gpsStatus === 'locked' ? <Icons.Navigation className="w-3 h-3" /> : <Icons.MapPin className="w-3 h-3" />}
                            <span>{gpsStatus === 'locked' ? 'Live High-Accuracy GPS' : 'Standard GPS Site Lock'}</span>
                        </span>
                    </Badge>
                </div>
            </div>

            {/* Mode Switch Tabs */}
            {!previewUrl && (
                <div className="flex items-center gap-2 mb-4">
                    <button
                        type="button"
                        onClick={() => setMode('upload')}
                        className={`flex-1 py-2.5 px-4 rounded-xl font-medium text-sm border flex items-center justify-center gap-2 transition-all ${
                            mode === 'upload'
                                ? 'bg-slate-900 text-white border-slate-900 shadow-sm'
                                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                        }`}
                    >
                        <Icons.Upload className="w-4 h-4" />
                        Upload / Browse Photo
                    </button>
                    <button
                        type="button"
                        onClick={() => setMode('camera')}
                        className={`flex-1 py-2.5 px-4 rounded-xl font-medium text-sm border flex items-center justify-center gap-2 transition-all ${
                            mode === 'camera'
                                ? 'bg-slate-900 text-white border-slate-900 shadow-sm'
                                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                        }`}
                    >
                        <Icons.Camera className="w-4 h-4" />
                        Live Device Camera
                    </button>
                </div>
            )}

            {/* Capture Area */}
            <div className="relative bg-slate-950 rounded-2xl overflow-hidden border border-slate-800 aspect-[16/10] md:aspect-[16/9] flex items-center justify-center shadow-inner">
                {/* 1. Preview Captured Image */}
                {previewUrl ? (
                    <div className="relative w-full h-full flex items-center justify-center bg-black group">
                        <img
                            src={previewUrl}
                            alt="Captured preview"
                            className="w-full h-full object-contain"
                        />
                        {/* Overlay Metadata Tag */}
                        <div className="absolute bottom-4 left-4 bg-black/75 backdrop-blur-md px-3 py-2 rounded-xl text-[11px] text-white font-mono space-y-1 border border-white/10 shadow-lg">
                            <div className="flex items-center gap-1.5 text-teal-400 font-semibold">
                                <Icons.MapPin className="w-3.5 h-3.5" />
                                <span>{gps.formatted}</span>
                            </div>
                            <div className="text-slate-300 flex items-center gap-1.5">
                                <Icons.Clock className="w-3 h-3 text-slate-400" />
                                <span>{new Date().toLocaleTimeString()} | Category: {categoryName || 'Site Asset'}</span>
                            </div>
                        </div>

                        {/* Reset / Retake Button on overlay */}
                        {!isUploading && (
                            <button
                                type="button"
                                onClick={handleReset}
                                className="absolute top-4 right-4 bg-slate-900/80 hover:bg-slate-900 text-white text-xs px-3 py-1.5 rounded-lg backdrop-blur-md border border-white/20 flex items-center gap-1.5 transition-all shadow-md"
                            >
                                <Icons.RotateCcw className="w-3.5 h-3.5" />
                                Retake / Change
                            </button>
                        )}
                    </div>
                ) : mode === 'camera' ? (
                    /* 2. Live Video Stream */
                    <div className="relative w-full h-full bg-black flex items-center justify-center">
                        <video
                            ref={videoRef}
                            autoPlay
                            playsInline
                            muted
                            className="w-full h-full object-cover"
                        />
                        {/* Camera Framing Reticle */}
                        <div className="absolute inset-8 border border-white/30 rounded-2xl pointer-events-none flex flex-col justify-between p-4">
                            <div className="flex justify-between">
                                <div className="w-5 h-5 border-t-2 border-l-2 border-teal-400"></div>
                                <div className="w-5 h-5 border-t-2 border-r-2 border-teal-400"></div>
                            </div>
                            <div className="text-center text-xs font-mono text-white/80 bg-black/40 backdrop-blur-sm self-center px-3 py-1 rounded-full border border-white/10">
                                Align {categoryName || 'subject'} inside frame
                            </div>
                            <div className="flex justify-between">
                                <div className="w-5 h-5 border-b-2 border-l-2 border-teal-400"></div>
                                <div className="w-5 h-5 border-b-2 border-r-2 border-teal-400"></div>
                            </div>
                        </div>

                        {cameraError ? (
                            <div className="absolute inset-0 bg-slate-900/95 flex flex-col items-center justify-center p-6 text-center">
                                <Icons.AlertTriangle className="w-10 h-10 text-amber-400 mb-3" />
                                <p className="text-sm font-semibold text-white mb-2">Camera Unavailable</p>
                                <p className="text-xs text-slate-400 mb-4 max-w-xs">{cameraError}</p>
                                <button
                                    type="button"
                                    onClick={() => setMode('upload')}
                                    className="bg-teal-600 hover:bg-teal-500 text-white text-xs px-4 py-2 rounded-xl font-medium transition-colors"
                                >
                                    Switch to File Upload
                                </button>
                            </div>
                        ) : (
                            /* Shutter Button */
                            <button
                                type="button"
                                onClick={captureCameraFrame}
                                className="absolute bottom-6 left-1/2 -translate-x-1/2 w-16 h-16 rounded-full bg-white/20 p-1 flex items-center justify-center backdrop-blur-md hover:scale-105 active:scale-95 transition-all shadow-2xl"
                            >
                                <div className="w-12 h-12 rounded-full bg-white border-2 border-slate-900 flex items-center justify-center shadow-md">
                                    <Icons.Camera className="w-5 h-5 text-slate-900" />
                                </div>
                            </button>
                        )}
                    </div>
                ) : (
                    /* 3. Drag and Drop / File Input */
                    <div
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={handleDrop}
                        onClick={() => fileInputRef.current?.click()}
                        className="w-full h-full flex flex-col items-center justify-center p-6 text-center cursor-pointer hover:bg-slate-900/80 transition-colors group"
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/jpeg,image/png,image/webp,image/heic,image/*"
                            capture="environment"
                            onChange={handleFileChange}
                            className="hidden"
                        />
                        <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-700 flex items-center justify-center mb-4 group-hover:scale-110 group-hover:border-teal-500 transition-all text-slate-400 group-hover:text-teal-400 shadow-lg">
                            <Icons.Upload className="w-8 h-8" />
                        </div>
                        <h4 className="font-semibold text-slate-200 text-sm mb-1">
                            Click or Drag photo here to upload
                        </h4>
                        <p className="text-xs text-slate-400 max-w-sm">
                            Supports high-res JPG, PNG, WebP photos. Live GPS & EXIF will be extracted automatically.
                        </p>
                    </div>
                )}
            </div>

            {/* Action Bar (When newly captured image is ready for upload) */}
            {previewUrl && selectedFile && (
                <div className="mt-4 flex items-center justify-between gap-4 p-4 bg-teal-950/20 border border-teal-800/30 rounded-2xl animate-fadeIn">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-teal-600/20 text-teal-400 flex items-center justify-center border border-teal-500/30">
                            <Icons.Image className="w-5 h-5" />
                        </div>
                        <div>
                            <p className="text-sm font-bold text-slate-800">
                                {selectedFile?.name || 'Captured Photo'}
                            </p>
                            <p className="text-xs text-slate-500">
                                Size: {Math.round(selectedFile.size / 1024)} KB • Ready for Gemini Vision Analysis
                            </p>
                        </div>
                    </div>

                    <button
                        type="button"
                        onClick={handleConfirm}
                        disabled={isUploading}
                        className={`px-6 py-3 rounded-xl font-bold text-sm shadow-md flex items-center gap-2 transition-all ${
                            isUploading
                                ? 'bg-teal-700 text-white opacity-80 cursor-wait'
                                : 'bg-teal-600 hover:bg-teal-500 text-white hover:shadow-teal-500/25'
                        }`}
                    >
                        {isUploading ? (
                            <>
                                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                                Running Vision AI & Fraud Check...
                            </>
                        ) : (
                            <>
                                <Icons.CheckCircle className="w-4 h-4" />
                                Run AI Vision Analysis
                            </>
                        )}
                    </button>
                </div>
            )}
        </div>
    );
}
