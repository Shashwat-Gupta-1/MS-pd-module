import React from 'react';
import { Icons } from './ui/Icons';

export default function CameraCapture({ onCapture }: { onCapture: (url: string, gps: string, ts: string) => void }) {
    return (
        <div className="bg-slate-900 rounded-xl aspect-video relative flex flex-col items-center justify-center text-slate-400 border-2 border-dashed border-slate-700 overflow-hidden group">
            <Icons.Camera className="w-12 h-12 mb-4 group-hover:scale-110 transition-transform text-slate-500" />
            <p className="text-sm">Mock Camera View</p>
            <button
                onClick={() => onCapture("mock-url.jpg", "26.9124° N, 75.7873° E", new Date().toLocaleString())}
                className="absolute bottom-4 bg-teal-600 hover:bg-teal-500 text-white px-6 py-2 rounded-full font-medium shadow-lg transition-colors"
            >
                Capture Photo
            </button>
        </div>
    );
}
