'use client';

import React, { useState, useMemo } from 'react';
import { Card, Badge } from '../../../components/ui/primitives';
import { Icons } from '../../../components/ui/Icons';
import { useCaseContext } from '../../../lib/CaseContext';

export default function NewCaseProfile() {
    const { profileData, setProfileData, navigate, caseId, setCaseId } = useCaseContext();
    const activeCaseId = caseId || 'APP-2026-9823';
    const [expandedSection, setExpandedSection] = useState<string>('borrower');

    const stats = useMemo(() => {
        let total = 0, filled = 0;
        Object.values(profileData).forEach(section => {
            Object.values(section.fields || {}).forEach(f => {
                if (f.required) { total++; if (f.value.trim() !== '') filled++; }
            });
        });
        return { total, filled, pct: Math.round((filled / total) * 100) || 0 };
    }, [profileData]);

    const handleFieldChange = (sec: string, field: string, val: string) => {
        setProfileData(prev => ({
            ...prev, [sec]: { ...prev[sec], fields: { ...prev[sec].fields, [field]: { ...prev[sec].fields![field], value: val } } }
        }));
    };

    const saveApplicationToDB = async (targetId: string) => {
        try {
            const borrowerName = profileData.borrower?.fields?.name?.value || "Borrower";
            const productType = profileData.business?.fields?.category?.value || "Business Loan";
            await fetch('http://localhost:8000/api/applications', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: targetId,
                    borrower_name: borrowerName,
                    product_type: productType,
                }),
            });
        } catch (err) {
            console.warn("Failed to persist application to DB:", err);
        }
    };

    return (
        <div className="max-w-3xl mx-auto animate-fadeIn pb-20">
            <div className="mb-8">
                <h2 className="text-2xl font-bold text-slate-800 mb-2">Applicant Profile Check</h2>
                <p className="text-slate-600">Review CRM details before starting the Personal Discussion.</p>

                {/* Application ID Controls & Database Sync Banner */}
                <Card className="mt-4 p-4 bg-slate-900 text-white border-0 shadow-md">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                        <div>
                            <label className="text-xs text-slate-400 block font-semibold mb-1">Active Application ID (PostgreSQL Record Key):</label>
                            <div className="flex items-center gap-2">
                                <input
                                    type="text"
                                    value={activeCaseId}
                                    onChange={(e) => setCaseId(e.target.value)}
                                    className="bg-slate-800 border border-slate-700 text-teal-400 font-mono text-sm px-3 py-1.5 rounded-lg focus:ring-2 focus:ring-teal-500 font-bold"
                                />
                            </div>
                        </div>

                        <button
                            type="button"
                            onClick={() => {
                                const newId = `APP-2026-${Math.floor(1000 + Math.random() * 9000)}`;
                                setCaseId(newId);
                                saveApplicationToDB(newId);
                            }}
                            className="px-3.5 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-all shrink-0 cursor-pointer"
                        >
                            <Icons.RotateCcw className="w-3.5 h-3.5" />
                            <span>Generate New Case ID</span>
                        </button>
                    </div>
                </Card>

                <Card className="mt-4 p-4">
                    <div className="flex justify-between items-center mb-2">
                        <span className="text-sm font-semibold text-slate-700">Profile Completeness</span>
                        <span className="text-sm font-bold text-teal-700">{stats.pct}%</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2.5">
                        <div className="bg-teal-600 h-2.5 rounded-full transition-all duration-500" style={{ width: `${stats.pct}%` }}></div>
                    </div>
                    {stats.filled < stats.total && (
                        <p className="text-xs text-amber-700 mt-2 flex items-center gap-1">
                            <Icons.AlertTriangle className="w-4 h-4" /> {stats.total - stats.filled} required fields are missing.
                        </p>
                    )}
                </Card>
            </div>

            <div className="space-y-4 mb-8">
                {Object.entries(profileData).map(([sKey, section]) => {
                    const isExpanded = expandedSection === sKey;
                    const Icon = Icons[section.icon as keyof typeof Icons] || Icons.FileText;
                    let secTotal = 0, secFilled = 0;

                    Object.values(section.fields || {}).forEach(f => {
                        if (f.required) { secTotal++; if (f.value.trim() !== '') secFilled++; }
                    });
                    const isComplete = secTotal === secFilled;

                    return (
                        <Card key={sKey} className="overflow-hidden">
                            <button onClick={() => setExpandedSection(isExpanded ? '' : sKey)} className="w-full px-5 py-4 flex items-center justify-between bg-white hover:bg-slate-50 transition-colors">
                                <div className="flex items-center gap-3">
                                    <div className={`p-2 rounded-lg ${isComplete ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500'}`}>
                                        <Icon className="w-5 h-5" />
                                    </div>
                                    <div className="text-left">
                                        <h3 className="font-semibold text-slate-800">{section.title}</h3>
                                        <p className="text-xs text-slate-500">{secFilled} of {secTotal} filled</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    {isComplete ? <Icons.CheckCircle className="w-5 h-5 text-emerald-500" /> : <Badge variant="warning">Missing Data</Badge>}
                                    {isExpanded ? <Icons.ChevronUp className="w-5 h-5 text-slate-400" /> : <Icons.ChevronDown className="w-5 h-5 text-slate-400" />}
                                </div>
                            </button>
                            {isExpanded && section.fields && (
                                <div className="p-5 border-t border-slate-100 bg-slate-50 grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {Object.entries(section.fields).map(([fKey, field]) => (
                                        <div key={fKey} className="flex flex-col">
                                            <label className="text-xs font-semibold text-slate-600 mb-1 flex justify-between">
                                                <span>{field.label} {field.required && <span className="text-red-500">*</span>}</span>
                                                {field.required && field.value.trim() === '' && <span className="text-red-500 font-normal">Missing</span>}
                                            </label>
                                            {field.type === 'select' ? (
                                                <select value={field.value} onChange={(e) => handleFieldChange(sKey, fKey, e.target.value)} className={`px-3 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-teal-500 bg-white ${field.required && !field.value ? 'border-red-300' : 'border-slate-300'}`}>
                                                    <option value="">Select...</option>
                                                    {field.options?.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                                                </select>
                                            ) : (
                                                <input type={field.type} value={field.value} onChange={(e) => handleFieldChange(sKey, fKey, e.target.value)} className={`px-3 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-teal-500 bg-white ${field.required && !field.value ? 'border-red-300' : 'border-slate-300'}`} placeholder={`Enter ${field.label.toLowerCase()}`} />
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </Card>
                    );
                })}
            </div>
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-slate-200">
                <button
                    type="button"
                    onClick={async () => {
                        let targetId = activeCaseId;
                        if (!targetId || targetId === 'APP-2026-9823') {
                            targetId = `APP-2026-${Math.floor(1000 + Math.random() * 9000)}`;
                            setCaseId(targetId);
                        }
                        await saveApplicationToDB(targetId);
                        navigate(`/officer/cases/${targetId}/photos`);
                    }}
                    className="w-full sm:w-auto px-5 py-3 rounded-xl border border-teal-600/30 bg-teal-50 text-teal-800 font-semibold text-sm hover:bg-teal-100 transition-colors flex items-center justify-center gap-2 cursor-pointer"
                >
                    <Icons.Camera className="w-4 h-4 text-teal-600" />
                    <span>Go Directly to Required Photos</span>
                </button>

                <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
                    <button
                        type="button"
                        onClick={async () => {
                            await saveApplicationToDB(activeCaseId);
                            navigate(`/officer/cases/${activeCaseId}/questionnaire`);
                        }}
                        className="w-full sm:w-auto bg-slate-900 hover:bg-slate-800 text-white px-6 py-3 rounded-xl font-semibold shadow-sm transition-colors flex items-center justify-center gap-2 cursor-pointer"
                    >
                        <span>Start PD Recording</span>
                        <span className="text-xs bg-slate-700 px-2 py-0.5 rounded-md">Step 2 →</span>
                    </button>
                </div>
            </div>
        </div>
    );
}
