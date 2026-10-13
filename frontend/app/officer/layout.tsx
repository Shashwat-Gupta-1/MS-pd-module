'use client';

import React from 'react';
import { Icons } from '../../components/ui/Icons';
import { useCaseContext } from '../../lib/CaseContext';
import PersistentRecordingBar from '../../components/PersistentRecordingBar';

export default function CaseLayout({ children }: { children: React.ReactNode }) {
    const { currentRoute, applicationId, profileData, navigate } = useCaseContext();

    const activeAppId = applicationId || 'APP-2026-9823';
    const borrowerName = 
        profileData.borrower?.fields?.fullName?.value || 
        profileData.borrower?.fields?.name?.value || 
        'Active Applicant';
    const empType = profileData.business?.fields?.employmentType?.value || 'Salaried';
    const subProfile = 
        profileData.business?.fields?.employerType?.value || 
        profileData.business?.fields?.businessCategory?.value || 
        '';

    const stepsConfig = [
        { pathKey: 'new-case', id: '/officer/new-case', label: 'Profile Verification' },
        { pathKey: 'questionnaire', id: `/officer/cases/${activeAppId}/questionnaire`, label: 'PD Recording' },
        { pathKey: 'gap-questions', id: `/officer/cases/${activeAppId}/gap-questions`, label: 'AI Analysis & Gaps' },
        { pathKey: 'reconfirm', id: `/officer/cases/${activeAppId}/reconfirm`, label: 'Reconfirmations' },
        { pathKey: 'photos', id: `/officer/cases/${activeAppId}/photos`, label: 'Required Photos' },
        { pathKey: 'review', id: `/officer/cases/${activeAppId}/review`, label: 'Final Review & Submit' }
    ];

    const currentIndex = stepsConfig.findIndex(s => 
        currentRoute === s.id || (s.pathKey !== 'new-case' && currentRoute.includes(`/${s.pathKey}`))
    );

    return (
        <div className="min-h-screen flex flex-col md:flex-row bg-slate-50">
            <aside className="md:w-72 bg-slate-900 text-white flex-shrink-0 shadow-xl md:sticky md:top-0 md:h-screen overflow-y-auto z-20">
                <div className="p-6 border-b border-slate-800">
                    <h1 className="text-xl font-bold tracking-tight mb-4 text-teal-400">MSFincap <span className="text-white">PD Assist</span></h1>
                    <div className="bg-slate-800 rounded-lg p-3">
                        <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Current Case</p>
                        <p className="font-semibold truncate text-white">{borrowerName}</p>
                        <p className="text-xs text-teal-300 truncate mt-0.5">{empType}{subProfile ? ` • ${subProfile}` : ''}</p>
                        <p className="text-[10px] text-slate-400 font-mono mt-1">{activeAppId}</p>
                    </div>
                </div>
                <div className="p-6">
                    <nav className="space-y-4 md:space-y-6 flex flex-row md:flex-col overflow-x-auto md:overflow-visible pb-4 md:pb-0">
                        {stepsConfig.map((s, idx) => {
                            const isCurrent = currentRoute === s.id || (s.pathKey !== 'new-case' && currentRoute.includes(`/${s.pathKey}`));
                            const isPast = currentIndex > idx;
                            return (
                                <button 
                                    key={s.id} 
                                    onClick={() => navigate(s.id)}
                                    className="flex items-center md:items-start flex-shrink-0 md:w-full mr-6 md:mr-0 text-left cursor-pointer group"
                                >
                                    <div className="flex flex-col items-center">
                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm z-10 transition-colors ${isCurrent ? 'bg-teal-500 text-white ring-4 ring-teal-500/30' : isPast ? 'bg-teal-700 text-white' : 'bg-slate-800 text-slate-500 group-hover:bg-slate-700'}`}>
                                            {isPast ? <Icons.CheckCircle className="w-5 h-5" /> : idx + 1}
                                        </div>
                                        {idx < stepsConfig.length - 1 && <div className={`hidden md:block w-0.5 h-10 -my-1 ${isPast ? 'bg-teal-700' : 'bg-slate-800'}`}></div>}
                                    </div>
                                    <div className="ml-3 hidden md:block mt-1.5"><p className={`font-medium ${isCurrent ? 'text-white' : 'text-slate-400 group-hover:text-slate-200'}`}>{s.label}</p></div>
                                </button>
                            );
                        })}
                    </nav>
                </div>
            </aside>
            <main className="flex-1 overflow-y-auto relative p-4 md:p-8">
                <PersistentRecordingBar />
                {children}
            </main>
        </div>
    );
}
