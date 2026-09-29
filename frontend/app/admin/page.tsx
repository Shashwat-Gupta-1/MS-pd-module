'use client';

import React from 'react';
import { Card } from '../../components/ui/primitives';
import { Icons } from '../../components/ui/Icons';
import AnalyticsChart from '../../components/AnalyticsChart';
import { useCaseContext } from '../../lib/CaseContext';

export default function AdminDashboard() {
    const { navigate } = useCaseContext();
    return (
        <div className="max-w-5xl mx-auto animate-fadeIn py-8">
            <div className="flex justify-between items-center mb-8">
                <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
                    <Icons.BarChart className="w-8 h-8 text-teal-600" /> PD Quality Analytics
                </h1>
                <button onClick={() => navigate('/officer/new-case')} className="bg-slate-900 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-slate-800 transition-colors">
                    Back to Field App
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <Card className="p-6">
                    <h3 className="text-slate-500 text-sm font-semibold uppercase tracking-wider mb-2">Avg Officer Score</h3>
                    <div className="text-4xl font-bold text-slate-900">84.2</div>
                    <p className="text-emerald-600 text-sm font-medium mt-2 flex items-center gap-1"><Icons.ChevronUp className="w-4 h-4"/> 2.1 from last week</p>
                </Card>
                <Card className="p-6">
                    <h3 className="text-slate-500 text-sm font-semibold uppercase tracking-wider mb-2">Avg Consistency Risk</h3>
                    <div className="text-4xl font-bold text-amber-600">Medium</div>
                    <p className="text-slate-600 text-sm font-medium mt-2">1.2 flags per case</p>
                </Card>
                <Card className="p-6">
                    <h3 className="text-slate-500 text-sm font-semibold uppercase tracking-wider mb-2">Completion Rate</h3>
                    <div className="text-4xl font-bold text-slate-900">92%</div>
                    <p className="text-emerald-600 text-sm font-medium mt-2 flex items-center gap-1"><Icons.ChevronUp className="w-4 h-4"/> 5% from last week</p>
                </Card>
            </div>

            <AnalyticsChart />
        </div>
    );
}
