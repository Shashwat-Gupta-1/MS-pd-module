'use client';

import React from 'react';
import { Icons } from '../../components/ui/Icons';
import { useCaseContext } from '../../lib/CaseContext';
import { mockCaseDetails } from '../../lib/mockData';

export default function CaseLayout({ children }: { children: React.ReactNode }) {
    const { currentRoute, profileData, caseId, navigate } = useCaseContext();
    const activeCaseId = caseId || mockCaseDetails.id;
    const borrowerName = profileData.borrower?.fields?.name?.value || mockCaseDetails.borrowerName;
    const businessCategory = profileData.business?.fields?.category?.value || mockCaseDetails.product;

    const stepsConfig = [
        { id: '/officer/new-case', label: 'Profile Verification' },
        { id: `/officer/cases/${activeCaseId}/questionnaire`, label: 'PD Recording' },
        { id: `/officer/cases/${activeCaseId}/gap-questions`, label: 'AI Analysis & Gaps' },
        { id: `/officer/cases/${activeCaseId}/reconfirm`, label: 'Reconfirmations' },
        { id: `/officer/cases/${activeCaseId}/photos`, label: 'Required Photos' },
        { id: `/officer/cases/${activeCaseId}/review`, label: 'Final Review & Submit' }
    ];

    const currentIndex = stepsConfig.findIndex(s => currentRoute === s.id || currentRoute.endsWith(s.id.split('/').pop()!));

    return (
        <div className="min-h-screen flex flex-col md:flex-row bg-slate-50">
            <aside className="md:w-72 bg-slate-900 text-white flex-shrink-0 shadow-xl md:sticky md:top-0 md:h-screen overflow-y-auto z-20">
                <div className="p-6 border-b border-slate-800">
                    <h1 className="text-xl font-bold tracking-tight mb-4 text-teal-400">MSFincap <span className="text-white">PD Assist</span></h1>
                    <div className="bg-slate-800 rounded-lg p-3">
                        <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Current Case</p>
                        <p className="font-semibold truncate text-white" suppressHydrationWarning>{borrowerName}</p>
                        <p className="text-xs text-slate-300 truncate mt-1" suppressHydrationWarning>{businessCategory}</p>
                        <p className="text-[10px] text-teal-400 font-mono mt-2" suppressHydrationWarning>{activeCaseId}</p>
                    </div>
                </div>
                <div className="p-6">
                    <nav className="space-y-3 md:space-y-4 flex flex-row md:flex-col overflow-x-auto md:overflow-visible pb-4 md:pb-0">
                        {stepsConfig.map((s, idx) => {
                            const isCurrent = currentRoute === s.id;
                            const isPast = currentIndex > idx;
                            return (
                                <button
                                    key={s.id}
                                    type="button"
                                    onClick={() => navigate(s.id)}
                                    className={`flex items-center md:items-start flex-shrink-0 md:w-full mr-4 md:mr-0 text-left p-2 rounded-xl transition-all cursor-pointer group ${
                                        isCurrent ? 'bg-slate-800/80 shadow-sm ring-1 ring-teal-500/30' : 'hover:bg-slate-800/40'
                                    }`}
                                >
                                    <div className="flex flex-col items-center">
                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs z-10 transition-colors ${
                                            isCurrent
                                                ? 'bg-teal-500 text-white ring-4 ring-teal-500/30'
                                                : isPast
                                                ? 'bg-teal-700 text-white'
                                                : 'bg-slate-800 text-slate-400 group-hover:bg-slate-700 group-hover:text-slate-200'
                                        }`}>
                                            {isPast ? <Icons.CheckCircle className="w-4 h-4" /> : idx + 1}
                                        </div>
                                        {idx < stepsConfig.length - 1 && (
                                            <div className={`hidden md:block w-0.5 h-6 -my-0.5 ${isPast ? 'bg-teal-700' : 'bg-slate-800'}`}></div>
                                        )}
                                    </div>
                                    <div className="ml-3 hidden md:block">
                                        <p className={`font-medium text-xs transition-colors ${
                                            isCurrent ? 'text-white font-bold' : isPast ? 'text-teal-300' : 'text-slate-400 group-hover:text-slate-200'
                                        }`}>
                                            {s.label}
                                        </p>
                                    </div>
                                </button>
                            );
                        })}
                    </nav>
                </div>
            </aside>
            <main className="flex-1 overflow-y-auto relative p-4 md:p-8">
                {children}
            </main>
        </div>
    );
}
