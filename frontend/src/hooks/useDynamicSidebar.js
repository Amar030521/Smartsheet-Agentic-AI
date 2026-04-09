import { useState, useEffect, useCallback } from 'react';

export function useDynamicSidebar(sessionId) {
  const [sections, setSections] = useState([]);
  const [treeData, setTreeData] = useState(null);
  const [loading, setLoading] = useState(true);

  const ACTIONS_SECTION = {
    section: 'ACTIONS',
    items: [
      { icon: '➕', label: 'Add Row',         prompt: 'I want to add a new row to a sheet. Help me choose which sheet.', type: 'action' },
      { icon: '🆕', label: 'New Dashboard',   prompt: 'Create a new dashboard in my workspace', type: 'action' },
      { icon: '🚀', label: 'Rollout Project', prompt: 'Show me available Control Center programs so I can roll out a new project', type: 'action' },
      { icon: '⚙️', label: 'Automations',     prompt: 'Show me the automation rules on my sheets', type: 'action' },
    ]
  };

  const loadSidebar = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/v1/sidebar');
      const data = await res.json();

      console.log('[Sidebar] response:', data);

      // Check for valid data — workspaces array must exist
      if (data && Array.isArray(data.workspaces)) {
        setTreeData(data);

        // Build sections: recent sheets + dashboards + actions
        const built = [];

        if (data.recent_sheets?.length > 0) {
          built.push({
            section: 'RECENT SHEETS',
            items: data.recent_sheets.slice(0, 6).map(s => ({
              icon: '📋', label: s.name,
              prompt: `Show me the data from sheet "${s.name}" (sheet_id: ${s.id})`,
              id: s.id, type: 'sheet'
            }))
          });
        }

        if (data.dashboards?.length > 0) {
          built.push({
            section: 'DASHBOARDS',
            items: data.dashboards.slice(0, 5).map(d => ({
              icon: '🖥️', label: d.name,
              prompt: `Show me the dashboard "${d.name}" (sight_id: ${d.id})`,
              id: d.id, type: 'dashboard'
            }))
          });
        }

        built.push(ACTIONS_SECTION);
        setSections(built);
      } else {
        // API returned unexpected shape — use fallback with actions only
        console.warn('[Sidebar] unexpected response shape:', data);
        setTreeData(null);
        setSections([ACTIONS_SECTION]);
      }
    } catch (err) {
      console.error('[Sidebar] fetch failed:', err);
      setTreeData(null);
      setSections([ACTIONS_SECTION]);
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadWorkspaceTree = useCallback(async (workspaceId) => {
    try {
      const res = await fetch(`/api/v1/sidebar/workspace/${workspaceId}`);
      const wsData = await res.json();
      if (wsData.error) return null;
      setTreeData(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          workspaces: prev.workspaces.map(ws =>
            ws.id === workspaceId ? { ...ws, ...wsData, loaded: true } : ws
          )
        };
      });
      return wsData;
    } catch (err) {
      return null;
    }
  }, []);

  useEffect(() => {
    loadSidebar();
  }, [loadSidebar]);

  return { sections, treeData, loading, reload: loadSidebar, loadWorkspaceTree };
}