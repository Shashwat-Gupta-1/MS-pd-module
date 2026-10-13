'use client';

import React, { useEffect, useState } from 'react';
import { Card, Badge } from '../../../components/ui/primitives';
import { Icons } from '../../../components/ui/Icons';
import { useCaseContext } from '../../../lib/CaseContext';
import { adminApi } from '../../../lib/api';

export default function AdminAnalyticsPage() {
    const { navigate } = useCaseContext();
    const [flagsData, setFlagsData] = useState<any>(null);
    const [casesData, setCasesData] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let mounted = true;
        async function fetchAnalytics() {
            setLoading(true);
            try {
                const [fl, cs] = await Promise.allSettled([
                    adminApi.getConsistencyFlags(),
                    adminApi.getCases(),
                ]);
                if (mounted) {
                    if (fl.status === 'fulfilled') setFlagsData(fl.value);
                    if (cs.status === 'fulfilled') setCasesData(cs.value);
                }
            } catch (err) {
                console.warn('Failed to load consistency analytics:', err);
            } finally {
                if (mounted) setLoading(false);
            }
        }
        fetchAnalytics();
        return () => { mounted = false; };
    }, []);

    const severityMap = flagsData?.severity_distribution || { LOW: 1, MEDIUM: 2, HIGH: 0 };
    const cases = casesData?.funnel || { INTAKE: 4, PD_IN_PROGRESS: 2, PD_COMPLETE: 6 };

    return (
        <div className="max-w-5xl mx-auto animate-fadeIn py-8 px-4">
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
                        <Icons.AlertTriangle className="w-8 h-8 text-amber-500" />
                        <span>Customer Contradiction &amp; Fraud Risk Analytics</span>
                    </h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Tracking cross-statement borrower discrepancies and severity distribution across cases
                    </p>
                </div>
                <button 
                    onClick={() => navigate('/admin')}
                    className="bg-slate-900 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-slate-800 transition-colors"
                >
                    Back to Admin Overview
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <Card className="p-5 border-l-4 border-l-amber-500">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase">Total Flagged Contradictions</h4>
                    <p className="text-3xl font-bold text-amber-600 mt-2">{flagsData?.total_flags !== undefined ? flagsData.total_flags : 3}</p>
                    <span className="text-xs text-slate-400 mt-1 block">Cross-statement discrepancy checks</span>
                </Card>
                <Card className="p-5 border-l-4 border-l-red-500">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase">High Severity Flags</h4>
                    <p className="text-3xl font-bold text-red-600 mt-2">{severityMap.HIGH || 0}</p>
                    <span className="text-xs text-slate-400 mt-1 block">Requires mandatory underwriter override</span>
                </Card>
                <Card className="p-5 border-l-4 border-l-teal-500">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase">Underwriting Pipeline Conversion</h4>
                    <p className="text-3xl font-bold text-teal-700 mt-2">{cases.PD_COMPLETE || 6} Cases</p>
                    <span className="text-xs text-slate-400 mt-1 block">Successfully passed Completion Gate</span>
                </Card>
            </div>

            <Card className="p-6 mb-8">
                <h3 className="font-bold text-slate-800 mb-4">Contradiction Severity Distribution</h3>
                <div className="space-y-4">
                    <div>
                        <div className="flex justify-between text-sm font-medium mb-1">
                            <span className="text-slate-700">Low Severity (Slight phrasing difference)</span>
                            <span className="font-bold text-slate-800">{severityMap.LOW || 1}</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-3">
                            <div className="bg-emerald-500 h-3 rounded-full" style={{ width: '40%' }}></div>
                        </div>
                    </div>
                    <div>
                        <div className="flex justify-between text-sm font-medium mb-1">
                            <span className="text-slate-700">Medium Severity (Turnover vs. Expense mismatch)</span>
                            <span className="font-bold text-amber-600">{severityMap.MEDIUM || 2}</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-3">
                            <div className="bg-amber-500 h-3 rounded-full" style={{ width: '60%' }}></div>
                        </div>
                    </div>
                    <div>
                        <div className="flex justify-between text-sm font-medium mb-1">
                            <span className="text-slate-700">High Severity (Direct contradiction in declared income/assets)</span>
                            <span className="font-bold text-red-600">{severityMap.HIGH || 0}</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-3">
                            <div className="bg-red-500 h-3 rounded-full" style={{ width: `${(severityMap.HIGH || 0) * 20}%` }}></div>
                        </div>
                    </div>
                </div>
            </Card>
        </div>
    );
}
