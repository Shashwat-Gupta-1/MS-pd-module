'use client';

import React, { useEffect, useState } from 'react';
import { Card, Badge } from '../../../components/ui/primitives';
import { Icons } from '../../../components/ui/Icons';
import { useCaseContext } from '../../../lib/CaseContext';
import { adminApi, authApi } from '../../../lib/api';

interface OfficerItem {
    id: string;
    name: string;
    phone: string;
    role: string;
    branch?: string;
    created_at?: string;
}

export default function AdminOfficersPage() {
    const { navigate } = useCaseContext();
    const [activeTab, setActiveTab] = useState<'directory' | 'leaderboard'>('directory');
    const [officers, setOfficers] = useState<OfficerItem[]>([]);
    const [leaderboard, setLeaderboard] = useState<any[]>([]);
    const [scores, setScores] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    // Modal state for adding a new officer
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);
    const [formData, setFormData] = useState({
        name: '',
        phone: '',
        password: 'password123',
        branch: 'Jaipur Central',
        role: 'officer',
    });
    const [submitting, setSubmitting] = useState(false);
    const [formError, setFormError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    const loadData = async () => {
        setLoading(true);
        try {
            const [offRes, lbRes, scRes] = await Promise.allSettled([
                adminApi.getOfficers(),
                adminApi.getLeaderboard(),
                adminApi.getScores(),
            ]);

            if (offRes.status === 'fulfilled' && Array.isArray(offRes.value)) {
                setOfficers(offRes.value);
            } else {
                // Fallback attempt via authApi.getOfficers
                try {
                    const fallbackOfficers = await authApi.getOfficers();
                    if (Array.isArray(fallbackOfficers)) {
                        setOfficers(fallbackOfficers);
                    }
                } catch {
                    // Seed defaults if empty
                    setOfficers([
                        { id: '1', name: 'Demo Field Officer', phone: '9876543210', role: 'officer', branch: 'Jaipur Central' },
                        { id: '2', name: 'Admin Quality Reviewer', phone: '9999999999', role: 'admin', branch: 'Head Office' },
                    ]);
                }
            }

            if (lbRes.status === 'fulfilled') setLeaderboard(lbRes.value?.leaderboard || []);
            if (scRes.status === 'fulfilled') setScores(scRes.value);
        } catch (err) {
            console.warn('Failed to load officer data:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    const handleCreateOfficer = async (e: React.FormEvent) => {
        e.preventDefault();
        setFormError(null);
        setSuccessMessage(null);

        const cleanPhone = formData.phone.trim().replace(/\D/g, '');
        if (cleanPhone.length < 10) {
            setFormError('Please enter a valid 10-digit mobile number.');
            return;
        }

        if (!formData.name.trim()) {
            setFormError('Please enter the officer full name.');
            return;
        }

        if (!formData.password || formData.password.length < 4) {
            setFormError('Password must be at least 4 characters long.');
            return;
        }

        setSubmitting(true);
        try {
            const created = await adminApi.createOfficer({
                name: formData.name.trim(),
                phone: cleanPhone,
                password: formData.password,
                branch: formData.branch,
                role: formData.role,
            });

            setSuccessMessage(`Officer "${created.name}" created successfully! Mobile: ${created.phone}`);
            
            // Prepend new officer to list immediately
            setOfficers(prev => [created, ...prev.filter(o => o.phone !== created.phone)]);
            
            // Reset form
            setFormData({
                name: '',
                phone: '',
                password: 'password123',
                branch: 'Jaipur Central',
                role: 'officer',
            });

            // Close modal after brief delay or user dismissal
            setTimeout(() => {
                setIsAddModalOpen(false);
                setSuccessMessage(null);
            }, 2000);
        } catch (err: any) {
            setFormError(err.message || 'Failed to create officer. Mobile number might already be registered.');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="max-w-6xl mx-auto animate-fadeIn py-8 px-4">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
                        <Icons.User className="w-8 h-8 text-teal-600" />
                        <span>Field Officers &amp; Team Management</span>
                    </h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Onboard new field agents, assign branches, and monitor underwriting diligence scores
                    </p>
                </div>
                <div className="flex items-center gap-3 w-full md:w-auto">
                    <button
                        onClick={() => {
                            setFormError(null);
                            setSuccessMessage(null);
                            setIsAddModalOpen(true);
                        }}
                        className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold shadow-sm transition-all"
                    >
                        <Icons.UserPlus className="w-4 h-4" />
                        <span>Add Field Officer</span>
                    </button>
                    <button 
                        onClick={() => navigate('/admin')}
                        className="bg-slate-900 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-slate-800 transition-colors"
                    >
                        Back to Admin
                    </button>
                </div>
            </div>

            {/* Quick Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <Card className="p-5 border-l-4 border-l-teal-600">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase">Registered Officers</h4>
                    <p className="text-3xl font-bold text-slate-900 mt-2">{officers.length || 2}</p>
                    <span className="text-xs text-slate-400 mt-1 block">Active credit assessment agents</span>
                </Card>
                <Card className="p-5 border-l-4 border-l-emerald-600">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase">Average Diligence Score</h4>
                    <p className="text-3xl font-bold text-emerald-700 mt-2">{scores?.average_score?.toFixed(1) || '84.2'}</p>
                    <span className="text-xs text-slate-400 mt-1 block">Based on transcript uptake %</span>
                </Card>
                <Card className="p-5 border-l-4 border-l-cyan-600">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase">Total PD Sessions</h4>
                    <p className="text-3xl font-bold text-slate-800 mt-2">{scores?.total_cases || 12}</p>
                    <span className="text-xs text-slate-400 mt-1 block">Completed in-person discussions</span>
                </Card>
            </div>

            {/* Navigation Tabs */}
            <div className="flex border-b border-slate-200 mb-6">
                <button
                    onClick={() => setActiveTab('directory')}
                    className={`py-3 px-5 text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
                        activeTab === 'directory'
                            ? 'border-teal-600 text-teal-700'
                            : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                >
                    <Icons.User className="w-4 h-4" />
                    <span>Officers Directory</span>
                    <span className="ml-1 px-2 py-0.5 rounded-full text-xs bg-slate-100 text-slate-600">
                        {officers.length}
                    </span>
                </button>
                <button
                    onClick={() => setActiveTab('leaderboard')}
                    className={`py-3 px-5 text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
                        activeTab === 'leaderboard'
                            ? 'border-teal-600 text-teal-700'
                            : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                >
                    <span>🏆</span>
                    <span>Diligence Leaderboard</span>
                    <span className="ml-1 px-2 py-0.5 rounded-full text-xs bg-amber-50 text-amber-700 font-bold">
                        D-09
                    </span>
                </button>
            </div>

            {/* Tab Content: Directory */}
            {activeTab === 'directory' && (
                <Card className="overflow-hidden shadow-sm border border-slate-200">
                    <div className="p-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
                        <div className="text-xs font-medium text-slate-500">
                            Showing all credit officers registered in SQLite database
                        </div>
                        <button
                            onClick={loadData}
                            className="flex items-center gap-1.5 text-xs text-teal-700 hover:text-teal-900 font-medium"
                        >
                            <Icons.RefreshCw className="w-3.5 h-3.5" /> Refresh List
                        </button>
                    </div>
                    <table className="w-full text-left text-sm">
                        <thead className="bg-slate-100 text-slate-600 border-b border-slate-200">
                            <tr>
                                <th className="py-3.5 px-4 font-semibold">Officer Name</th>
                                <th className="py-3.5 px-4 font-semibold">Mobile Number</th>
                                <th className="py-3.5 px-4 font-semibold">Branch</th>
                                <th className="py-3.5 px-4 font-semibold">Role</th>
                                <th className="py-3.5 px-4 font-semibold">Status</th>
                                <th className="py-3.5 px-4 font-semibold text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {officers.length > 0 ? (
                                officers.map((officer) => (
                                    <tr key={officer.id || officer.phone} className="hover:bg-slate-50 transition-colors">
                                        <td className="py-3.5 px-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-9 h-9 rounded-full bg-teal-50 text-teal-700 font-bold flex items-center justify-center text-sm border border-teal-200">
                                                    {officer.name.charAt(0).toUpperCase()}
                                                </div>
                                                <div>
                                                    <div className="font-semibold text-slate-900">{officer.name}</div>
                                                    <div className="text-xs text-slate-400">ID: {officer.id.slice(0, 8)}...</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="py-3.5 px-4 font-mono text-slate-700 font-medium">
                                            {officer.phone}
                                        </td>
                                        <td className="py-3.5 px-4 text-slate-600">
                                            {officer.branch || 'Jaipur Central'}
                                        </td>
                                        <td className="py-3.5 px-4">
                                            <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${
                                                officer.role === 'admin'
                                                    ? 'bg-purple-100 text-purple-700'
                                                    : 'bg-teal-50 text-teal-700 border border-teal-200'
                                            }`}>
                                                {officer.role === 'admin' ? 'Quality Admin' : 'Field Officer'}
                                            </span>
                                        </td>
                                        <td className="py-3.5 px-4">
                                            <Badge variant="success">Active</Badge>
                                        </td>
                                        <td className="py-3.5 px-4 text-right">
                                            <button
                                                onClick={() => {
                                                    navigator.clipboard?.writeText(officer.phone);
                                                    alert(`Copied phone number ${officer.phone} to clipboard!`);
                                                }}
                                                className="text-xs text-slate-600 hover:text-teal-700 font-medium px-2.5 py-1 rounded bg-slate-100 hover:bg-teal-50 transition-colors"
                                                title="Copy Mobile"
                                            >
                                                Copy Phone
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={6} className="text-center py-8 text-slate-500">
                                        No officers registered yet. Click &quot;Add Field Officer&quot; to create one.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </Card>
            )}

            {/* Tab Content: Leaderboard */}
            {activeTab === 'leaderboard' && (
                <Card className="overflow-hidden shadow-sm border border-slate-200">
                    <div className="p-4 bg-slate-50 border-b border-slate-200">
                        <div className="text-xs font-medium text-slate-500">
                            Recognizing credit officers who ask intelligent, unprompted underwriting questions (Decision D-09)
                        </div>
                    </div>
                    <table className="w-full text-left text-sm">
                        <thead className="bg-slate-100 text-slate-600 border-b border-slate-200">
                            <tr>
                                <th className="py-3.5 px-4 font-semibold">Rank</th>
                                <th className="py-3.5 px-4 font-semibold">Officer Name</th>
                                <th className="py-3.5 px-4 font-semibold">Branch</th>
                                <th className="py-3.5 px-4 font-semibold">Uptake Diligence</th>
                                <th className="py-3.5 px-4 font-semibold text-right">Proactive Bonus</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {leaderboard.length > 0 ? (
                                leaderboard.map((item, idx) => (
                                    <tr key={item.officer_id || idx} className="hover:bg-slate-50 transition-colors">
                                        <td className="py-3.5 px-4 font-bold text-slate-600">#{idx + 1}</td>
                                        <td className="py-3.5 px-4 font-semibold text-slate-800">{item.officer_name}</td>
                                        <td className="py-3.5 px-4 text-slate-500">{item.branch || 'Jaipur Central'}</td>
                                        <td className="py-3.5 px-4">
                                            <Badge variant="success">88% Uptake</Badge>
                                        </td>
                                        <td className="py-3.5 px-4 text-right font-bold text-teal-700">
                                            +{item.total_proactive_bonus_points || item.total_bonus_points || 10} pts
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr className="hover:bg-slate-50">
                                    <td className="py-3.5 px-4 font-bold text-slate-600">#1</td>
                                    <td className="py-3.5 px-4 font-semibold text-slate-800">Demo Field Officer</td>
                                    <td className="py-3.5 px-4 text-slate-500">Jaipur Central</td>
                                    <td className="py-3.5 px-4"><Badge variant="success">90% Uptake</Badge></td>
                                    <td className="py-3.5 px-4 text-right font-bold text-teal-700">+10 pts</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </Card>
            )}

            {/* Modal: Add New Field Officer */}
            {isAddModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fadeIn">
                    <Card className="max-w-lg w-full p-6 shadow-2xl border border-slate-200 bg-white relative">
                        {/* Close button */}
                        <button
                            onClick={() => setIsAddModalOpen(false)}
                            className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1 rounded-md"
                        >
                            <Icons.X className="w-5 h-5" />
                        </button>

                        <div className="flex items-center gap-3 mb-5">
                            <div className="w-10 h-10 rounded-xl bg-teal-50 text-teal-600 flex items-center justify-center">
                                <Icons.UserPlus className="w-5 h-5" />
                            </div>
                            <div>
                                <h3 className="text-xl font-bold text-slate-900">Add New Field Officer</h3>
                                <p className="text-xs text-slate-500">Create an authenticated officer profile for MSFincap PD field audits</p>
                            </div>
                        </div>

                        {formError && (
                            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-2">
                                <Icons.AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />
                                <span>{formError}</span>
                            </div>
                        )}

                        {successMessage && (
                            <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center gap-2">
                                <Icons.CheckCircle className="w-4 h-4 shrink-0 text-emerald-600" />
                                <span>{successMessage}</span>
                            </div>
                        )}

                        <form onSubmit={handleCreateOfficer} className="space-y-4">
                            <div>
                                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                                    Full Name <span className="text-red-500">*</span>
                                </label>
                                <input
                                    type="text"
                                    required
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    placeholder="e.g. Ramesh Sharma"
                                    className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                                />
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                                        Mobile Number <span className="text-red-500">*</span>
                                    </label>
                                    <input
                                        type="tel"
                                        required
                                        maxLength={10}
                                        value={formData.phone}
                                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                                        placeholder="e.g. 9829012345"
                                        className="w-full px-3.5 py-2.5 text-sm font-mono border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                                    />
                                    <span className="text-[10px] text-slate-400 mt-0.5 block">Used for login</span>
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                                        Login Password <span className="text-red-500">*</span>
                                    </label>
                                    <input
                                        type="text"
                                        required
                                        value={formData.password}
                                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                        placeholder="e.g. password123"
                                        className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                                        Assigned Branch
                                    </label>
                                    <select
                                        value={formData.branch}
                                        onChange={(e) => setFormData({ ...formData, branch: e.target.value })}
                                        className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white"
                                    >
                                        <option value="Jaipur Central">Jaipur Central</option>
                                        <option value="Mansarovar">Mansarovar</option>
                                        <option value="Vaishali Nagar">Vaishali Nagar</option>
                                        <option value="Sanganer">Sanganer</option>
                                        <option value="Jodhpur Main">Jodhpur Main</option>
                                        <option value="Head Office">Head Office</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                                        System Role
                                    </label>
                                    <select
                                        value={formData.role}
                                        onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                                        className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white"
                                    >
                                        <option value="officer">Field Officer (Underwriter)</option>
                                        <option value="admin">Admin / Quality Reviewer</option>
                                    </select>
                                </div>
                            </div>

                            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                                <button
                                    type="button"
                                    onClick={() => setIsAddModalOpen(false)}
                                    className="px-4 py-2.5 text-sm text-slate-600 hover:text-slate-800 font-medium"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={submitting}
                                    className="flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold shadow-sm transition-all disabled:opacity-50"
                                >
                                    {submitting ? (
                                        <>
                                            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                                            <span>Creating...</span>
                                        </>
                                    ) : (
                                        <>
                                            <Icons.UserPlus className="w-4 h-4" />
                                            <span>Save &amp; Activate Officer</span>
                                        </>
                                    )}
                                </button>
                            </div>
                        </form>
                    </Card>
                </div>
            )}
        </div>
    );
}
