'use client';

import React from 'react';
import { Card } from './ui/primitives';
import { Icons } from './ui/Icons';
import { useCaseContext } from '../lib/CaseContext';

export default function OfficerRemarksForm() {
    const { observations, setObservations, generalRemarks, setGeneralRemarks } = useCaseContext();

    const addObservation = () => setObservations([...observations, { id: Date.now(), topic: '', stated: '', observed: '', discrepancy: 'None' }]);
    const updateObs = (id: number, field: string, val: string) => setObservations(obs => obs.map(o => o.id === id ? { ...o, [field]: val } : o));
    const removeObs = (id: number) => setObservations(obs => obs.filter(o => o.id !== id));

    return (
        <>
            <Card className="mb-8">
                <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50 rounded-t-xl">
                    <div>
                        <h3 className="font-bold text-slate-800">Field Observations vs Statements</h3>
                        <p className="text-sm text-slate-500">Record physical discrepancies noticed during visit.</p>
                    </div>
                    <button onClick={addObservation} className="px-4 py-2 bg-white border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 shadow-sm">+ Add Row</button>
                </div>
                <div className="p-5 space-y-4">
                    {observations.length === 0 && <p className="text-sm text-slate-500 text-center py-4">No observations added yet.</p>}
                    {observations.map((obs) => (
                        <div key={obs.id} className="grid grid-cols-12 gap-3 items-start bg-white p-3 border border-slate-200 rounded-lg relative group">
                            <div className="col-span-12 md:col-span-2">
                                <label className="block text-xs font-semibold text-slate-500 mb-1">Topic</label>
                                <select value={obs.topic} onChange={(e) => updateObs(obs.id, 'topic', e.target.value)} className="w-full text-sm border-slate-300 rounded-md py-1.5 focus:ring-teal-500">
                                    <option value="">Select...</option>
                                    {['Income', 'Stock', 'Living Standard'].map(t => <option key={t} value={t}>{t}</option>)}
                                </select>
                            </div>
                            <div className="col-span-12 md:col-span-4">
                                <label className="block text-xs font-semibold text-slate-500 mb-1">Borrower Claimed</label>
                                <input type="text" value={obs.stated} onChange={(e) => updateObs(obs.id, 'stated', e.target.value)} className="w-full text-sm border-slate-300 rounded-md py-1.5 focus:ring-teal-500" />
                            </div>
                            <div className="col-span-12 md:col-span-4">
                                <label className="block text-xs font-semibold text-slate-500 mb-1">I Observed</label>
                                <input type="text" value={obs.observed} onChange={(e) => updateObs(obs.id, 'observed', e.target.value)} className="w-full text-sm border-slate-300 rounded-md py-1.5 focus:ring-teal-500" />
                            </div>
                            <div className="col-span-12 md:col-span-2">
                                <label className="block text-xs font-semibold text-slate-500 mb-1">Discrepancy</label>
                                <select value={obs.discrepancy} onChange={(e) => updateObs(obs.id, 'discrepancy', e.target.value)} className={`w-full text-sm rounded-md py-1.5 focus:ring-teal-500 font-medium ${obs.discrepancy === 'Major' ? 'bg-red-50 text-red-700' : obs.discrepancy === 'Minor' ? 'bg-amber-50 text-amber-700' : 'bg-slate-50'}`}>
                                    <option value="None">None</option>
                                    <option value="Minor">Minor</option>
                                    <option value="Major">Major</option>
                                </select>
                            </div>
                            <button onClick={() => removeObs(obs.id)} className="absolute -right-2 -top-2 bg-white rounded-full p-1 shadow-md border border-slate-200 text-slate-400 hover:text-red-500 hidden group-hover:block"><Icons.Trash className="w-4 h-4" /></button>
                        </div>
                    ))}
                </div>
            </Card>

            <Card>
                <div className="p-5 border-b border-slate-100 bg-slate-50 rounded-t-xl"><h3 className="font-bold text-slate-800">Overall Assessment</h3></div>
                <div className="p-5">
                    <textarea className="w-full border-slate-300 rounded-xl p-4 text-sm focus:ring-2 focus:ring-teal-500 outline-none" rows={4} placeholder="Enter your final qualitative assessment..." value={generalRemarks} onChange={(e) => setGeneralRemarks(e.target.value)}></textarea>
                </div>
            </Card>
        </>
    );
}
