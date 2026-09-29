'use client';

import React, { useState } from 'react';
import { Icons } from '../../../../../components/ui/Icons';
import RecorderWidget, { RecState } from '../../../../../components/RecorderWidget';
import { useCaseContext } from '../../../../../lib/CaseContext';

export default function QuestionnairePage() {
    const { navigate } = useCaseContext();
    const [recState, setRecState] = useState<RecState>('idle');

    const handleStop = () => {
        setRecState('processing');
        setTimeout(() => navigate('/officer/cases/APP-2026-9823/gap-questions'), 2500);
    };

    return (
        <div className="max-w-3xl mx-auto animate-fadeIn py-12 px-4 flex flex-col items-center justify-center">
            {recState === 'processing' ? (
                <div className="flex flex-col items-center justify-center py-10">
                    <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-teal-600 mb-8"></div>
                    <h3 className="text-xl font-bold text-slate-800 mb-6">Processing AI Analysis...</h3>
                    <div className="space-y-3 w-64">
                        <div className="flex items-center gap-3 text-slate-600"><Icons.CheckCircle className="w-5 h-5 text-emerald-500" /> Transcribing audio</div>
                        <div className="flex items-center gap-3 text-slate-600"><Icons.CheckCircle className="w-5 h-5 text-emerald-500" /> Identifying profile</div>
                        <div className="flex items-center gap-3 text-slate-400 animate-pulse"><div className="w-5 h-5 rounded-full border-2 border-slate-300 border-t-teal-600 animate-spin"></div> Analysing gaps</div>
                    </div>
                </div>
            ) : (
                <>
                    <h2 className="text-2xl font-bold text-slate-800 mb-8">Record Personal Discussion</h2>

                    <RecorderWidget recState={recState} setRecState={setRecState} onStop={handleStop} />

                    {recState === 'idle' && (
                        <button onClick={() => navigate('/officer/cases/APP-2026-9823/gap-questions')} className="mt-8 text-sm font-medium text-slate-500 hover:text-slate-700 underline underline-offset-4">
                            Borrower declined recording - enter manual mode
                        </button>
                    )}
                </>
            )}
        </div>
    );
}
