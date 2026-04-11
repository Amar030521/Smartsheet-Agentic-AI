import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useAuth } from './hooks/useAuth';
import LoginPage from './components/LoginPage';
import AdminPanel from './components/AdminPanel';
import { v4 as uuidv4 } from 'uuid';
import { sendMessage, sendMessageStream, clearSession, getHealth } from './utils/api';
import { useVoiceInput } from './hooks/useVoiceInput';
import { useDynamicSidebar } from './hooks/useDynamicSidebar';
import { useChatSessions } from './hooks/useChatSessions';
import MessageBubble from './components/MessageBubble';
import ChartCard from './components/ChartCard';
import DashboardCard from './components/DashboardCard';
import FormCard from './components/FormCard';
import InfographicCard from './components/InfographicCard';
import ToolStrip from './components/ToolStrip';
import ConfirmCard from './components/ConfirmCard';
import './index.css';

const SESSION_KEY = 'smartsheet_agent_session';

const WELCOME_MESSAGE = {
  id: 'welcome',
  role: 'assistant',
  followups: [],
  content: `**Welcome to Smartsheet AI Agent** — your Smartsheet intelligence layer.

I have real-time access to your workspaces, sheets, and Control Center. Ask me anything about your projects, metrics, or data.

**What I can do:**
- Query project status, KPIs, and productivity metrics
- Analyze trends and surface insights with charts
- Create or update rows directly from chat
- Roll out new projects via Control Center
- Create dashboards in your workspace
- Answer follow-up questions with full context

**Try:** *"What's the status of my projects?"* or *"Show KPI metrics for this quarter"*`,
  tool_calls: [],
  chart_data: null,
  needs_confirmation: false
};


const QUICK_PROMPTS = [
  { icon: '🎯', text: 'What\'s the status of all my projects?' },
  { icon: '📈', text: 'Show KPI metrics with a chart' },
  { icon: '⚠️', text: 'Which projects are delayed or at risk?' },
  { icon: '🚀', text: 'Roll out a new project from Control Center' },
  { icon: '💰', text: 'Show budget vs actuals' },
  { icon: '📊', text: 'Productivity summary this month' },
];


// ── TREE NODE COMPONENT ──────────────────────────────────────────
function WorkspaceNode({ node, depth, expanded, setExpanded, onSend, loadWorkspaceTree }) {
  const key = node.id;
  const isOpen = expanded[key];
  const [loadingChildren, setLoadingChildren] = React.useState(false);

  const hasChildren = node.type === 'workspace'
    ? true
    : (node.folders?.length > 0) || (node.subfolders?.length > 0) ||
      (node.sheets?.length > 0) || (node.dashboards?.length > 0) ||
      (node.reports?.length > 0);

  const toggle = (e) => {
    e.stopPropagation();
    handleExpand();
  };

  const handleExpand = async () => {
    const newOpen = !isOpen;
    setExpanded(prev => ({ ...prev, [key]: newOpen }));
    if (newOpen && node.type === 'workspace' && !node.loaded && loadWorkspaceTree) {
      setLoadingChildren(true);
      await loadWorkspaceTree(node.id);
      setLoadingChildren(false);
    }
  };

  const handleClick = () => {
    if (node.type === 'workspace') {
      onSend(`Show me the contents of workspace "${node.name}" (workspace_id: ${node.id})`);
      handleExpand();
    } else if (node.type === 'sheet') {
      onSend(`Show me data from sheet "${node.name}" (sheet_id: ${node.id})`);
    } else if (node.type === 'dashboard') {
      onSend(`Show me the dashboard "${node.name}" (sight_id: ${node.id})`);
    } else if (node.type === 'folder') {
      setExpanded(prev => ({ ...prev, [key]: !prev[key] }));
    }
  };

  const icon = {
    workspace: '🏢', folder: '📁', sheet: '📋',
    dashboard: '🖥️', report: '📊'
  }[node.type] || '📄';

  const indent = depth * 12;

  return (
    <div>
      <div className="sidebar-item tree-node"
        style={{ paddingLeft: 8 + indent }}
        onClick={handleClick}
        title={node.name}>
        {hasChildren && (
          <span className="tree-arrow" onClick={toggle}
            style={{ marginRight: 4, fontSize: 10, opacity: 0.7, minWidth: 12, display: 'inline-block' }}>
            {loadingChildren ? '⏳' : isOpen ? '▼' : '▶'}
          </span>
        )}
        {!hasChildren && <span style={{ minWidth: 16, display: 'inline-block' }} />}
        <span className="item-icon" style={{ marginRight: 6 }}>{icon}</span>
        <span className="item-label">{node.name}</span>
      </div>

      {isOpen && hasChildren && (
        <div className="tree-children">
          {(node.folders || node.subfolders || []).map(f => (
            <WorkspaceNode key={f.id} node={f} depth={depth + 1}
              expanded={expanded} setExpanded={setExpanded} onSend={onSend} loadWorkspaceTree={loadWorkspaceTree} />
          ))}
          {(node.sheets || []).map(s => (
            <WorkspaceNode key={s.id} node={s} depth={depth + 1}
              expanded={expanded} setExpanded={setExpanded} onSend={onSend} loadWorkspaceTree={loadWorkspaceTree} />
          ))}
          {(node.dashboards || []).map(d => (
            <WorkspaceNode key={d.id} node={{ ...d, type: 'dashboard' }} depth={depth + 1}
              expanded={expanded} setExpanded={setExpanded} onSend={onSend} loadWorkspaceTree={loadWorkspaceTree} />
          ))}
          {(node.reports || []).map(r => (
            <WorkspaceNode key={r.id} node={{ ...r, type: 'report' }} depth={depth + 1}
              expanded={expanded} setExpanded={setExpanded} onSend={onSend} loadWorkspaceTree={loadWorkspaceTree} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── LIVE AGENT STATUS INDICATOR ─────────────────────────────────
// Receives real events from backend SSE stream — zero fake timers.
// events: array of { type, text, icon, display } pushed live as agent works.
function AgentStatusIndicator({ events }) {
  const latest = events.length > 0 ? events[events.length - 1] : null;
  const toolCount = events.filter(e => e.type === 'tool').length;
  // Progress grows with each real tool call, max 85% until response arrives
  const pct = events.length === 0 ? 5 : Math.min(85, 10 + toolCount * 15);

  const icon = latest?.icon || '🤖';
  const text = latest?.type === 'tool'
    ? (latest.display || latest.tool)
    : (latest?.text || 'Connecting to Smartsheet...');

  return (
    <div className="msg-group">
      <div className="msg-avatar ai">AI</div>
      <div className="msg-body">
        <div className="thinking agent-status">
          <div className="thinking-dots">
            <span /><span /><span />
          </div>
          <div className="agent-status-content">
            <div className="agent-status-text">
              <span className="agent-status-icon">{icon}</span>
              {text}
            </div>
            <div className="agent-progress-bar">
              <div
                className="agent-progress-fill"
                style={{ width: `${pct}%`, transition: 'width 0.5s ease' }}
              />
            </div>
            <div className="agent-progress-label">
              {toolCount > 0
                ? `${toolCount} tool${toolCount !== 1 ? 's' : ''} called`
                : 'Starting...'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const { user, loading: authLoading, login, logout, getToken } = useAuth();
  const [showAdmin, setShowAdmin] = useState(false);
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [streamEvents, setStreamEvents] = useState([]);
  const [sessionId] = useState(() => localStorage.getItem(SESSION_KEY) || uuidv4());
  const [pendingConfirmation, setPendingConfirmation] = useState(null);
  const [healthStatus, setHealthStatus] = useState('connecting');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const { sections: sidebarSections, treeData: sidebarData, loading: sidebarLoading, reload: reloadSidebar, loadWorkspaceTree } = useDynamicSidebar(sessionId, getToken, user);
  const { sessions: chatSessions, loadSessions: reloadSessions, loadMessages, renameSession, deleteSession } = useChatSessions(getToken, user);
  const [showAllSessions, setShowAllSessions] = useState(false);
  const [sessionsCollapsed, setSessionsCollapsed] = useState(false);
  const [workspacesCollapsed, setWorkspacesCollapsed] = useState(false);
  const [editingSessionId, setEditingSessionId] = useState(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [expandedNodes, setExpandedNodes] = useState({});
  const [sidebarWidth, setSidebarWidth] = useState(200);
  const isResizing = React.useRef(false);

  const startResize = React.useCallback((e) => {
    isResizing.current = true;
    const startX = e.clientX;
    const startW = sidebarWidth;
    const onMove = (ev) => {
      if (!isResizing.current) return;
      const newW = Math.min(400, Math.max(150, startW + ev.clientX - startX));
      setSidebarWidth(newW);
    };
    const onUp = () => {
      isResizing.current = false;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [sidebarWidth]);

  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    localStorage.setItem(SESSION_KEY, sessionId);
  }, [sessionId]);

  useEffect(() => {
    getHealth()
      .then(h => setHealthStatus(h.smartsheet_connected ? 'connected' : 'degraded'))
      .catch(() => setHealthStatus('error'));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    }
  }, [input]);

  const { isRecording, isSupported: voiceSupported, startRecording, stopRecording } = useVoiceInput({
    onResult: (text) => {
      setInput(text);
      setIsListening(false);
      setTimeout(() => doSend(text, true), 300);
    },
    onError: (err) => {
      setIsListening(false);
      console.warn(err);
    }
  });

  const doSend = useCallback(async (text, fromVoice = false) => {
    const userText = (text || input).trim();
    if (!userText || isLoading) return;

    setInput('');
    setIsLoading(true);
    setStreamEvents([]);
    setPendingConfirmation(null);

    const userMsg = {
      id: uuidv4(), role: 'user', content: userText,
      tool_calls: [], chart_data: null, needs_confirmation: false
    };
    setMessages(prev => [...prev, userMsg]);

    try {
      const res = await sendMessageStream(userText, sessionId, fromVoice, (event) => {
        if (event.type === 'status' || event.type === 'tool') {
          setStreamEvents(prev => [...prev, event]);
        }
      });

      if (!res) throw new Error('No response received from server');

      const aiMsg = {
        id: uuidv4(),
        role: 'assistant',
        content: res.response,
        chart_data: res.chart_data || null,
        dashboard_data: res.dashboard_data || null,
        input_form: res.input_form || null,
        infographics: res.infographics || [],
        tool_calls: res.tool_calls || [],
        needs_confirmation: res.needs_confirmation || false,
        followups: res.followups || [],
        processing_time_ms: res.processing_time_ms
      };

      setMessages(prev => [...prev, aiMsg]);

      if (res.needs_confirmation) {
        setPendingConfirmation({ msgId: aiMsg.id, text: userText });
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        id: uuidv4(), role: 'assistant',
        content: `⚠️ **Error:** ${err.message}\n\nPlease check your connection and try again.`,
        tool_calls: [], chart_data: null, needs_confirmation: false
      }]);
    } finally {
      setIsLoading(false);
      setStreamEvents([]);
      inputRef.current?.focus();
      reloadSessions();
    }
  }, [input, isLoading, sessionId]);

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      doSend();
    }
  };

  const handleConfirm = () => {
    setPendingConfirmation(null);
    doSend('Yes, confirmed. Please proceed.');
  };

  const handleCancel = () => {
    setPendingConfirmation(null);
    setMessages(prev => [...prev, {
      id: uuidv4(), role: 'assistant',
      content: '✓ Action cancelled. What else can I help you with?',
      tool_calls: [], chart_data: null, needs_confirmation: false
    }]);
  };

  const loadHistorySession = useCallback(async (session) => {
    const msgs = await loadMessages(session.id);
    if (!msgs.length) {
      setMessages([{
        id: uuidv4(), role: 'assistant',
        content: '⚠️ Could not load messages for this session. The session may be empty or there was a connection issue.',
        tool_calls: [], chart_data: null, needs_confirmation: false, followups: [], infographics: []
      }]);
      return;
    }
    const formatted = msgs.map(m => ({
      id: m.id || uuidv4(),
      role: m.role,
      content: m.content,
      tool_calls: m.tool_calls || [],
      chart_data: m.chart_data || null,
      dashboard_data: m.dashboard_data || null,
      infographics: m.infographics || [],
      followups: m.followups || [],
      needs_confirmation: false,
    }));
    setMessages(formatted);
    localStorage.setItem(SESSION_KEY, session.id);
  }, [loadMessages]);

  const handleNewSession = async () => {
    await clearSession(sessionId).catch(() => {});
    localStorage.removeItem(SESSION_KEY);
    window.location.reload();
  };

  const handleVoice = () => {
    if (isRecording) {
      stopRecording();
      setIsListening(false);
    } else {
      setIsListening(true);
      startRecording();
    }
  };

  const statusLabel = {
    connecting: 'Connecting...',
    connected: 'Live · Smartsheet API',
    degraded: 'Degraded',
    error: 'Connection Error'
  }[healthStatus] || 'Unknown';

  if (authLoading) return (
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'#fff7f0' }}>
      <div style={{ fontSize:14, color:'#b07a55' }}>Loading...</div>
    </div>
  );
  if (!user) return <LoginPage onLogin={login} />;

  return (
    <>
    <div className="app">
      {/* HEADER */}
      <header className="header">
        <div className="header-left">
          <button className="header-btn" onClick={() => setSidebarOpen(o => !o)}
            style={{ fontSize: 16, padding: '5px 10px' }}>
            {sidebarOpen ? '◀' : '▶'}
          </button>
          <div className="logo-mark">
            <div className="logo-bar" />
            <div className="logo-bar" />
            <div className="logo-bar" />
          </div>
          <div className="logo-text">
            <span className="logo-title">Smartsheet AI Agent</span>
            <span className="logo-subtitle">Smartsheet Intelligence</span>
          </div>
        </div>

        <div className="header-center">
          <div className="status-pill">
            <div className={`status-dot ${healthStatus === 'connecting' ? 'connecting' : healthStatus === 'error' ? 'error' : ''}`} />
            {statusLabel}
          </div>
        </div>

        <div className="header-right" style={{ display:'flex', alignItems:'center', gap:8 }}>
          <span style={{ fontSize:12, color:'#7a4f30', fontWeight:600 }}>👤 {user.name}</span>
          {user.is_admin && (
            <button className="header-btn" onClick={() => setShowAdmin(true)}
              style={{ background:'#fff3ea', color:'#d4651a', border:'1px solid #f0d5be' }}>
              ⚙️ Admin
            </button>
          )}
          <button className="header-btn" onClick={() => { logout(); window.location.href = '/'; }}
            style={{ color:'#7a4f30' }}>
            Sign out
          </button>
          <button className="header-btn" onClick={handleNewSession}>+ New Chat</button>
        </div>
      </header>

      <div className="main">
        {/* SIDEBAR */}
        {sidebarOpen && (
          <aside className="sidebar" style={{ width: sidebarWidth, minWidth: sidebarWidth, position: 'relative' }}>
            {sidebarLoading ? (
              <div style={{ padding: '16px 8px' }}>
                <div className="sidebar-label">Loading workspaces...</div>
                {[1,2,3,4,5].map(i => (
                  <div key={i} className="sidebar-item" style={{ opacity: 0.3 }}>
                    <span className="item-icon">◌</span>
                    <span style={{ background: 'var(--border-default)', borderRadius: 4, color: 'transparent', minWidth: 80 }}>Loading</span>
                  </div>
                ))}
              </div>
            ) : (
              <>
                {/* WORKSPACES TREE */}
                <div className="sidebar-section">
                  <div className="sidebar-label"
                    style={{ display:'flex', justifyContent:'space-between', alignItems:'center', cursor:'pointer', userSelect:'none' }}
                    onClick={() => setWorkspacesCollapsed(c => !c)}>
                    <span>WORKSPACES</span>
                    <span style={{ fontSize:10, opacity:0.6, marginLeft:4 }}>{workspacesCollapsed ? '▶' : '▼'}</span>
                  </div>
                  {!workspacesCollapsed && (
                    <>
                      {sidebarData?.workspaces?.length > 0 ? (
                        sidebarData.workspaces.map(ws => (
                          <WorkspaceNode key={ws.id} node={ws} depth={0}
                            expanded={expandedNodes} setExpanded={setExpandedNodes}
                            onSend={doSend} loadWorkspaceTree={loadWorkspaceTree} />
                        ))
                      ) : (
                        <>
                          <div className="sidebar-item" onClick={() => doSend('List all my Smartsheet workspaces')}>
                            <span className="item-icon">🏢</span>
                            <span className="item-label">My Workspaces</span>
                          </div>
                          <div className="sidebar-item" onClick={() => doSend('Show all sheets I have access to')}>
                            <span className="item-icon">📋</span>
                            <span className="item-label">All Sheets</span>
                          </div>
                        </>
                      )}
                    </>
                  )}
                </div>

                {/* CHAT HISTORY */}
                {chatSessions.length > 0 && (
                  <>
                    <div className="sidebar-divider" />
                    <div className="sidebar-section">
                      <div className="sidebar-label" style={{ display:'flex', justifyContent:'space-between', alignItems:'center', cursor:'pointer' }}
                        onClick={() => setSessionsCollapsed(c => !c)}>
                        <span>CHAT HISTORY</span>
                        <span style={{ fontSize:10, opacity:0.6 }}>{sessionsCollapsed ? '▶' : '▼'}</span>
                      </div>
                      {!sessionsCollapsed && (
                        <>
                          {(showAllSessions ? chatSessions : chatSessions.slice(0, 10)).map(s => (
                            <div key={s.id} className="sidebar-item" style={{ paddingRight:4, position:'relative' }}
                              title={s.title}>
                              {editingSessionId === s.id ? (
                                <input
                                  autoFocus
                                  value={editingTitle}
                                  onChange={e => setEditingTitle(e.target.value)}
                                  onBlur={() => { renameSession(s.id, editingTitle); setEditingSessionId(null); }}
                                  onKeyDown={e => { if(e.key==='Enter'){renameSession(s.id,editingTitle);setEditingSessionId(null);} if(e.key==='Escape')setEditingSessionId(null); }}
                                  onClick={e => e.stopPropagation()}
                                  style={{ width:'100%', fontSize:12, border:'1px solid #f0d5be', borderRadius:4, padding:'2px 6px', background:'#fff', outline:'none' }}
                                />
                              ) : (
                                <>
                                  <span className="item-icon" style={{fontSize:11}}>💬</span>
                                  <span className="item-label" style={{fontSize:12, flex:1}}
                                    onClick={() => loadHistorySession(s)}>
                                    {s.title || 'Chat'}
                                  </span>
                                  <div style={{display:'flex', gap:2, flexShrink:0}}>
                                    <span style={{fontSize:10, cursor:'pointer', opacity:0.5, padding:'0 3px'}}
                                      title="Rename"
                                      onClick={e => {e.stopPropagation();setEditingSessionId(s.id);setEditingTitle(s.title||'');}}>✏️</span>
                                    <span style={{fontSize:10, cursor:'pointer', opacity:0.5, padding:'0 3px'}}
                                      title="Delete"
                                      onClick={e => {e.stopPropagation();if(window.confirm('Delete this chat?'))deleteSession(s.id);}}>🗑️</span>
                                  </div>
                                </>
                              )}
                            </div>
                          ))}
                          {chatSessions.length > 10 && (
                            <div className="sidebar-item" onClick={() => setShowAllSessions(s => !s)}
                              style={{ opacity:0.6, fontSize:12, justifyContent:'center' }}>
                              {showAllSessions ? '▲ Show less' : `▼ Show all ${chatSessions.length} chats`}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </>
                )}

                {sidebarSections.map((section, si) => (
                  <div key={si}>
                    <div className="sidebar-divider" />
                    <div className="sidebar-section">
                      <div className="sidebar-label">{section.section}</div>
                      {section.items.map((item, ii) => (
                        <div key={ii}
                          className={`sidebar-item ${item.type === 'action' ? 'sidebar-action' : ''}`}
                          onClick={() => doSend(item.prompt)}
                          title={item.label}>
                          <span className="item-icon">{item.icon}</span>
                          <span className="item-label">{item.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}

                <div className="sidebar-divider" />
                <div className="sidebar-item" onClick={reloadSidebar} style={{ opacity: 0.6 }}>
                  <span className="item-icon">🔄</span>
                  <span>Refresh</span>
                </div>
              </>
            )}
            {/* Resize handle */}
            <div
              onMouseDown={startResize}
              style={{
                position: 'absolute', right: 0, top: 0, bottom: 0,
                width: 4, cursor: 'col-resize', zIndex: 10,
                background: 'transparent',
              }}
              onMouseEnter={e => e.currentTarget.style.background = '#e8c4a0'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            />
          </aside>
        )}

        {/* CHAT */}
        <div className="chat-area">
          <div className="messages">
            {messages.map((msg) => (
              <div key={msg.id} className={`msg-group ${msg.role}`}>
                {msg.role === 'assistant' && (
                  <div className="msg-avatar ai">AI</div>
                )}
                <div className="msg-body">
                  {msg.tool_calls?.length > 0 && (
                    <ToolStrip tools={msg.tool_calls} />
                  )}
                  <MessageBubble role={msg.role} content={msg.content} />
                  {msg.followups?.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8, maxWidth: 520 }}>
                      {msg.followups.map((fu, i) => (
                        <button key={i}
                          onClick={() => doSend(fu)}
                          style={{
                            background: '#fff3ea',
                            border: '1px solid #e8c4a0',
                            borderRadius: 20,
                            padding: '5px 12px',
                            fontSize: 12,
                            color: '#7a4f30',
                            cursor: 'pointer',
                            textAlign: 'left',
                            lineHeight: 1.4,
                            transition: 'background 0.15s',
                          }}
                          onMouseEnter={e => e.target.style.background = '#ffe8d6'}
                          onMouseLeave={e => e.target.style.background = '#fff3ea'}
                        >
                          {fu}
                        </button>
                      ))}
                    </div>
                  )}
                  {msg.infographics?.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
                      {msg.infographics.map((ig, i) => <InfographicCard key={i} data={ig} />)}
                    </div>
                  )}
                  {msg.input_form && (
                    <FormCard
                      form={msg.input_form}
                      onSubmit={async (form, values) => {
                        const entries = Object.entries(values).filter(([k,v]) => v !== '' && v !== false && v !== null && v !== undefined);
                        const summary = entries.map(([k,v]) => `${k}: ${v}`).join(', ');
                        const prompt = form.type === 'new_row'
                          ? `Create a new row in sheet "${form.sheet_name}" (sheet_id: ${form.sheet_id}) with these values: ${summary}`
                          : form.type === 'email_input'
                          ? `Send the email/update request with these details: ${summary}`
                          : `Submit form "${form.title}" with: ${summary}`;
                        doSend(prompt);
                      }}
                      onCancel={() => {
                        setMessages(prev => prev.map(m =>
                          m.id === msg.id ? { ...m, input_form: null } : m
                        ));
                      }}
                    />
                  )}
                  {msg.dashboard_data && <DashboardCard data={msg.dashboard_data} />}
                  {msg.chart_data && !msg.dashboard_data && <ChartCard data={msg.chart_data} />}
                  {msg.needs_confirmation && pendingConfirmation?.msgId === msg.id && (
                    <ConfirmCard
                      message="This will make changes to your Smartsheet workspace."
                      onConfirm={handleConfirm}
                      onCancel={handleCancel}
                    />
                  )}
                  {msg.processing_time_ms && msg.role === 'assistant' && (
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', paddingLeft: 4 }}>
                      {(msg.processing_time_ms / 1000).toFixed(1)}s
                    </div>
                  )}
                </div>
                {msg.role === 'user' && (
                  <div className="msg-avatar user-av">P</div>
                )}
              </div>
            ))}

            {/* Live status indicator — driven by real backend SSE events */}
            {isLoading && <AgentStatusIndicator events={streamEvents} />}
            <div ref={bottomRef} />
          </div>

          {messages.length === 1 && (
            <div className="suggestions">
              <div className="suggestions-label">Quick start</div>
              <div className="suggestions-grid">
                {QUICK_PROMPTS.map((p, i) => (
                  <button key={i} className="suggestion-chip"
                    onClick={() => doSend(p.text)}>
                    <span>{p.icon}</span>
                    <span>{p.text}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* INPUT */}
          <div className="input-area">
            <div className="input-row">
              {voiceSupported && (
                <button className={`mic-btn ${isRecording ? 'recording' : ''}`}
                  onClick={handleVoice}
                  title={isRecording ? 'Stop recording' : 'Voice input'}>
                  {isRecording ? '⏹' : '🎤'}
                </button>
              )}
              <textarea
                ref={el => { textareaRef.current = el; inputRef.current = el; }}
                className="input-textarea"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Ask about your projects, metrics, or give an instruction..."
                rows={1}
                disabled={isLoading}
              />
              <button className="send-btn"
                onClick={() => doSend()}
                disabled={isLoading || !input.trim()}>
                ↑
              </button>
            </div>
            <div className="input-footer">
              <span className="input-hint">Enter to send</span>
              <span className="input-hint">·</span>
              <span className="input-hint">Shift+Enter for new line</span>
              <span className="input-hint">·</span>
              <span className="input-hint">Connected via Smartsheet API</span>
            </div>
          </div>
        </div>
      </div>

      {/* Voice overlay */}
      {isListening && !isRecording && (
        <div className="voice-overlay" onClick={() => setIsListening(false)}>
          <div className="voice-modal">
            <div className="voice-ring" onClick={stopRecording}>🎤</div>
            <div className="voice-label">Listening...</div>
            <div className="voice-hint">Speak your question, then it will auto-send</div>
          </div>
        </div>
      )}
    </div>
    {showAdmin && <AdminPanel token={getToken()} onClose={() => setShowAdmin(false)} />}
    </>
  );
}