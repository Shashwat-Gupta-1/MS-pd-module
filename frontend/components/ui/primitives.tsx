import React from 'react';
import type { StatusLevel } from '../../lib/types';

export const Card = ({ children, className = "" }: { children: React.ReactNode, className?: string }) =>
    <div className={`bg-white rounded-xl shadow-sm border border-slate-200 ${className}`}>{children}</div>;

export const Badge = ({ children, variant = 'default', className = "" }: { children: React.ReactNode, variant?: StatusLevel | 'primary', className?: string }) => {
    const variants = {
        default: 'bg-slate-100 text-slate-700',
        success: 'bg-emerald-100 text-emerald-700',
        warning: 'bg-amber-100 text-amber-800',
        critical: 'bg-red-100 text-red-700',
        primary: 'bg-teal-50 text-teal-700'
    };
    return (
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${variants[variant]} ${className}`}>
            {children}
        </span>
    );
};

export const CircularGauge = ({ value, label, size = 120, colorClass = "text-teal-600" }: { value: number, label?: string, size?: number, colorClass?: string }) => {
    const strokeWidth = 10;
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (value / 100) * circumference;

    return (
        <div className="flex flex-col items-center justify-center relative" style={{ width: size, height: size }}>
            <svg className="transform -rotate-90 w-full h-full">
                <circle cx={size/2} cy={size/2} r={radius} stroke="currentColor" strokeWidth={strokeWidth} fill="transparent" className="text-slate-200" />
                <circle cx={size/2} cy={size/2} r={radius} stroke="currentColor" strokeWidth={strokeWidth} fill="transparent" strokeDasharray={circumference} strokeDashoffset={offset} className={`transition-all duration-1000 ease-out ${colorClass}`} />
            </svg>
            <div className="absolute flex flex-col items-center">
                <span className="text-3xl font-bold text-slate-800">{value}</span>
                {label && <span className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</span>}
            </div>
        </div>
    );
};
