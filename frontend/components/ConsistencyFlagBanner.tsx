'use client';

import React, { useState } from 'react';
import { Card, Badge, CircularGauge } from './ui/primitives';
import { Icons } from './ui/Icons';
import { useCaseContext } from '../lib/CaseContext';

export default function ConsistencyFlagBanner() {
    const { inconsistencies, setInconsistencies } = useCaseContext();
    const [resolutionNotes, setResolutionNotes] = useState<Record<string, string>>({});

    const handleResolve = (id: string) => {
        if (!resolutionNotes[id]) return;
        setInconsistencies(prev => prev.map(inc => inc.id === id ? { ...inc, status: 'resolved', note: resolutionNotes[id] } : inc));
    };

    const openIncCount = inconsistencies.filter(i => i.status === 'open').length;

    return (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <Card className="p-6 col-span-1 flex flex-col items-center justify-center text-center">
                <CircularGauge value={65} label="Consistency" size={140} colorClass="text-amber-500" />
                <p className="text-sm font-medium text-slate-600 mt-4">Status: <span className="text-amber-600 font-bold">Medium Risk</span></p>
            </Card>
            <div className="col-span-3">
                <Card className="overflow-hidden h-full">
                    <div className="p-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
                        <h3 className="font-semibold text-slate-800">AI Flagged Inconsistencies</h3>
                        <Badge variant={openIncCount > 0 ? 'warning' : 'success'}>{openIncCount} Actionable Items</Badge>
                    </div>
                    <div className="divide-y divide-slate-100">
                        {inconsistencies.map(inc => (
                            <div key={inc.id} className={`p-4 transition-colors ${inc.status === 'resolved' ? 'bg-slate-50 opacity-70' : 'bg-white'}`}>
                                <div className="flex justify-between items-start mb-2">
                                    <div className="flex items-center gap-2">
                                        <span className="font-semibold text-slate-800">{inc.field}</span>
                                        <Badge variant={inc.severity === 'critical' ? 'critical' : 'warning'}>{inc.severity === 'critical' ? 'High' : 'Medium'} Severity</Badge>
                                    </div>
                                    {inc.status === 'resolved' && <Badge variant="success"><Icons.CheckCircle className="w-3 h-3 inline mr-1"/>Resolved</Badge>}
                                </div>
                                <div className="grid grid-cols-2 gap-4 mt-3 bg-slate-50 p-3 rounded-lg border border-slate-100 text-sm">
                                    <div><span className="text-slate-500 block mb-1 text-xs uppercase">Earlier:</span> "{inc.val1}"</div>
                                    <div><span className="text-slate-500 block mb-1 text-xs uppercase">Later:</span> "{inc.val2}"</div>
                                </div>
                                {inc.status === 'open' ? (
                                    <div className="mt-4 flex gap-2">
                                        <input type="text" value={resolutionNotes[inc.id] || ''} onChange={(e) => setResolutionNotes(p => ({...p, [inc.id]: e.target.value}))} placeholder="Add resolution note..." className="flex-1 text-sm px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 outline-none" />
                                        <button onClick={() => handleResolve(inc.id)} className="px-4 py-2 bg-teal-50 text-teal-700 font-medium text-sm rounded-lg hover:bg-teal-100 border border-teal-200 transition-colors">Mark Resolved</button>
                                    </div>
                                ) : (
                                    <p className="mt-3 text-sm text-slate-600 italic">Resolution: {inc.note}</p>
                                )}
                            </div>
                        ))}
                    </div>
                </Card>
            </div>
        </div>
    );
}
