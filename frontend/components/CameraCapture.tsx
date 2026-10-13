'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Icons } from './ui/Icons';

interface CameraCaptureProps {
    onCapture: (
        file: File,
        previewUrl: string,
        gpsString: string,
        timestamp: string,
        lat?: number,
        lng?: number,
        accuracy?: number
    ) => void | Promise<void>;
    categoryName?: string;
}

export default function CameraCapture({ onCapture, categoryName }: CameraCaptureProps) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [isStreaming, setIsStreaming] = useState<boolean>(false);
    const [cameraError, setCameraError] = useState<string | null>(null);
    const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment');
    const [capturedPreview, setCapturedPreview] = useState<string | null>(null);
    const [capturedFile, setCapturedFile] = useState<File | null>(null);
    const [isCapturing, setIsCapturing] = useState<boolean>(false);

    // Live Geolocation state
    const [gpsCoords, setGpsCoords] = useState<{ lat: number; lng: number; accuracy: number } | null>(null);
    const [gpsStatus, setGpsStatus] = useState<'acquiring' | 'locked' | 'fallback'>('acquiring');

    // 1. Fetch live geolocation on mount
    useEffect(() => {
        if (typeof window !== 'undefined' && 'geolocation' in navigator) {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    setGpsCoords({
                        lat: Number(pos.coords.latitude.toFixed(6)),
                        lng: Number(pos.coords.longitude.toFixed(6)),
                        accuracy: Number(pos.coords.accuracy.toFixed(1)),
                    });
                    setGpsStatus('locked');
                },
                (err) => {
                    console.warn('Geolocation warning (using default site coordinates):', err.message);
                    setGpsCoords({ lat: 26.9124, lng: 75.7873, accuracy: 15.0 });
                    setGpsStatus('fallback');
                },
                { enableHighAccuracy: true, timeout: 8000, maximumAge: 10000 }
            );
        } else {
            setGpsCoords({ lat: 26.9124, lng: 75.7873, accuracy: 20.0 });
            setGpsStatus('fallback');
        }
    }, []);

    // 2. Start Video Stream
    const startCamera = useCallback(async () => {
        setCameraError(null);
        if (typeof window === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
            setCameraError('Camera API is not supported in this browser environment. Please use direct photo upload below.');
            return;
        }

        try {
            // Stop existing tracks if any
            if (videoRef.current && videoRef.current.srcObject) {
                const stream = videoRef.current.srcObject as MediaStream;
                stream.getTracks().forEach((track) => track.stop());
            }

            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: { ideal: facingMode },
                    width: { ideal: 1920 },
                    height: { ideal: 1080 },
                },
                audio: false,
            });

            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                await videoRef.current.play();
                setIsStreaming(true);
            }
        } catch (err: any) {
            console.warn('Webcam stream error:', err);
            setIsStreaming(false);
            if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                setCameraError('Camera permission was denied. Please allow camera access in browser settings or upload a photo directly.');
            } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
                setCameraError('No camera found on this device. Please upload an image file using the button below.');
            } else {
                setCameraError('Unable to start live camera viewfinder. Please use the camera upload button below.');
            }
        }
    }, [facingMode]);

    // Initialize or switch camera
    useEffect(() => {
        if (!capturedPreview) {
            startCamera();
        }
        return () => {
            if (videoRef.current && videoRef.current.srcObject) {
                const stream = videoRef.current.srcObject as MediaStream;
                stream.getTracks().forEach((track) => track.stop());
            }
        };
    }, [startCamera, capturedPreview]);

    // 3. Shutter Snapshot
    const handleSnap = async () => {
        if (!videoRef.current || !canvasRef.current) return;
        setIsCapturing(true);

        const video = videoRef.current;
        const canvas = canvasRef.current;
        const width = video.videoWidth || 1280;
        const height = video.videoHeight || 720;

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
            setIsCapturing(false);
            return;
        }

        // Draw video frame to canvas
        ctx.drawImage(video, 0, 0, width, height);

        // Convert to Blob
        canvas.toBlob(
            (blob) => {
                if (!blob) {
                    setIsCapturing(false);
                    return;
                }
                const filename = `${(categoryName || 'photo').toLowerCase()}_${Date.now()}.jpg`;
                const file = new File([blob], filename, { type: 'image/jpeg' });
                const previewUrl = URL.createObjectURL(blob);

                setCapturedFile(file);
                setCapturedPreview(previewUrl);
                setIsCapturing(false);

                // Stop live stream tracks
                if (videoRef.current && videoRef.current.srcObject) {
                    const stream = videoRef.current.srcObject as MediaStream;
                    stream.getTracks().forEach((track) => track.stop());
                    setIsStreaming(false);
                }
            },
            'image/jpeg',
            0.92
        );
    };

    // 4. File Input Fallback (Direct camera or file upload)
    const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const previewUrl = URL.createObjectURL(file);
        setCapturedFile(file);
        setCapturedPreview(previewUrl);

        // Stop stream if active
        if (videoRef.current && videoRef.current.srcObject) {
            const stream = videoRef.current.srcObject as MediaStream;
            stream.getTracks().forEach((track) => track.stop());
            setIsStreaming(false);
        }
    };

    // 5. Retake Photo
    const handleRetake = () => {
        if (capturedPreview) {
            URL.revokeObjectURL(capturedPreview);
        }
        setCapturedPreview(null);
        setCapturedFile(null);
        startCamera();
    };

    // 6. Confirm & Submit Photo
    const handleConfirm = () => {
        if (!capturedFile || !capturedPreview) return;
        const lat = gpsCoords?.lat || 26.9124;
        const lng = gpsCoords?.lng || 75.7873;
        const acc = gpsCoords?.accuracy || 10.0;
        const gpsString = `${lat}° N, ${lng}° E (±${Math.round(acc)}m)`;
        const timestamp = new Date().toISOString();

        onCapture(capturedFile, capturedPreview, gpsString, timestamp, lat, lng, acc);
    };

    // Toggle Front/Back Camera
    const toggleFacingMode = () => {
        setFacingMode((prev) => (prev === 'environment' ? 'user' : 'environment'));
    };

    return (
        <div className="relative w-full rounded-2xl overflow-hidden bg-slate-950 border border-slate-800 shadow-xl text-white">
            {/* Viewfinder Container */}
            <div className="relative aspect-video sm:aspect-[4/3] md:aspect-video w-full flex items-center justify-center bg-black overflow-hidden">
                {/* 1. Captured Preview State */}
                {capturedPreview ? (
                    <div className="relative w-full h-full flex items-center justify-center bg-black">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                            src={capturedPreview}
                            alt="Captured Site Photo"
                            className="max-h-full max-w-full object-contain"
                        />
                        <div className="absolute top-4 left-4 bg-emerald-950/80 border border-emerald-500/50 backdrop-blur-md px-3 py-1.5 rounded-full flex items-center gap-2 text-xs font-semibold text-emerald-300">
                            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                            <span>Photo Captured &amp; Ready</span>
                        </div>
                    </div>
                ) : (
                    /* 2. Live Video Stream View */
                    <>
                        <video
                            ref={videoRef}
                            playsInline
                            muted
                            autoPlay
                            className={`w-full h-full object-cover transition-opacity duration-300 ${
                                isStreaming ? 'opacity-100' : 'opacity-0'
                            }`}
                        />

                        {/* Viewfinder Reticle / Framing Grid */}
                        {isStreaming && (
                            <div className="absolute inset-0 pointer-events-none flex flex-col justify-between p-6">
                                <div className="flex justify-between items-start">
                                    <div className="w-8 h-8 border-t-2 border-l-2 border-teal-400 rounded-tl-lg"></div>
                                    <div className="w-8 h-8 border-t-2 border-r-2 border-teal-400 rounded-tr-lg"></div>
                                </div>
                                <div className="flex justify-center items-center">
                                    <div className="w-12 h-12 border border-white/30 rounded-full flex items-center justify-center">
                                        <div className="w-1.5 h-1.5 bg-teal-400 rounded-full"></div>
                                    </div>
                                </div>
                                <div className="flex justify-between items-end">
                                    <div className="w-8 h-8 border-b-2 border-l-2 border-teal-400 rounded-bl-lg"></div>
                                    <div className="w-8 h-8 border-b-2 border-r-2 border-teal-400 rounded-br-lg"></div>
                                </div>
                            </div>
                        )}

                        {/* Loading / Camera Error Fallback */}
                        {!isStreaming && (
                            <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center bg-slate-900/90 z-10">
                                {cameraError ? (
                                    <>
                                        <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mb-3 text-amber-400">
                                            <Icons.Camera className="w-7 h-7" />
                                        </div>
                                        <h4 className="text-base font-bold text-slate-100 mb-1">Live Camera Standby</h4>
                                        <p className="text-xs text-slate-400 max-w-sm mb-4 leading-relaxed">
                                            {cameraError}
                                        </p>
                                        <button
                                            type="button"
                                            onClick={() => fileInputRef.current?.click()}
                                            className="bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold px-5 py-2.5 rounded-xl shadow-lg transition flex items-center gap-2"
                                        >
                                            <Icons.Upload className="w-4 h-4" />
                                            <span>Take Photo / Choose File</span>
                                        </button>
                                    </>
                                ) : (
                                    <div className="flex flex-col items-center gap-3">
                                        <div className="w-10 h-10 border-3 border-teal-500 border-t-transparent rounded-full animate-spin"></div>
                                        <p className="text-xs text-slate-300 font-medium">Initializing camera viewfinder...</p>
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                )}

                {/* Live GPS Coordinates Tag on Viewfinder */}
                <div className="absolute top-4 right-4 bg-slate-950/75 border border-slate-700/60 backdrop-blur-md px-3 py-1.5 rounded-xl flex items-center gap-2 text-xs font-mono text-slate-200 z-20">
                    <span
                        className={`w-2 h-2 rounded-full ${
                            gpsStatus === 'locked' ? 'bg-emerald-400' : 'bg-amber-400'
                        }`}
                    ></span>
                    <span>
                        {gpsCoords
                            ? `${gpsCoords.lat.toFixed(4)}°, ${gpsCoords.lng.toFixed(4)}° (±${Math.round(
                                  gpsCoords.accuracy
                              )}m)`
                            : 'Acquiring GPS...'}
                    </span>
                </div>

                {/* Switch Camera Button (Front/Rear) */}
                {isStreaming && !capturedPreview && (
                    <button
                        type="button"
                        onClick={toggleFacingMode}
                        title="Switch Camera"
                        className="absolute top-4 left-4 bg-slate-950/75 hover:bg-slate-800 border border-slate-700/60 backdrop-blur-md p-2 rounded-xl text-slate-300 hover:text-white transition z-20"
                    >
                        <Icons.RotateCcw className="w-4 h-4" />
                    </button>
                )}
            </div>

            {/* Hidden canvas for snapshot rasterization */}
            <canvas ref={canvasRef} className="hidden" />

            {/* Hidden file input for native camera / gallery upload fallback */}
            <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleFileInput}
                className="hidden"
            />

            {/* Viewfinder Controls Bar */}
            <div className="p-4 bg-slate-900 border-t border-slate-800 flex items-center justify-between gap-4">
                {capturedPreview ? (
                    /* Captured Controls: Retake or Confirm */
                    <div className="w-full flex items-center justify-between gap-4">
                        <button
                            type="button"
                            onClick={handleRetake}
                            className="px-4 py-2.5 rounded-xl border border-slate-700 hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-bold transition flex items-center gap-2"
                        >
                            <Icons.RotateCcw className="w-4 h-4" />
                            <span>Retake Photo</span>
                        </button>

                        <div className="text-center text-xs text-slate-400 hidden sm:block">
                            Review clarity before upload
                        </div>

                        <button
                            type="button"
                            onClick={handleConfirm}
                            className="px-6 py-2.5 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 text-xs font-black shadow-lg transition flex items-center gap-2"
                        >
                            <Icons.CheckCircle className="w-4 h-4" />
                            <span>Confirm &amp; Save Photo</span>
                        </button>
                    </div>
                ) : (
                    /* Live View Controls: Shutter button and Upload Fallback */
                    <div className="w-full flex items-center justify-between gap-4">
                        <button
                            type="button"
                            onClick={() => fileInputRef.current?.click()}
                            className="px-3.5 py-2 rounded-xl border border-slate-700 hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-semibold transition flex items-center gap-2"
                            title="Upload existing image or use native device camera"
                        >
                            <Icons.Upload className="w-4 h-4" />
                            <span className="hidden sm:inline">Upload Photo</span>
                        </button>

                        {/* Center Shutter Button */}
                        <div className="flex items-center gap-3">
                            <button
                                type="button"
                                onClick={handleSnap}
                                disabled={!isStreaming || isCapturing}
                                className={`w-16 h-16 rounded-full border-4 border-white/80 p-1 flex items-center justify-center transition-all ${
                                    isStreaming
                                        ? 'hover:scale-105 active:scale-95 bg-teal-600 hover:bg-teal-500 text-white shadow-teal-500/50 shadow-lg cursor-pointer'
                                        : 'bg-slate-700 opacity-50 cursor-not-allowed'
                                }`}
                                aria-label="Take Photo"
                            >
                                <div className="w-11 h-11 rounded-full bg-white flex items-center justify-center">
                                    <Icons.Camera className="w-5 h-5 text-slate-900" />
                                </div>
                            </button>
                        </div>

                        <div className="text-right text-xs text-slate-400">
                            <span className="hidden sm:inline">Category: </span>
                            <span className="font-bold text-teal-400">{categoryName || 'Site Photo'}</span>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
