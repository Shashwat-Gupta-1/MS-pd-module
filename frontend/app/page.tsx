'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card } from '../components/ui/primitives';
import { Icons } from '../components/ui/Icons';
import { authApi } from '../lib/api';
import { useCaseContext } from '../lib/CaseContext';

export default function LoginPage() {
    const router = useRouter();
    const { setOfficer } = useCaseContext();
    const [role, setRole] = useState<'officer' | 'admin'>('officer');
    const [phone, setPhone] = useState('9876543210');
    const [password, setPassword] = useState('password123');
    const [loading, setLoading] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    // Registration Modal State
    const [isRegisterModalOpen, setIsRegisterModalOpen] = useState(false);
    const [regName, setRegName] = useState('');
    const [regPhone, setRegPhone] = useState('');
    const [regPassword, setRegPassword] = useState('password123');
    const [regBranch, setRegBranch] = useState('Jaipur Central');
    const [regRole, setRegRole] = useState('officer');
    const [regLoading, setRegLoading] = useState(false);
    const [regError, setRegError] = useState<string | null>(null);
    const [regSuccess, setRegSuccess] = useState<string | null>(null);

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        setRegError(null);
        setRegSuccess(null);

        const cleanPhone = regPhone.trim().replace(/\D/g, '');
        if (cleanPhone.length < 10) {
            setRegError('Please enter a valid 10-digit mobile number.');
            return;
        }

        if (!regName.trim()) {
            setRegError('Please enter your full name.');
            return;
        }

        setRegLoading(true);
        try {
            const newOfficer = await authApi.register({
                name: regName.trim(),
                phone: cleanPhone,
                password: regPassword,
                branch: regBranch,
                role: regRole,
            });

            setRegSuccess(`Officer ${newOfficer.name} created! Auto-filling login form...`);

            // Auto-fill login form
            setPhone(cleanPhone);
            setPassword(regPassword);
            setRole(regRole === 'admin' ? 'admin' : 'officer');

            setTimeout(() => {
                setIsRegisterModalOpen(false);
                setRegSuccess(null);
            }, 1500);
        } catch (err: any) {
            setRegError(err.message || 'Registration failed. Mobile number might already exist.');
        } finally {
            setRegLoading(false);
        }
    };


    const handleRoleSwitch = (newRole: 'officer' | 'admin') => {
        setRole(newRole);
        setErrorMessage(null);
        if (newRole === 'officer') {
            setPhone('9876543210');
            setPassword('password123');
        } else {
            setPhone('9999999999');
            setPassword('admin123');
        }
    };

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setErrorMessage(null);

        try {
            // Clean phone number input (fallback if officer typed prefix)
            let cleanPhone = phone.trim().replace(/\D/g, '');
            if (cleanPhone.length < 10) {
                cleanPhone = role === 'admin' ? '9999999999' : '9876543210';
            }

            const res = await authApi.login(cleanPhone, password);
            setOfficer({
                id: res.officer_id,
                name: res.name,
                role: res.role,
                phone: cleanPhone,
            });

            if (res.role === 'admin' || role === 'admin') {
                router.push('/admin');
            } else {
                router.push('/officer/new-case');
            }
        } catch (err: any) {
            console.error('Login error:', err);
            setErrorMessage(err.message || 'Login failed. Please verify credentials.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 animate-fadeIn relative overflow-hidden">
            {/* Background Decorations */}
            <div className="absolute -top-32 -left-32 w-96 h-96 bg-teal-500 rounded-full mix-blend-overlay filter blur-3xl opacity-30"></div>
            <div className="absolute -bottom-32 -right-32 w-96 h-96 bg-emerald-500 rounded-full mix-blend-overlay filter blur-3xl opacity-30"></div>

            <Card className="max-w-md w-full p-8 shadow-2xl border-t-4 border-t-teal-500 relative z-10 bg-white/95 backdrop-blur-sm">
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-teal-50 text-teal-600 mb-4 shadow-inner">
                        <Icons.Briefcase className="w-8 h-8" />
                    </div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 mb-1">MSFincap <span className="text-teal-600">PD Assist</span></h1>
                    <p className="text-sm text-slate-500">Sign in to your account</p>
                </div>

                {errorMessage && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center gap-2">
                        <Icons.AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />
                        <span>{errorMessage}</span>
                    </div>
                )}

                <form onSubmit={handleLogin} className="space-y-5">
                    {/* Role Selector */}
                    <div className="flex p-1 bg-slate-100 rounded-lg">
                        <button 
                            type="button" 
                            onClick={() => handleRoleSwitch('officer')} 
                            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${role === 'officer' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                        >
                            Field Officer
                        </button>
                        <button 
                            type="button" 
                            onClick={() => handleRoleSwitch('admin')} 
                            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${role === 'admin' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                        >
                            Admin / Quality
                        </button>
                    </div>

                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">Registered Mobile Number</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Icons.User className="h-5 w-5 text-slate-400" />
                                </div>
                                <input 
                                    type="text" 
                                    required 
                                    value={phone} 
                                    onChange={(e) => setPhone(e.target.value)} 
                                    className="block w-full pl-10 pr-3 py-2.5 border border-slate-300 rounded-lg text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-shadow font-mono" 
                                    placeholder="e.g. 9876543210" 
                                />
                            </div>
                            <span className="text-[11px] text-slate-400 mt-1 block">
                                {role === 'officer' ? 'Default Officer: 9876543210' : 'Default Admin: 9999999999'}
                            </span>
                        </div>
                        
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Icons.Lock className="h-5 w-5 text-slate-400" />
                                </div>
                                <input 
                                    type="password" 
                                    required 
                                    value={password} 
                                    onChange={(e) => setPassword(e.target.value)} 
                                    className="block w-full pl-10 pr-3 py-2.5 border border-slate-300 rounded-lg text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-shadow" 
                                    placeholder="••••••••" 
                                />
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center justify-between mt-2">
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input type="checkbox" defaultChecked className="w-4 h-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500" />
                            <span className="text-sm text-slate-600">Remember credentials</span>
                        </label>
                        <button type="button" className="text-sm font-medium text-teal-600 hover:text-teal-500">FastAPI JWT Auth</button>
                    </div>

                    <button 
                        type="submit" 
                        disabled={loading} 
                        className="w-full flex justify-center items-center py-3 px-4 border border-transparent rounded-xl shadow-sm text-sm font-semibold text-white bg-slate-900 hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-900 transition-colors disabled:opacity-70 disabled:cursor-not-allowed"
                    >
                        {loading ? <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div> : 'Sign In to MSFincap'}
                    </button>

                    <div className="pt-2 text-center border-t border-slate-100">
                        <button
                            type="button"
                            onClick={() => {
                                setRegError(null);
                                setRegSuccess(null);
                                setIsRegisterModalOpen(true);
                            }}
                            className="text-xs font-semibold text-teal-600 hover:text-teal-700 flex items-center justify-center gap-1.5 mx-auto"
                        >
                            <Icons.UserPlus className="w-3.5 h-3.5" />
                            <span>New Field Officer? Quick Register Here</span>
                        </button>
                    </div>
                </form>
            </Card>

            {/* Quick Register Modal */}
            {isRegisterModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm animate-fadeIn">
                    <Card className="max-w-md w-full p-6 shadow-2xl border border-slate-200 bg-white relative">
                        <button
                            onClick={() => setIsRegisterModalOpen(false)}
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
                                <p className="text-xs text-slate-500">Create an authenticated officer profile</p>
                            </div>
                        </div>

                        {regError && (
                            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-2">
                                <Icons.AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />
                                <span>{regError}</span>
                            </div>
                        )}

                        {regSuccess && (
                            <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center gap-2">
                                <Icons.CheckCircle className="w-4 h-4 shrink-0 text-emerald-600" />
                                <span>{regSuccess}</span>
                            </div>
                        )}

                        <form onSubmit={handleRegister} className="space-y-4">
                            <div>
                                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                                    Full Name <span className="text-red-500">*</span>
                                </label>
                                <input
                                    type="text"
                                    required
                                    value={regName}
                                    onChange={(e) => setRegName(e.target.value)}
                                    placeholder="e.g. Vikas Meena"
                                    className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                                    Mobile Number <span className="text-red-500">*</span>
                                </label>
                                <input
                                    type="tel"
                                    required
                                    maxLength={10}
                                    value={regPhone}
                                    onChange={(e) => setRegPhone(e.target.value)}
                                    placeholder="e.g. 9829012345"
                                    className="w-full px-3.5 py-2.5 text-sm font-mono border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                                    Login Password <span className="text-red-500">*</span>
                                </label>
                                <input
                                    type="password"
                                    required
                                    value={regPassword}
                                    onChange={(e) => setRegPassword(e.target.value)}
                                    placeholder="••••••••"
                                    className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                                        Branch
                                    </label>
                                    <select
                                        value={regBranch}
                                        onChange={(e) => setRegBranch(e.target.value)}
                                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white"
                                    >
                                        <option value="Jaipur Central">Jaipur Central</option>
                                        <option value="Mansarovar">Mansarovar</option>
                                        <option value="Vaishali Nagar">Vaishali Nagar</option>
                                        <option value="Sanganer">Sanganer</option>
                                        <option value="Head Office">Head Office</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                                        Role
                                    </label>
                                    <select
                                        value={regRole}
                                        onChange={(e) => setRegRole(e.target.value)}
                                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white"
                                    >
                                        <option value="officer">Field Officer</option>
                                        <option value="admin">Quality Admin</option>
                                    </select>
                                </div>
                            </div>

                            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                                <button
                                    type="button"
                                    onClick={() => setIsRegisterModalOpen(false)}
                                    className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 font-medium"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={regLoading}
                                    className="flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold shadow-sm transition-all disabled:opacity-50"
                                >
                                    {regLoading ? 'Registering...' : 'Register & Auto Fill'}
                                </button>
                            </div>
                        </form>
                    </Card>
                </div>
            )}
        </div>
    );
}