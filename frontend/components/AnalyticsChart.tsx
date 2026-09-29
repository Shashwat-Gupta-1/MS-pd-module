import React from 'react';
import { Card } from './ui/primitives';

export default function AnalyticsChart() {
    return (
        <Card className="p-6 mb-8">
            <h3 className="font-bold text-slate-800 mb-6">Flagged Inconsistencies by Category (Last 30 Days)</h3>
            <div className="space-y-4">
                {[
                    { label: 'Income Claims', value: 45, max: 50 },
                    { label: 'Years in Business', value: 28, max: 50 },
                    { label: 'Existing Debt', value: 15, max: 50 },
                    { label: 'Stock Valuation', value: 12, max: 50 }
                ].map(item => (
                    <div key={item.label}>
                        <div className="flex justify-between text-sm font-medium text-slate-700 mb-1">
                            <span>{item.label}</span><span>{item.value}</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-3">
                            <div className="bg-teal-500 h-3 rounded-full" style={{ width: `${(item.value / item.max) * 100}%` }}></div>
                        </div>
                    </div>
                ))}
            </div>
        </Card>
    );
}
