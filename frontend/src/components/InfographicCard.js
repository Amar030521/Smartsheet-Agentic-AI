import React, { useEffect, useRef, useState } from 'react';

const STATUS_COLOR = {
  good:    { bg:'#f0fdf4', border:'#10b981', text:'#166534', accent:'#10b981' },
  warn:    { bg:'#fffbeb', border:'#f59e0b', text:'#854d0e', accent:'#f59e0b' },
  bad:     { bg:'#fef2f2', border:'#ef4444', text:'#991b1b', accent:'#ef4444' },
  neutral: { bg:'#f8fafc', border:'#94a3b8', text:'#475569', accent:'#94a3b8' },
  info:    { bg:'#eff6ff', border:'#3b82f6', text:'#1e40af', accent:'#3b82f6' },
};

const C = { good:'#10b981', warn:'#f59e0b', bad:'#ef4444', neutral:'#94a3b8', info:'#3b82f6' };

// Animated progress bar
function AnimatedBar({ pct, color, delay = 0 }) {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setWidth(pct), 100 + delay);
    return () => clearTimeout(t);
  }, [pct, delay]);
  return (
    <div style={{ height: 8, background: '#f0e8de', borderRadius: 4, overflow: 'hidden', flex: 1 }}>
      <div style={{
        height: '100%', width: `${width}%`, borderRadius: 4,
        background: color, transition: 'width 0.8s cubic-bezier(0.4,0,0.2,1)',
        boxShadow: `0 0 8px ${color}44`,
      }} />
    </div>
  );
}

// Animated ring
function Ring({ pct, color, size = 80 }) {
  const [progress, setProgress] = useState(0);
  useEffect(() => { const t = setTimeout(() => setProgress(pct), 200); return () => clearTimeout(t); }, [pct]);
  const r = (size - 10) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (progress / 100) * circ;
  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#f0e8de" strokeWidth={8} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={8}
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        style={{ transition: 'stroke-dasharray 1s cubic-bezier(0.4,0,0.2,1)' }} />
    </svg>
  );
}

// ── STAT GRID ────────────────────────────────────────────────────
function StatGrid({ data }) {
  return (
    <div>
      {data.title && <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#b07a55', marginBottom: 10 }}>{data.title}</div>}
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(data.items.length, 4)}, 1fr)`, gap: 10 }}>
        {data.items.map((item, i) => {
          const s = STATUS_COLOR[item.status] || STATUS_COLOR.neutral;
          const vLen = String(item.value).length;
          const vSize = vLen > 8 ? 18 : vLen > 5 ? 22 : 26;
          return (
            <div key={i} style={{
              background: s.bg, border: `1px solid ${s.border}20`,
              borderTop: `3px solid ${s.accent}`, borderRadius: 10,
              padding: '12px 14px', minWidth: 0,
            }}>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: s.text, marginBottom: 6, opacity: 0.8 }}>{item.label}</div>
              <div style={{ fontSize: vSize, fontWeight: 800, color: '#1a1a1a', lineHeight: 1.1, letterSpacing: '-0.02em' }}>{item.value}</div>
              {item.delta && (
                <div style={{ fontSize: 11, color: item.delta.startsWith('+') && !item.delta.startsWith('+-') ? '#10b981' : '#ef4444', fontWeight: 700, marginTop: 4 }}>{item.delta}</div>
              )}
              {item.sub && <div style={{ fontSize: 11, color: s.text, marginTop: 3, lineHeight: 1.4, opacity: 0.85 }}>{item.sub}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── PROGRESS BARS ────────────────────────────────────────────────
function ProgressBars({ data }) {
  return (
    <div>
      {data.title && <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#b07a55', marginBottom: 12 }}>{data.title}</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {data.bars.map((bar, i) => {
          const color = C[bar.status] || '#d4651a';
          const s = STATUS_COLOR[bar.status] || STATUS_COLOR.neutral;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 130, flexShrink: 0, fontSize: 12, fontWeight: 600, color: '#2d1a0e', textAlign: 'right' }}>{bar.label}</div>
              <AnimatedBar pct={bar.pct} color={color} delay={i * 80} />
              <div style={{
                width: 46, flexShrink: 0, fontSize: 12, fontWeight: 700,
                color: color, textAlign: 'right',
              }}>{bar.pct}%</div>
              {bar.note && <div style={{ fontSize: 11, color: '#b07a55', flexShrink: 0 }}>{bar.note}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── PROGRESS RINGS ───────────────────────────────────────────────
function ProgressRings({ data }) {
  return (
    <div>
      {data.title && <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#b07a55', marginBottom: 14 }}>{data.title}</div>}
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        {data.rings.map((ring, i) => {
          const color = C[ring.status] || '#d4651a';
          return (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, minWidth: 80 }}>
              <div style={{ position: 'relative', width: 76, height: 76 }}>
                <Ring pct={ring.pct} color={color} size={76} />
                <div style={{
                  position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center',
                }}>
                  <span style={{ fontSize: 16, fontWeight: 800, color: '#1a1a1a', lineHeight: 1 }}>{ring.pct}%</span>
                </div>
              </div>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#2d1a0e', textAlign: 'center', maxWidth: 80, lineHeight: 1.3 }}>{ring.label}</div>
              {ring.note && <div style={{ fontSize: 10, color: '#b07a55', textAlign: 'center' }}>{ring.note}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── PIPELINE ─────────────────────────────────────────────────────
function Pipeline({ data }) {
  const total = data.stages[0]?.count || 1;
  return (
    <div>
      {data.title && <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#b07a55', marginBottom: 14 }}>{data.title}</div>}
      <div style={{ display: 'flex', alignItems: 'stretch', gap: 0 }}>
        {data.stages.map((stage, i) => {
          const pct = Math.round((stage.count / total) * 100);
          const colors = {
            blue: '#3b82f6', orange: '#d4651a', red: '#ef4444',
            green: '#10b981', amber: '#f59e0b', purple: '#8b5cf6', gray: '#94a3b8'
          };
          const color = colors[stage.color] || '#d4651a';
          const isLast = i === data.stages.length - 1;
          return (
            <React.Fragment key={i}>
              <div style={{ flex: stage.count, minWidth: 60, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <div style={{
                  width: '100%', background: color, borderRadius: i === 0 ? '8px 0 0 8px' : isLast ? '0 8px 8px 0' : 0,
                  padding: '10px 8px', textAlign: 'center', color: '#fff',
                  fontSize: 22, fontWeight: 800, lineHeight: 1,
                  boxShadow: `inset 0 -3px 0 rgba(0,0,0,0.15)`,
                }}>{stage.count}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#2d1a0e', textAlign: 'center', lineHeight: 1.3 }}>{stage.label}</div>
                <div style={{ fontSize: 10, color: '#b07a55' }}>{pct}%</div>
              </div>
              {!isLast && (
                <div style={{ width: 0, height: 0, borderTop: '24px solid transparent', borderBottom: '24px solid transparent', borderLeft: `14px solid ${color}`, flexShrink: 0, marginTop: 0, alignSelf: 'flex-start' }} />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

// ── COMPARISON BARS (budget vs actual) ──────────────────────────
function ComparisonBars({ data }) {
  const maxVal = Math.max(...data.bars.flatMap(b => [b.value1, b.value2 || 0]));
  return (
    <div>
      {data.title && <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#b07a55', marginBottom: 12 }}>{data.title}</div>}
      <div style={{ display: 'flex', gap: 8, fontSize: 11, marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}><div style={{ width: 12, height: 12, borderRadius: 2, background: '#d4651a' }}/>{data.label1 || 'Budget'}</div>
        {data.label2 && <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}><div style={{ width: 12, height: 12, borderRadius: 2, background: '#2563eb' }}/>{data.label2}</div>}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {data.bars.map((bar, i) => {
          const pct1 = (bar.value1 / maxVal) * 100;
          const pct2 = bar.value2 ? (bar.value2 / maxVal) * 100 : 0;
          const over = bar.value2 > bar.value1;
          return (
            <div key={i}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#2d1a0e', marginBottom: 4 }}>{bar.label}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <AnimatedBar pct={pct1} color="#d4651a" delay={i * 60} />
                {bar.value2 !== undefined && <AnimatedBar pct={pct2} color={over ? '#ef4444' : '#2563eb'} delay={i * 60 + 100} />}
              </div>
              {bar.value2 !== undefined && (
                <div style={{ fontSize: 11, color: over ? '#ef4444' : '#10b981', fontWeight: 600, marginTop: 2 }}>
                  {over ? '▲' : '▼'} {bar.label2 || ''} {bar.variance || ''}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── HEALTH SCORECARD ─────────────────────────────────────────────
function HealthScore({ data }) {
  const icons = { good: '✅', warn: '⚠️', bad: '🔴', neutral: '○' };
  return (
    <div>
      {data.title && <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#b07a55', marginBottom: 12 }}>{data.title}</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1, borderRadius: 10, overflow: 'hidden', border: '1px solid #f0d5be' }}>
        {data.metrics.map((m, i) => {
          const s = STATUS_COLOR[m.status] || STATUS_COLOR.neutral;
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '9px 14px', background: i % 2 === 0 ? '#fff' : '#fdf8f5',
              borderBottom: i < data.metrics.length - 1 ? '1px solid #fdf0e8' : 'none',
            }}>
              <div style={{ fontSize: 13, color: '#2d1a0e', fontWeight: 500 }}>{m.label}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: s.accent }}>{m.value}</div>
                <span style={{ fontSize: 14 }}>{icons[m.status] || ''}</span>
              </div>
            </div>
          );
        })}
      </div>
      {data.score !== undefined && (
        <div style={{ marginTop: 10, textAlign: 'center', fontSize: 12, color: '#b07a55' }}>
          Overall health: <strong style={{ fontSize: 16, color: data.score >= 70 ? '#10b981' : data.score >= 40 ? '#f59e0b' : '#ef4444' }}>{data.score}/100</strong>
        </div>
      )}
    </div>
  );
}

// ── RISK MATRIX ──────────────────────────────────────────────────
function RiskMatrix({ data }) {
  const typeIcon = { Risk:'⚠️', Action:'📋', Issue:'🔴', Dependency:'🔗', Assumption:'💭' };
  return (
    <div>
      {data.title && <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#b07a55', marginBottom: 10 }}>{data.title}</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {data.items.map((item, i) => {
          const s = STATUS_COLOR[item.severity] || STATUS_COLOR.warn;
          return (
            <div key={i} style={{
              display: 'flex', gap: 10, padding: '9px 12px',
              background: s.bg, borderRadius: 8, borderLeft: `3px solid ${s.border}`,
              alignItems: 'flex-start',
            }}>
              <span style={{ fontSize: 16, flexShrink: 0, marginTop: 1 }}>{typeIcon[item.type] || '⚠️'}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#1a1a1a' }}>{item.type}: {item.description}</div>
                <div style={{ fontSize: 11, color: '#b07a55', marginTop: 2 }}>
                  {item.owner && <span>Owner: {item.owner} · </span>}
                  {item.days_overdue && <span style={{ color: '#ef4444', fontWeight: 600 }}>{item.days_overdue} days overdue</span>}
                  {item.due && !item.days_overdue && <span>Due: {item.due}</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── MAIN COMPONENT ───────────────────────────────────────────────
export default function InfographicCard({ data }) {
  if (!data) return null;

  const wrapStyle = {
    background: '#fff', border: '1px solid #f0d5be', borderRadius: 12,
    padding: '16px 18px', margin: '10px 0',
  };

  switch (data.type) {
    case 'stat_grid':      return <div style={wrapStyle}><StatGrid data={data} /></div>;
    case 'progress_bars':  return <div style={wrapStyle}><ProgressBars data={data} /></div>;
    case 'progress_rings': return <div style={wrapStyle}><ProgressRings data={data} /></div>;
    case 'pipeline':       return <div style={wrapStyle}><Pipeline data={data} /></div>;
    case 'comparison_bars':return <div style={wrapStyle}><ComparisonBars data={data} /></div>;
    case 'health_score':   return <div style={wrapStyle}><HealthScore data={data} /></div>;
    case 'risk_matrix':    return <div style={wrapStyle}><RiskMatrix data={data} /></div>;
    default: return null;
  }
}
