import React from 'react';

export default function ToolStrip({ tools, isLive = false }) {
  if (!tools?.length) return null;

  return (
    <div className="tool-strip">
      {tools.map((t, i) => (
        <div key={i} className="tool-pill">
          {isLive && <span className="tool-dot" />}
          <span>{t.display || t.tool}</span>
        </div>
      ))}
    </div>
  );
}
