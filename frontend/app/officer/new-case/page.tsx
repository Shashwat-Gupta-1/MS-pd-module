'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Card, Badge } from '../../../components/ui/primitives';
import { Icons } from '../../../components/ui/Icons';
import { useCaseContext } from '../../../lib/CaseContext';
import { applicantsApi, applicationsApi, questionnaireApi } from '../../../lib/api';
import { samplePresets } from '../../../lib/mockData';
import type { ProfileField } from '../../../lib/types';

export default function NewCaseProfile() {
    const { profileData, setProfileData, navigate, setApplicationId, setSessionId, loadApplicationData } = useCaseContext();
    const [expandedSection, setExpandedSection] = useState<string>('business');
    const [categoriesConfig, setCategoriesConfig] = useState<any[]>([]);
    const [submitting, setSubmitting] = useState<boolean>(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    // 1. Fetch dynamic categories from backend API on mount
    useEffect(() => {
        let mounted = true;
        async function fetchDynamicCategories() {
            try {
                const res = await questionnaireApi.getCategories();
                if (mounted && res?.employment_types?.length) {
                    setCategoriesConfig(res.employment_types);
                    setProfileData(prev => {
                        const bus = prev.business;
                        if (!bus?.fields) return prev;
                        const empVal = (bus.fields.employmentType?.value || '').toLowerCase();
                        const isSalaried = empVal.startsWith('salari') || empVal.includes('salari');
                        const targetType = res.employment_types.find(t =>
                            isSalaried ? t.id === 'salaried' : t.id === 'self_employed'
                        );
                        if (!targetType) return prev;

                        const fieldKey = targetType.sub_category_field;
                        const currField = bus.fields[fieldKey];
                        if (currField) {
                            return {
                                ...prev,
                                business: {
                                    ...bus,
                                    fields: {
                                        ...bus.fields,
                                        [fieldKey]: {
                                            ...currField,
                                            label: targetType.sub_category_label,
                                            options: targetType.categories.map((c: any) => c.label)
                                        }
                                    }
                                }
                            };
                        }
                        return prev;
                    });
                }
            } catch (err) {
                console.warn('Could not load dynamic questionnaire categories:', err);
            }
        }
        fetchDynamicCategories();
        return () => { mounted = false; };
    }, [setProfileData]);

    const stats = useMemo(() => {
        let total = 0, filled = 0;
        Object.values(profileData || {}).forEach(section => {
            if (!section || !section.fields) return;
            Object.values(section.fields).forEach(f => {
                if (f && typeof f === 'object' && f.required) {
                    total++;
                    if (f.value !== undefined && f.value !== null && String(f.value).trim() !== '') filled++;
                }
            });
        });
        return { total, filled, pct: Math.round((filled / total) * 100) || 0 };
    }, [profileData]);

    // 2. Dynamic field handler with Employment Type morphing
    const handleFieldChange = (sec: string, field: string, val: string) => {
        if (sec === 'business' && field === 'employmentType') {
            const valLower = val.toLowerCase();
            const isSalaried = valLower.startsWith('salari') || valLower.includes('salari');

            const salariedOptions = categoriesConfig.find(t => t.id === 'salaried')?.categories?.map((c: any) => c.label) || [
                'Government / PSU', 'Private Company / Corporate'
            ];
            const selfEmployedOptions = categoriesConfig.find(t => t.id === 'self_employed')?.categories?.map((c: any) => c.label) || [
                'Retail / Trading', 'Manufacturing / Job-Work', 'Services / Repairs'
            ];

            setProfileData(prev => {
                const prevBus = prev.business?.fields || {};
                const newFields: Record<string, ProfileField> = isSalaried ? {
                    employmentType: {
                        label: 'Employment Type',
                        value: 'Salaried',
                        required: true,
                        type: 'select',
                        options: ['Self-Employed', 'Salaried']
                    },
                    employerType: {
                        label: 'Employer Type',
                        value: salariedOptions[0] || 'Government / PSU',
                        required: true,
                        type: 'select',
                        options: salariedOptions
                    },
                    employerName: {
                        label: 'Employer / Company Name',
                        value: prevBus.employerName?.value || 'Rajasthan State Road Transport',
                        required: true,
                        type: 'text'
                    },
                    operatingYears: {
                        label: 'Years with Current Employer',
                        value: prevBus.operatingYears?.value || '4',
                        required: true,
                        type: 'number'
                    },
                    monthlyTurnover: {
                        label: 'Monthly In-Hand Net Salary (₹)',
                        value: prevBus.monthlyTurnover?.value || '45000',
                        required: true,
                        type: 'number'
                    },
                    premisesStatus: {
                        label: 'Salary Payment Mode',
                        value: prevBus.premisesStatus?.value || 'Bank Transfer',
                        required: true,
                        type: 'select',
                        options: ['Bank Transfer', 'Cash']
                    },
                    employeeCount: {
                        label: 'Designation / Job Role',
                        value: prevBus.employeeCount?.value || 'Senior Clerk / Executive',
                        required: true,
                        type: 'text'
                    },
                } : {
                    employmentType: {
                        label: 'Employment Type',
                        value: 'Self-Employed',
                        required: true,
                        type: 'select',
                        options: ['Self-Employed', 'Salaried']
                    },
                    businessCategory: {
                        label: 'Business Category',
                        value: selfEmployedOptions[0] || 'Retail / Trading',
                        required: true,
                        type: 'select',
                        options: selfEmployedOptions
                    },
                    businessName: {
                        label: 'Business Name',
                        value: prevBus.businessName?.value || 'Verma Kirana & General Stores',
                        required: true,
                        type: 'text'
                    },
                    operatingYears: {
                        label: 'Years in Business',
                        value: prevBus.operatingYears?.value || '5',
                        required: true,
                        type: 'number'
                    },
                    monthlyTurnover: {
                        label: 'Estimated Monthly Turnover (₹)',
                        value: prevBus.monthlyTurnover?.value || '180000',
                        required: true,
                        type: 'number'
                    },
                    premisesStatus: {
                        label: 'Shop Ownership',
                        value: prevBus.premisesStatus?.value || 'Rented',
                        required: true,
                        type: 'select',
                        options: ['Owned', 'Rented']
                    },
                    employeeCount: {
                        label: 'Number of Workers',
                        value: prevBus.employeeCount?.value || '2',
                        required: true,
                        type: 'number'
                    },
                };

                return {
                    ...prev,
                    business: {
                        ...prev.business,
                        title: isSalaried ? 'Employment Information' : 'Business Information',
                        fields: newFields
                    }
                };
            });
            return;
        }

        setProfileData(prev => ({
            ...prev,
            [sec]: {
                ...prev[sec],
                fields: {
                    ...prev[sec].fields,
                    [field]: { ...prev[sec].fields![field], value: val }
                }
            }
        }));
    };

    const handleStartPD = async () => {
        setSubmitting(true);
        setErrorMessage(null);

        try {
            // Extract fields from profileData
            const borrowerFields = profileData.borrower?.fields || {};
            const businessFields = profileData.business?.fields || {};
            const loanFields = profileData.loan?.fields || {};

            const name = borrowerFields.fullName?.value?.trim() || borrowerFields.name?.value?.trim() || 'Ramesh Kumar Gupta';
            const rawPhone = (borrowerFields.phone?.value || '9812345678').replace(/[^\d+]/g, '');
            const phone = rawPhone.length >= 10 ? rawPhone : '9812345678';
            let pan = (borrowerFields.pan?.value || 'ABCDE1234F').trim().toUpperCase();
            if (pan.length !== 10) pan = 'ABCDE1234F';
            const aadhaar = borrowerFields.aadhaar?.value?.trim() || undefined;

            // Resolve Stage 2 Employment Type
            const rawEmpType = (businessFields.employmentType?.value || businessFields.type?.value || 'Self-Employed').toLowerCase();
            const isSalaried = rawEmpType.startsWith('salari') || rawEmpType.includes('salari');
            const employmentType: 'self_employed' | 'salaried' = isSalaried ? 'salaried' : 'self_employed';

            // Resolve Stage 3 Category Mapping
            let businessCategory = 'retail';
            let employerType: string | undefined = undefined;

            if (isSalaried) {
                const rawSub = (businessFields.employerType?.value || businessFields.businessCategory?.value || '').toLowerCase();
                if (rawSub.includes('gov') || rawSub.includes('psu')) {
                    businessCategory = 'salaried_govt';
                    employerType = 'salaried_govt';
                } else {
                    businessCategory = 'salaried_private';
                    employerType = 'salaried_private';
                }
            } else {
                const rawSub = (businessFields.businessCategory?.value || '').toLowerCase();
                if (rawSub.includes('manuf')) {
                    businessCategory = 'manufacturing';
                } else if (rawSub.includes('serv')) {
                    businessCategory = 'services';
                } else {
                    businessCategory = 'retail';
                }
            }

            const requestedAmount = parseFloat(loanFields.requestedAmount?.value || loanFields.amount?.value) || 500000;
            const tenure = parseInt(loanFields.desiredTenure?.value || loanFields.tenure?.value) || 24;

            // 1. Create applicant in FastAPI
            const applicantRes = await applicantsApi.create({
                name,
                phone,
                pan,
                aadhaar_number: aadhaar,
                employment_type: employmentType,
                business_category: businessCategory,
                employer_type: employerType,
            });

            // 2. Create application in FastAPI
            const appRes = await applicationsApi.create({
                applicant_id: applicantRes.id,
                product_type: loanFields.product?.value || 'secured_business_loan',
                requested_amount: requestedAmount,
                tenure,
                rate: 16.5,
            });

            // 3. Load application questions and state
            const targetAppId = appRes.id;
            setSessionId(null);
            setApplicationId(targetAppId);
            await loadApplicationData(targetAppId);

            // 4. Navigate to live questionnaire
            navigate(`/officer/cases/${targetAppId}/questionnaire`);
        } catch (err: any) {
            console.error('API submission failed:', err);
            const errDetail = err?.response?.data?.detail || err?.message || 'Failed to create applicant or application. Please check fields and try again.';
            setErrorMessage(errDetail);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="max-w-3xl mx-auto animate-fadeIn pb-20">
            <div className="mb-8">
                <h2 className="text-2xl font-bold text-slate-800 mb-2">Applicant Profile Intake</h2>
                <p className="text-slate-600">Review CRM details and register case in backend database before starting PD discussion.</p>

                {/* Quick Presets for Testing & Clean Intake */}
                <div className="flex flex-wrap items-center gap-2 mt-4 p-3 bg-slate-100 rounded-xl border border-slate-200">
                    <span className="text-xs font-bold text-slate-600 mr-1">Quick Sample Presets:</span>
                    <button
                        type="button"
                        onClick={() => { setProfileData(samplePresets.salariedPrivate()); setErrorMessage(null); }}
                        className="px-2.5 py-1.5 text-xs font-semibold rounded-lg bg-teal-600 text-white hover:bg-teal-700 shadow-sm transition-colors flex items-center gap-1.5"
                    >
                        <span>🏢</span> Salaried (Private Corp)
                    </button>
                    <button
                        type="button"
                        onClick={() => { setProfileData(samplePresets.salariedGovt()); setErrorMessage(null); }}
                        className="px-2.5 py-1.5 text-xs font-semibold rounded-lg bg-sky-600 text-white hover:bg-sky-700 shadow-sm transition-colors flex items-center gap-1.5"
                    >
                        <span>🏛️</span> Salaried (Govt / PSU)
                    </button>
                    <button
                        type="button"
                        onClick={() => { setProfileData(samplePresets.selfEmployed()); setErrorMessage(null); }}
                        className="px-2.5 py-1.5 text-xs font-semibold rounded-lg bg-amber-600 text-white hover:bg-amber-700 shadow-sm transition-colors flex items-center gap-1.5"
                    >
                        <span>🏪</span> Self-Employed (Retail)
                    </button>
                </div>

                {errorMessage && (
                    <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center gap-2">
                        <Icons.AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
                        <span>{errorMessage}</span>
                    </div>
                )}

                <Card className="mt-6 p-4">
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
                        if (f && typeof f === 'object' && f.required) {
                            secTotal++;
                            if (f.value !== undefined && f.value !== null && String(f.value).trim() !== '') secFilled++;
                        }
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
                                    {Object.entries(section.fields).map(([fKey, field]) => {
                                        if (!field || typeof field !== 'object') return null;
                                        return (
                                        <div key={fKey} className="flex flex-col">
                                            <label className="text-xs font-semibold text-slate-600 mb-1 flex justify-between">
                                                <span>{field.label || fKey} {field.required && <span className="text-red-500">*</span>}</span>
                                                {field.required && (!field.value || String(field.value).trim() === '') && <span className="text-red-500 font-normal">Missing</span>}
                                            </label>
                                            {field.type === 'select' ? (
                                                <select 
                                                    value={field.value} 
                                                    onChange={(e) => handleFieldChange(sKey, fKey, e.target.value)} 
                                                    className={`px-3 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-teal-500 bg-white ${field.required && !field.value ? 'border-red-300' : 'border-slate-300'}`}
                                                >
                                                    <option value="">Select...</option>
                                                    {field.options?.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                                                </select>
                                            ) : (
                                                <input 
                                                    type={field.type} 
                                                    value={field.value} 
                                                    onChange={(e) => handleFieldChange(sKey, fKey, e.target.value)} 
                                                    className={`px-3 py-2 rounded-lg border text-sm focus:ring-2 focus:ring-teal-500 bg-white ${field.required && !field.value ? 'border-red-300' : 'border-slate-300'}`} 
                                                    placeholder={`Enter ${field.label.toLowerCase()}`} 
                                                />
                                            )}
                                        </div>
                                    );
                                })}
                                </div>
                            )}
                        </Card>
                    );
                })}
            </div>

            <div className="flex justify-end pt-4 border-t border-slate-200">
                <button 
                    onClick={handleStartPD} 
                    disabled={submitting}
                    className="bg-slate-900 hover:bg-slate-800 text-white px-6 py-3 rounded-xl font-semibold shadow-sm transition-colors flex items-center gap-2 disabled:opacity-70"
                >
                    {submitting ? (
                        <>
                            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                            <span>Registering Case...</span>
                        </>
                    ) : (
                        <>
                            <span>Register Case &amp; Start PD Recording</span>
                            <Icons.ArrowRight className="w-4 h-4" />
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}
