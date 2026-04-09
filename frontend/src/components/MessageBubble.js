import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function childText(children) {
  if (!children) return '';
  if (typeof children === 'string') return children;
  if (Array.isArray(children)) return children.map(childText).join('');
  if (children?.props?.children) return childText(children.props.children);
  return '';
}

function getHeadlineStyle(text) {
  const s = String(text);
  if (/🔴|🚨/.test(s)) return { borderLeft:'4px solid #ef4444', background:'#fef2f2' };
  if (/🟡|⚠️/.test(s)) return { borderLeft:'4px solid #f59e0b', background:'#fffbeb' };
  if (/🟢|✅/.test(s)) return { borderLeft:'4px solid #10b981', background:'#f0fdf4' };
  return { borderLeft:'4px solid #d4651a', background:'#fff7f0' };
}

const SectionHeader = ({ children }) => (
  <div style={{
    fontSize:11, fontWeight:700, textTransform:'uppercase', letterSpacing:'0.09em',
    color:'#d4651a', margin:'22px 0 10px 0', padding:'7px 14px',
    background:'#fff7f0', borderLeft:'3px solid #d4651a', borderRadius:'0 8px 8px 0',
    display:'flex', alignItems:'center', gap:8,
  }}>
    {children}
  </div>
);

export default function MessageBubble({ role, content }) {
  if (role === 'user') {
    return <div className="bubble user-bubble">{content}</div>;
  }

  return (
    <div className="bubble ai-bubble">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => {
            const text = childText(children);
            const isHeadline = /^[🔴🟡🟢🚨⚠️✅]/.test(text.trim());
            if (isHeadline) {
              const style = getHeadlineStyle(text);
              return (
                <div style={{
                  ...style, padding:'12px 18px', borderRadius:10,
                  marginBottom:18, fontSize:15, fontWeight:800,
                  lineHeight:1.4, color:'#1a1a1a',
                }}>
                  {children}
                </div>
              );
            }
            return <p style={{ margin:'0 0 10px 0', lineHeight:1.7, fontSize:14 }}>{children}</p>;
          },

          h1: ({ children }) => <SectionHeader>{children}</SectionHeader>,
          h2: ({ children }) => <SectionHeader>{children}</SectionHeader>,
          h3: ({ children }) => <SectionHeader>{children}</SectionHeader>,

          ul: ({ children }) => (
            <ul style={{ paddingLeft:0, margin:'0 0 14px 0', listStyle:'none', display:'flex', flexDirection:'column', gap:5 }}>
              {children}
            </ul>
          ),

          li: ({ children, ordered }) => {
            const text = childText(children);
            const isCrit = /🔴|critical|immediately|unauthorized|0\s*%\s*(progress|complete)|abandoned|bypass|ghost|#INVALID|#NO MATCH/i.test(text);
            const isWarn = /⚠️|overdue|missing|invalid|inconsistent|risk|stuck|no (?:pm|owner|director)/i.test(text);
            const isGood = /✅|on.?track|complete|early|ahead|only.*phase.*(done|complete)/i.test(text);
            const borderColor = isCrit ? '#ef4444' : isWarn ? '#f59e0b' : isGood ? '#10b981' : '#e8c4a0';
            const bg = isCrit ? '#fef2f2' : isWarn ? '#fffbeb' : isGood ? '#f0fdf4' : '#fdf6f0';
            const dot = isCrit ? '🔴' : isWarn ? '⚠️' : isGood ? '✅' : '•';
            return (
              <li style={{
                padding:'8px 14px 8px 36px', position:'relative',
                background:bg, borderRadius:8, borderLeft:`3px solid ${borderColor}`,
                fontSize:13.5, lineHeight:1.65, color:'#1a1a1a',
              }}>
                <span style={{ position:'absolute', left:10, top:8, fontSize:isCrit||isWarn||isGood?14:16, lineHeight:1 }}>{dot}</span>
                {children}
              </li>
            );
          },

          ol: ({ children }) => (
            <ol style={{ paddingLeft:0, margin:'0 0 14px 0', listStyle:'none', display:'flex', flexDirection:'column', gap:6, counterReset:'action-item' }}>
              {children}
            </ol>
          ),

          strong: ({ children }) => (
            <strong style={{
              color:'#1a1a1a', fontWeight:700,
              background:'rgba(212,101,26,0.1)',
              padding:'1px 4px', borderRadius:4,
            }}>{children}</strong>
          ),

          em: ({ children }) => (
            <em style={{ color:'#7a4f30', fontStyle:'italic' }}>{children}</em>
          ),

          table: ({ children }) => (
            <div style={{ overflowX:'auto', margin:'14px 0', borderRadius:10, border:'1px solid #f0d5be', boxShadow:'0 2px 8px rgba(212,101,26,0.06)' }}>
              <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead>{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children, ...props }) => <tr style={{ transition:'background 0.1s' }}>{children}</tr>,
          th: ({ children }) => (
            <th style={{
              background:'linear-gradient(135deg,#fff3ea,#ffecd8)',
              padding:'10px 16px', textAlign:'left',
              color:'#7a4f30', fontWeight:700, fontSize:11,
              textTransform:'uppercase', letterSpacing:'0.07em',
              borderBottom:'2px solid #e8c4a0', whiteSpace:'nowrap',
            }}>{children}</th>
          ),
          td: ({ children }) => (
            <td style={{
              padding:'9px 16px', borderBottom:'1px solid #fdf0e8',
              color:'#1a1a1a', fontSize:13, lineHeight:1.5, verticalAlign:'top',
            }}>{children}</td>
          ),

          code: ({ inline, children }) =>
            inline
              ? <code style={{ background:'#fff3ea', color:'#b8511a', padding:'1px 7px', borderRadius:4, fontSize:12, fontFamily:'monospace', border:'1px solid #f0d5be' }}>{children}</code>
              : <pre style={{ background:'#1a1a2e', borderRadius:10, padding:16, overflowX:'auto', margin:'12px 0' }}>
                  <code style={{ color:'#e8c4a0', fontSize:13, fontFamily:'monospace', lineHeight:1.6 }}>{children}</code>
                </pre>,

          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer"
              style={{ color:'#d4651a', textDecoration:'underline', textUnderlineOffset:3 }}>
              {children}
            </a>
          ),

          hr: () => <div style={{ height:1, background:'linear-gradient(to right,#f0d5be,transparent)', margin:'18px 0' }}/>,

          blockquote: ({ children }) => (
            <div style={{
              borderLeft:'3px solid #d4651a', background:'#fff7f0',
              padding:'10px 16px', margin:'12px 0', borderRadius:'0 10px 10px 0',
              fontSize:13, color:'#7a4f30', fontStyle:'italic',
            }}>{children}</div>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}