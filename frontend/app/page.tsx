'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card } from '../components/ui/primitives';
import { Icons } from '../components/ui/Icons';

export default function LoginPage() {
    const router = useRouter();
    const [role, setRole] = useState<'officer' | 'admin'>('officer');
    const [empId, setEmpId] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);

    const handleLogin = (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        
        // Simulate network delay
        setTimeout(() => {
            setLoading(false);
            if (role === 'admin') {
                router.push('/admin');
            } else {
                router.push('/officer/new-case');
            }
        }, 800);
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

                <form onSubmit={handleLogin} className="space-y-5">
                    {/* Role Selector */}
                    <div className="flex p-1 bg-slate-100 rounded-lg">
                        <button 
                            type="button" 
                            onClick={() => setRole('officer')} 
                            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${role === 'officer' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                        >
                            Field Officer
                        </button>
                        <button 
                            type="button" 
                            onClick={() => setRole('admin')} 
                            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${role === 'admin' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                        >
                            Admin / Quality
                        </button>
                    </div>

                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">Employee ID</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Icons.User className="h-5 w-5 text-slate-400" />
                                </div>
                                <input 
                                    type="text" 
                                    required 
                                    value={empId} 
                                    onChange={(e) => setEmpId(e.target.value)} 
                                    className="block w-full pl-10 pr-3 py-2.5 border border-slate-300 rounded-lg text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-shadow" 
                                    placeholder="e.g. MSF-1042" 
                                />
                            </div>
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
                            <input type="checkbox" className="w-4 h-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500" />
                            <span className="text-sm text-slate-600">Remember me</span>
                        </label>
                        <button type="button" className="text-sm font-medium text-teal-600 hover:text-teal-500">Forgot password?</button>
                    </div>

                    <button 
                        type="submit" 
                        disabled={loading} 
                        className="w-full flex justify-center items-center py-3 px-4 border border-transparent rounded-xl shadow-sm text-sm font-semibold text-white bg-slate-900 hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-900 transition-colors disabled:opacity-70 disabled:cursor-not-allowed"
                    >
                        {loading ? <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div> : 'Sign In'}
                    </button>
                </form>
            </Card>
        </div>
    );
}