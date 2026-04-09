import React, { useState } from 'react';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer
} from 'recharts';

const COLORS = [
  'var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)',
  'var(--chart-4)', 'var(--chart-5)', 'var(--chart-6)'
];

const SOLID_COLORS = [
  '#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'
];

const tooltipStyle = {
  background: '#1a2235',
  border: '1px solid #2a3d5a',
  borderRadius: 8,
  color: '#e8eef8',
  fontSize: 12
};

export default function ChartCard({ data }) {
  const [type, setType] = useState(data.chart_type || 'bar');

  if (!data?.labels?.length || !data?.values?.length) return null;

  const chartData = data.labels.map((label, i) => ({
    name: String(label).length > 16 ? String(label).slice(0, 14) + '…' : String(label),
    fullName: String(label),
    value: parseFloat(data.values[i]) || 0
  }));

  const renderChart = () => {
    switch (type) {
      case 'line':
        return (
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e2d45" />
            <XAxis dataKey="name" tick={{ fill: '#8ba0bc', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#8ba0bc', fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: '#2563eb33' }} />
            <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2.5}
              dot={{ fill: '#2563eb', r: 4, strokeWidth: 2, stroke: '#1a2235' }}
              activeDot={{ r: 6 }} />
          </LineChart>
        );

      case 'pie':
        return (
          <PieChart>
            <Pie data={chartData} dataKey="value" nameKey="name"
              cx="50%" cy="50%" outerRadius={90} innerRadius={40}
              paddingAngle={3}
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              labelLine={{ stroke: '#4a6080' }}>
              {chartData.map((_, i) => (
                <Cell key={i} fill={SOLID_COLORS[i % SOLID_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        );

      default: // bar
        return (
          <BarChart data={chartData} barSize={28}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e2d45" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: '#8ba0bc', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#8ba0bc', fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#ffffff08' }} />
            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
              {chartData.map((_, i) => (
                <Cell key={i} fill={SOLID_COLORS[i % SOLID_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        );
    }
  };

  return (
    <div className="chart-card">
      <div className="chart-header">
        <span className="chart-title">{data.chart_title || 'Chart'}</span>
        <div className="chart-tabs">
          {['bar', 'line', 'pie'].map(t => (
            <button key={t} className={`chart-tab ${type === t ? 'active' : ''}`}
              onClick={() => setType(t)}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        {renderChart()}
      </ResponsiveContainer>
    </div>
  );
}
