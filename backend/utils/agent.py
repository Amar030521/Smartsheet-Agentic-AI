"""
Agent Orchestration Layer - with rate limit retry handling
"""
import json
import re
import sys
import os
import time
import anthropic
from typing import Optional, Generator

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'mcp'))
from smartsheet_mcp_server import MCP_TOOLS, execute_tool

from utils.config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_anthropic_client: Optional[anthropic.Anthropic] = None


def get_anthropic_client() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


SYSTEM_PROMPT = """You are a Chief Portfolio Intelligence Officer embedded in Smartsheet. You advise founders and directors. You have three modes — detect from query intent automatically.

TODAY: {today}

═══════════════════════════════════════
STEP 0 — DETECT USER CONTEXT FIRST
═══════════════════════════════════════
Before doing anything else, determine WHERE the user is and WHAT SCOPE they are asking about.
This controls which tools you call and what you include in the response.

CONTEXT LEVEL 1 — GLOBAL (no workspace mentioned, no prior context in conversation)
Signals: "give me a summary", "what do I have", "overview of everything", "what's going on"
→ call list_workspaces → for each workspace call get_workspace_contents(shallow=True) → for each workspace call get_sheet_summary on its most important sheets
→ Summarise ACROSS all workspaces: what each workspace is for, key activity, headline numbers

CONTEXT LEVEL 2 — INSIDE A SPECIFIC WORKSPACE
Signals: workspace name or ID in message OR user just navigated into a workspace in the conversation
Examples: "give me summary of Professional Certificate workspace", "what's in this workspace", "summarise this workspace"
→ call get_workspace_contents(shallow=False) to get full folder/sheet tree
→ call get_folder_contents for each folder inside the workspace
→ call get_sheet_summary on EVERY sheet found — read the actual data
→ Summarise ONLY that workspace: what each folder/project is doing, statuses, key numbers, what is actually happening inside

CONTEXT LEVEL 3 — INSIDE A PROJECT/FOLDER
Signals: folder name, project name, or folder_id mentioned OR user is in a folder context from the conversation
Examples: "give me summary of BP folder", "what's happening in this project", "summarise this project"
→ call get_folder_contents(folder_id) to get all sheets in that folder
→ call get_sheet_summary on EVERY sheet in the folder — read actual data, not just names
→ call get_sheet_with_links if any sheet has cross-sheet references — resolve and include linked data
→ Summarise ONLY that folder/project: what each sheet tracks, current statuses, key findings from actual row data

CONTEXT LEVEL 4 — INSIDE A SPECIFIC SHEET
Signals: sheet name or sheet_id mentioned, or "this sheet", "this tracker", "this report"
Examples: "summarise this sheet", "what's in the budget tracker", "give me summary of Rubric Sheet"
→ call get_sheet_summary(sheet_id) for analytical data
→ call get_sheet(sheet_id) if you need full row detail for the summary
→ call list_cross_sheet_references to find and resolve linked data
→ call get_sheet_with_links if cross-sheet links exist
→ Summarise ONLY that sheet: purpose of the sheet, what it tracks, current values, key patterns, what the data is telling you

CRITICAL SCOPING RULES:
- NEVER include data from outside the user's current context
- If user says "this workspace" — only that workspace, nothing else
- If user says "this project" or "this folder" — only sheets inside that folder
- If user says "this sheet" — only that sheet
- If context is ambiguous — ask one clarifying question: "Are you asking about [workspace name] specifically, or everything?"
- ALWAYS read actual sheet content (get_sheet_summary at minimum) — never give a summary based on names/counts alone
- Cross-sheet references must be resolved — call get_sheet_with_links and list_cross_sheet_references when sheets link to other sheets

═══════════════════════════════════════
THREE RESPONSE MODES — DETECT FROM QUERY
═══════════════════════════════════════

MODE 1 — EXECUTIVE BRIEF (default for summary queries)
Triggers: "status", "portfolio", "what is", "how many", "which projects", "overdue", "summary", "quick", "show me the status", "give me a summary", "overview", "what's going on"

Structure:
**🔴/🟡/🟢 [Headline — single most critical finding from the actual data, quantified]**
- [Finding 1: what this workspace/project/sheet is actually doing + key number]
- [Finding 2: status or health finding with metric]
- [Finding 3: pattern, risk, or concentration]
- [What is working — if data shows it]
- [Recommended immediate action]
[Max 5 bullets. No paragraphs. No sub-headers.]
DASHBOARD::{{...}}
FOLLOWUPS::["<specific action>","<specific drill-down>","<specific action>"]

For SUMMARY queries specifically — the response must answer:
- What is this workspace/project/sheet actually ABOUT (purpose, domain)
- What is currently HAPPENING (statuses, active work, counts)
- What are the KEY NUMBERS (budget, timelines, completion %)
- What needs ATTENTION (risks, delays, blockers)
Do NOT just list file/sheet names. Read the data and explain what the work actually IS.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MODE 2 — DATA TABLE (when user wants to see actual records)
Triggers: "list all", "list the", "show all", "show me all", "give me all", "list projects", "list items", "list rows", "all projects", "full list", "every project"

Structure:
**[Brief 1-line intel headline with the single most important flag]**
✅ [What is working — one line, specific]
⚠️ [Key bottleneck or risk — one line, specific]
🔴 [Most critical issue — one line, specific]

[Then the FULL markdown table — every row, all key columns]
| Project ID | Name | Dept | PM | Budget | Status | Bottleneck |
|---|---|---|---|---|---|---|
[All rows from the sheet — do not summarise or skip any]

DASHBOARD::{{...}}
FOLLOWUPS::["<action on specific row>","<filter by bottleneck>","<escalate specific issue>"]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MODE 3 — DEEP ANALYSIS (explicit request for detail)
Triggers: "deep dive", "detailed analysis", "explain", "break down", "full report", "investigate", "why", "root cause", "comprehensive", "walk me through"

ALWAYS cover ALL of these sections — skip only if data truly unavailable:

**🔴/🟡/🟢 [Project/Topic] — [single most critical finding, quantified, one line]**

### Root Cause Analysis
What is actually broken and WHY — not just symptoms. Pattern: "X because Y — evidence: Z"
Example: "486-day delay because Systems/IT has 0% progress with no scheduled dates — planning abandoned, not execution failure"

### Critical Findings
3-5 numbered findings, each: metric + comparison + business impact
Always cover: timeline status, budget status, data integrity issues, governance gaps
Flag contradictions: "84% progress but actual end date Oct 2025 = marked closed while still active"

### Phase / Workstream Performance
Each phase: completion % + what is blocking + days ahead or behind
Flag 0% phases with missing dates — these are abandoned, not pending

### Budget & Financial Health
Budgeted vs actual vs variance with % overrun
Flag #INVALID formulas, identical actuals across projects (data integrity broken)
State burn rate: "X% of budget consumed with Y% of work remaining — unsustainable"

### Risk & RAID Exposure
List all open RAID items: type + description + days overdue + owner role
Pattern finding: "All 3 RAID items 500+ days overdue — log abandoned mid-project"

### Recommended Actions
1. [Specific action] — [Owner role, not email] — [Timeline: immediate/this week/48 hours]
2. [Specific action] — [Owner role] — [Timeline]
3. [Specific action] — [Owner role] — [Timeline]

[NO DASHBOARD in Mode 3 — offer as followup pill instead]
FOLLOWUPS::["Show this analysis as a dashboard","[Specific drill-down from findings above]","[Specific action from recommendations above]"]

CHARACTER / LENGTH RULES:
- Mode 1: max 5 bullets, each max 120 chars
- Mode 2: intel = max 3 one-liners + full table (all rows, no omissions)
- Mode 3: max 4 sections, max 3 sentences per section
- Every mode: FOLLOWUPS:: is always the absolute last line

═══════════════════════════════════════
INTELLIGENCE RULES — ALL MODES
═══════════════════════════════════════
Every finding must have: [metric] + [comparison/pattern] + [business impact]

NEVER: "Several projects are delayed"
ALWAYS: "4/4 projects delayed avg +370 days — ₹262K of active spend with no delivery date"

NEVER: "Budget data may be inaccurate"
ALWAYS: "Identical $67,490 actual for all 4 — data integrity broken, variance unreliable"

Pattern language:
- "X of Y (Z%) — systemic, not isolated"
- "Avg 18% overrun on 3/4 projects in this division — pattern not anomaly"
- "[Name] = PM + Director + VP — single point of failure, ₹291K with zero backup"

In Mode 2 tables, add a Bottleneck column if data allows — populate with:
- "VP approval missing", "No PM assigned", "Data error: #NO MATCH", "Not provisioned", "On track ✅"

What is working (always surface when present):
- "Pre-Work 97% done — only phase on track"
- "ANP006: only green project, on time and on budget"

═══════════════════════════════════════
DASHBOARD RULES
═══════════════════════════════════════
Mode 1 + Mode 2: Always output DASHBOARD:: — never skip, never wait to be asked.
Mode 3: Never output DASHBOARD:: — put "Show this analysis as a dashboard" in FOLLOWUPS::.

Data: get_sheet_summary → column_analysis.value_counts → compute percentages yourself.
Scale: simple = 2-3 KPIs + 1-2 panels | portfolio = 4-6 KPIs + 3-4 panels
Every panel needs real computed insight + alert — never placeholder text.

Chart selection — NEVER output a panel without actual data:
- stacked_bar: status/approval per group | pie: distribution ≤6 slices
- bar: cross-division comparison | waterfall: budget variance
- gantt: timelines | india_map: Indian state data | Max 4 panels

CRITICAL PANEL RULES:
1. NEVER output a panel with empty labels:[] or values:[] — skip it entirely
2. NEVER output a panel if you cannot populate real numbers from the data
3. Every panel MUST have at minimum: title + chart_type + labels (≥2 items) + values/datasets
4. If you only have insight text but no chart data — do NOT create a panel, put the insight in the KPI sub field instead
5. Better to have 2 strong panels than 4 panels where 2 are empty

PANEL VALIDATION before outputting:
- labels array has ≥2 items? ✅ include panel
- values array matches labels length? ✅ include panel
- labels:[] or values:[]? ❌ skip panel entirely
- Only have insight text, no data? ❌ skip panel, add insight to a KPI card instead

FORMAT:
DASHBOARD::{"title":"...","subtitle":"...","source":"...","as_of":"...","kpis":[{"label":"...","value":"...","sub":"...","delta":"...","status":"good|warn|bad"}],"panels":[{"title":"...","chart_type":"bar","labels":["A","B","C"],"values":[10,20,30],"insight":"[computed numbers]","alert":"[risk + urgency]"}]}

═══════════════════════════════════════
ACTIONABILITY
═══════════════════════════════════════
After showing data or risks, immediately offer to act.
Tools available: send_row_email, request_row_update, rollout_project, update_row, create_row.
Before rollout: check division overrun history → warn and recommend buffer.

═══════════════════════════════════════
FORMS & ROW CREATION
═══════════════════════════════════════
Never ask field by field. get_sheet_by_name → use form_fields → FORM::
Skip auto_status_fields (Status, Approval, Provisioned) — shown in info box only.
FORM::{"type":"new_row","title":"...","sheet_id":"...","sheet_name":"...","submit_label":"Create Row","auto_fields":["Status"],"fields":[{"name":"...","label":"...","field_type":"text|select|date|contact|checkbox|number","required":true,"options":["..."]}]}

═══════════════════════════════════════
TOOL RULES
═══════════════════════════════════════
1. get_sheet_by_name(name, workspace_id) — always pass workspace_id
2. For "list all" queries: call get_sheet (not get_sheet_summary) to get all actual rows
3. Multiple matches → list and confirm
4. Delete / rollout → CONFIRM_REQUIRED
5. Dashboards → get_sheet_summary (not get_sheet)

AUTOMATION API LIMITATION:
- Smartsheet API CANNOT create new automation rules — this is an official, permanent API limitation
- create_automation tool will always return success=False with the config to create manually
- When this happens: respond with ONE clean block showing the config, NOT a long tutorial
  Example: "⚠️ Smartsheet API doesn't support creating automations — here's the config to set up manually (Automation → Create Workflow):" then show the config_to_create as a simple list
- What CAN be done via API: list_automations, update_automation (message/recipients/enable), delete_automation

DISPLAY RULES — clean output only:
- NEVER display sheet IDs, row IDs, workspace IDs, or any numeric Smartsheet IDs
- NEVER display raw email addresses — show the person's name instead, never the email string
- Use names only: "Budget Tracking", "BP Folder", "Professional Certificate Workspace"
- IDs and emails are for internal tool use only — invisible to the user

CONTACT ACCURACY RULES — CRITICAL, NEVER VIOLATE:
- NEVER guess, infer, or assume a person's name or role from context
- ONLY report a person as PM/Lead/Owner if that specific field in the sheet EXPLICITLY contains their name
- If the Project Manager field is empty or unclear — say "Project Manager not assigned" — NEVER substitute another name found elsewhere in the sheet
- A person appearing in task rows, assignee columns, or other sheets does NOT make them the PM of this project
- If you need someone's email for an action and it is not in the current sheet — ask the user: "I don't have [Name]'s email in this sheet. Could you provide it?" — NEVER pull email from another sheet or workspace

═══════════════════════════════════════
INFOGRAPHICS — INLINE VISUAL BLOCKS
═══════════════════════════════════════
Use INFOGRAPHIC:: blocks to render visual elements INSIDE the message — not as separate dashboards.
Place them naturally within the response where they add clarity.

WHEN TO USE (automatically, without being asked):
- Phase/workstream completion → progress_bars or progress_rings
- Portfolio health metrics at the top of any analysis → stat_grid
- Approval pipeline status → pipeline
- Budget vs actual comparison → comparison_bars  
- RAID items list → risk_matrix
- Overall scorecard → health_score

FORMAT (one per visual element, placed inline in text):
INFOGRAPHIC::{"type":"progress_bars","title":"Phase Completion","bars":[{"label":"Pre-Work","pct":97,"status":"good","note":"148 days early"},{"label":"Operations","pct":84,"status":"warn"},{"label":"Systems/IT","pct":35,"status":"bad","note":"critical blocker"},{"label":"HR","pct":17,"status":"bad","note":"abandoned"}]}

INFOGRAPHIC::{"type":"stat_grid","title":"Portfolio Snapshot","items":[{"label":"Total Projects","value":"12","sub":"7 approved, 5 pending","status":"neutral"},{"label":"Budget","value":"$612K","sub":"64% in Manufacturing","status":"warn"},{"label":"Provisioned","value":"5/7","sub":"2 approved not deployed","status":"warn"},{"label":"Approval Rate","value":"58%","sub":"5 stuck at VP","status":"bad"}]}

INFOGRAPHIC::{"type":"pipeline","title":"Approval Pipeline","stages":[{"label":"Submitted","count":12,"color":"blue"},{"label":"Director Approved","count":7,"color":"orange"},{"label":"VP Approved","count":3,"color":"red"},{"label":"Provisioned","count":5,"color":"green"}]}

INFOGRAPHIC::{"type":"comparison_bars","title":"Budget vs Actual","label1":"Budget","label2":"Actual","bars":[{"label":"ANP003 Pharmed","value1":56844,"value2":67490,"variance":"+19%"},{"label":"ANP005 Synergy","value1":60000,"value2":67490,"variance":"+12%"}]}

INFOGRAPHIC::{"type":"risk_matrix","title":"Open RAID Items","items":[{"type":"Action","description":"Client resources for UAT","severity":"bad","owner":"PM","days_overdue":573},{"type":"Issue","description":"Key team member unavailable","severity":"bad","owner":"PM","days_overdue":569}]}

INFOGRAPHIC::{"type":"health_score","title":"Project Health Scorecard","metrics":[{"label":"Schedule","value":"486 days late","status":"bad"},{"label":"Budget","value":"+19% over","status":"bad"},{"label":"Progress","value":"84%","status":"warn"},{"label":"Data Integrity","value":"#INVALID errors","status":"bad"}],"score":12}

RULES:
- Place INFOGRAPHIC:: blocks BETWEEN sections of text, not all at the end
- Mode 1 (Executive Brief): use stat_grid after headline, maybe 1 more
- Mode 2 (Data Table): use pipeline or stat_grid at top
- Mode 3 (Deep Analysis): use progress_bars for phases, comparison_bars for budget, risk_matrix for RAID
- Never use INFOGRAPHIC:: for things better shown in DASHBOARD:: (full charts with axes)
- Keep data accurate — use real numbers from tool results

═══════════════════════════════════════
FOLLOWUPS — ABSOLUTE LAST LINE
═══════════════════════════════════════
Always the very last line. Always 3 options. Always specific to what was just shown.

Mode 1: FOLLOWUPS::["<action on finding>","<drill-down on finding>","<action>"]
Mode 2: FOLLOWUPS::["<action on specific row/project from table>","<filter table by bottleneck>","<provision or escalate specific item>"]
Mode 3: FOLLOWUPS::["Show this analysis as a dashboard","<investigate specific risk>","<escalate to specific person>"]

NEVER write follow-up questions as plain text in the response body.
NEVER say "Would you like me to..." — that goes in FOLLOWUPS:: only."""


def _serialize_content(content_blocks) -> list:
    """Convert Anthropic content blocks to plain dicts for session storage."""
    result = []
    for block in content_blocks:
        if hasattr(block, 'type'):
            if block.type == "text":
                result.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                result.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })
        elif isinstance(block, dict):
            result.append(block)
    return result


def _call_claude_with_retry(client, model, max_tokens, system, tools, messages, max_retries=4):
    """Call Claude API with exponential backoff on rate limit and overloaded errors."""
    for attempt in range(max_retries):
        try:
            return client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=tools,
                messages=messages
            )
        except anthropic.RateLimitError as e:
            if attempt == max_retries - 1:
                raise e
            wait_time = (2 ** attempt) * 5  # 5s, 10s, 20s, 40s
            logger.warning(f"Rate limit hit, retrying in {wait_time}s...", attempt=attempt+1)
            time.sleep(wait_time)
        except anthropic.APIStatusError as e:
            error_str = str(e).lower()
            is_retryable = (
                "rate_limit" in error_str or
                "overloaded" in error_str or
                "529" in error_str or
                "overloaded_error" in error_str
            )
            if is_retryable and attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 8  # 8s, 16s, 32s for overloaded
                logger.warning(f"API overloaded/rate-limited, retrying in {wait_time}s...", attempt=attempt+1, error=str(e)[:100])
                time.sleep(wait_time)
            else:
                raise e


def _tool_display_name(tool_name: str) -> str:
    display = {
        "list_workspaces": "📁 Listing workspaces",
        "get_workspace_contents": "📂 Loading workspace",
        "list_sheets": "📋 Listing sheets",
        "get_sheet": "📊 Fetching sheet data",
        "get_sheet_by_name": "📊 Fetching sheet data",
        "get_sheet_summary": "📊 Summarising sheet",
        "filter_rows": "🔍 Filtering rows",
        "aggregate_column": "📈 Computing metrics",
        "get_project_status_summary": "🎯 Analyzing project status",
        "get_sheet_with_links": "🔗 Resolving linked data",
        "list_cross_sheet_references": "🔗 Listing cross-sheet references",
        "get_linked_sheet_value": "🔗 Fetching linked value",
        "search_sheets": "🔍 Searching sheets",
        "find_contact_in_sheet": "👤 Finding contact",
        "create_row": "➕ Creating row",
        "update_row": "✏️ Updating row",
        "delete_row": "🗑️ Deleting row",
        "list_dashboards": "🖥️ Listing dashboards",
        "get_dashboard": "🖥️ Loading dashboard",
        "create_dashboard": "🆕 Creating dashboard",
        "add_widget_to_dashboard": "🖥️ Adding widget",
        "list_automations": "⚙️ Listing automations",
        "create_automation": "⚙️ Creating automation",
        "update_automation": "⚙️ Updating automation",
        "delete_automation": "⚙️ Deleting automation",
        "list_scc_programs": "🎯 Loading SCC programs",
        "list_blueprints": "📐 Fetching blueprints",
        "rollout_project": "🚀 Rolling out project",
        "list_scc_projects": "📌 Listing SCC projects",
        "create_webhook": "🔔 Creating webhook",
        "list_webhooks": "🔔 Listing webhooks",
        "send_row_email": "📧 Sending email",
        "request_row_update": "📧 Requesting update",
    }
    return display.get(tool_name, f"⚙️ {tool_name.replace('_', ' ').title()}")


def run_agent_stream(messages: list, user_message: str, smartsheet_token: str = None) -> Generator[dict, None, None]:
    """
    Streaming version of run_agent — yields real-time status events as the agent works.
    Yields dicts: { "type": "status"|"tool"|"done"|"error", ...fields }
    The final "done" event contains the full result identical to run_agent().
    The existing run_agent() is untouched — this is additive only.
    """
    from datetime import date, timedelta
    today = date.today()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)

    date_context = f"""

CURRENT DATE CONTEXT (use these exact values — never guess):
- Today: {today.strftime('%Y-%m-%d')} ({today.strftime('%A, %d %B %Y')})
- Tomorrow: {tomorrow.strftime('%Y-%m-%d')}
- Yesterday: {yesterday.strftime('%Y-%m-%d')}
- Current month: {today.strftime('%B %Y')}
- Current year: {today.year}
When user says "today", "tomorrow", "yesterday", "this week", "next week" — use these exact dates."""

    dynamic_system = SYSTEM_PROMPT + date_context
    client = get_anthropic_client()
    messages.append({"role": "user", "content": user_message})

    MAX_PAIRS = 10
    if len(messages) > MAX_PAIRS * 2:
        trimmed = messages[-(MAX_PAIRS * 2):]
        start = 0
        for i, msg in enumerate(trimmed):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    start = i
                    break
        messages = trimmed[start:]

    _DATA_TOOLS = {"get_sheet_summary", "filter_rows", "aggregate_column",
                   "get_project_status_summary", "get_sheet", "get_sheet_by_name",
                   "get_sheet_with_links", "find_contact_in_sheet"}

    for msg in messages:
        if msg.get("role") == "user" and isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    cs = block.get("content", "")
                    _tid = block.get("tool_use_id", "")
                    _tname = ""
                    for _msg in messages:
                        if isinstance(_msg.get("content"), list):
                            for _b in _msg["content"]:
                                if isinstance(_b, dict) and _b.get("type") == "tool_use" and _b.get("id") == _tid:
                                    _tname = _b.get("name", "")
                    _trunc_limit = 4000 if _tname in _DATA_TOOLS else 1500
                    if isinstance(cs, str) and len(cs) > _trunc_limit:
                        block["content"] = cs[:_trunc_limit] + "...[truncated for token efficiency]"

    tool_calls_made = []
    chart_data = None
    needs_confirmation = False
    final_text = ""
    iteration = 0
    max_iterations = 8

    yield {"type": "status", "text": "Thinking...", "icon": "🤖"}

    try:
        while iteration < max_iterations:
            iteration += 1

            yield {"type": "status", "text": "Calling AI model...", "icon": "🤖"}

            response = _call_claude_with_retry(
                client=client,
                model=settings.claude_model,
                max_tokens=settings.claude_max_tokens,
                system=dynamic_system,
                tools=MCP_TOOLS,
                messages=messages
            )

            text_blocks = [b for b in response.content if b.type == "text"]
            tool_blocks = [b for b in response.content if b.type == "tool_use"]

            messages.append({
                "role": "assistant",
                "content": _serialize_content(response.content)
            })

            if response.stop_reason == "end_turn" or not tool_blocks:
                final_text = "\n".join(b.text for b in text_blocks)
                yield {"type": "status", "text": "Preparing response...", "icon": "✍️"}

                if "FOLLOWUPS::" not in final_text and final_text.strip():
                    is_deep = "###" in final_text or len(final_text) > 2000
                    is_table = "|---|" in final_text or "| --- |" in final_text
                    if is_deep and not is_table:
                        final_text = final_text.rstrip() + '\nFOLLOWUPS::["Show this analysis as a dashboard","Deep dive into the highest risk finding","Send escalation to relevant stakeholders"]'
                    elif is_table:
                        final_text = final_text.rstrip() + '\nFOLLOWUPS::["Filter to items with bottlenecks only","Provision the approved but undeployed projects","Send update requests to stuck PMs"]'
                    else:
                        final_text = final_text.rstrip() + '\nFOLLOWUPS::["Show this as a dashboard","Filter to critical items only","Send update requests to delayed PMs"]'
                break

            tool_results = []
            for tb in tool_blocks:
                tool_name = tb.name
                tool_input = tb.input
                display = _tool_display_name(tool_name)

                yield {"type": "tool", "tool": tool_name, "display": display, "icon": display.split()[0] if display else "⚙️"}

                tool_calls_made.append({"tool": tool_name, "input": tool_input, "display": display})
                result = execute_tool(tool_name, tool_input, smartsheet_token=smartsheet_token)

                if isinstance(result, dict) and "chart_data" in result and not chart_data:
                    chart_data = result["chart_data"]

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tb.id,
                    "content": json.dumps(result, default=str)
                })

            messages.append({"role": "user", "content": tool_results})

        # Fallback if loop exhausted
        if not final_text.strip():
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    content_blocks = msg.get("content", [])
                    if isinstance(content_blocks, list):
                        texts = [b.get("text", "") for b in content_blocks if isinstance(b, dict) and b.get("type") == "text"]
                        if texts:
                            final_text = "\n".join(t for t in texts if t)
                            break
            if not final_text.strip():
                tool_names = [t["display"] for t in tool_calls_made]
                final_text = f"I ran {len(tool_calls_made)} operations ({', '.join(tool_names)}) but couldn't complete the response. Please try again."

        # Parse CHART::
        if "CHART::" in final_text:
            try:
                chart_start = final_text.index("CHART::") + 7
                brace_count = 0
                chart_end = chart_start
                for i, c in enumerate(final_text[chart_start:], chart_start):
                    if c == "{": brace_count += 1
                    elif c == "}":
                        brace_count -= 1
                        if brace_count == 0: chart_end = i + 1; break
                raw_chart = json.loads(final_text[chart_start:chart_end])
                if "datasets" in raw_chart and "values" not in raw_chart:
                    raw_chart["values"] = raw_chart["datasets"][0].get("values", [])
                chart_data = raw_chart
                final_text = (final_text[:final_text.index("CHART::")] + final_text[chart_end:]).strip()
            except Exception:
                try: final_text = final_text[:final_text.index("CHART::")].strip()
                except Exception: pass

        # Parse DASHBOARD::
        dashboard_data = None
        if "DASHBOARD::" in final_text:
            try:
                db_idx = final_text.index("DASHBOARD::")
                obj_start = final_text.index("{", db_idx + 11)
                brace_count = 0
                obj_end = obj_start
                for i, c in enumerate(final_text[obj_start:], obj_start):
                    if c == "{": brace_count += 1
                    elif c == "}":
                        brace_count -= 1
                        if brace_count == 0: obj_end = i + 1; break
                dashboard_data = json.loads(final_text[obj_start:obj_end])
                final_text = (final_text[:db_idx] + final_text[obj_end:]).strip()
            except Exception:
                try: final_text = final_text[:final_text.index("DASHBOARD::")].strip()
                except Exception: pass

        # Scrub IDs and emails — strip email addresses but KEEP person names intact
        final_text = re.sub(r'\b\d{10,}\b', '[ID]', final_text)
        final_text = re.sub(r'\(?\s*(?:sheet[_\s]?id|workspace[_\s]?id|folder[_\s]?id|row[_\s]?id|id)\s*[:\-]?\s*\[ID\]\s*\)?', '', final_text, flags=re.IGNORECASE)
        final_text = re.sub(r'^\s*\[ID\]\s*$', '', final_text, flags=re.MULTILINE)
        # Remove emails in parentheses/brackets: "Name (email@x.com)" → "Name"
        final_text = re.sub(r'\s*[\(\[]\s*[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\s*[\)\]]', '', final_text)
        # Remove standalone email addresses — keep names intact
        final_text = re.sub(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b', '', final_text)
        final_text = re.sub(r'\(\s*\)', '', final_text)
        final_text = re.sub(r',\s*,', ',', final_text)
        final_text = re.sub(r'\n{3,}', '\n\n', final_text).strip()

        # Parse INFOGRAPHIC::
        infographics = []
        _ig_positions = []
        _search_pos = 0
        while True:
            _tag_idx = final_text.find('INFOGRAPHIC::', _search_pos)
            if _tag_idx == -1: break
            _brace_idx = final_text.find('{', _tag_idx)
            if _brace_idx == -1: break
            _depth = 0
            _end_idx = _brace_idx
            for _ci, _ch in enumerate(final_text[_brace_idx:], _brace_idx):
                if _ch == '{': _depth += 1
                elif _ch == '}':
                    _depth -= 1
                    if _depth == 0: _end_idx = _ci + 1; break
            _json_str = final_text[_brace_idx:_end_idx]
            try:
                _ig = json.loads(_json_str)
                infographics.append(_ig)
                _ig_positions.append((_tag_idx, _end_idx))
            except Exception: pass
            _search_pos = _end_idx
        for _start, _end in reversed(_ig_positions):
            final_text = (final_text[:_start] + final_text[_end:]).strip()
        final_text = re.sub(r'^,\s*\{[^}]*\}', '', final_text, flags=re.MULTILINE).strip()

        # Parse FORM::
        input_form = None
        if "FORM::" in final_text:
            try:
                fm_idx = final_text.index("FORM::")
                obj_start = final_text.index("{", fm_idx)
                brace_count = 0
                obj_end = obj_start
                for i, c in enumerate(final_text[obj_start:], obj_start):
                    if c == "{": brace_count += 1
                    elif c == "}":
                        brace_count -= 1
                        if brace_count == 0: obj_end = i + 1; break
                input_form = json.loads(final_text[obj_start:obj_end])
                final_text = (final_text[:fm_idx] + final_text[obj_end:]).strip()
            except Exception:
                try: final_text = final_text[:final_text.index("FORM::")].strip()
                except Exception: pass

        # Parse FOLLOWUPS::
        followups = []
        if "FOLLOWUPS::" in final_text:
            try:
                fu_idx = final_text.index("FOLLOWUPS::")
                fu_start = fu_idx + 11
                while fu_start < len(final_text) and final_text[fu_start] in (' ', '\t'):
                    fu_start += 1
                fu_end = final_text.index("]", fu_start) + 1
                raw = final_text[fu_start:fu_end].replace("'", '"')
                followups = json.loads(raw)
                if not isinstance(followups, list): followups = []
                final_text = (final_text[:fu_idx] + final_text[fu_end:]).strip()
            except Exception:
                try: final_text = final_text[:final_text.index("FOLLOWUPS::")].strip()
                except Exception: pass

        if "CONFIRM_REQUIRED" in final_text:
            needs_confirmation = True
            final_text = final_text.replace("CONFIRM_REQUIRED", "").strip()

        yield {
            "type": "done",
            "response": final_text,
            "chart_data": chart_data,
            "dashboard_data": dashboard_data,
            "input_form": input_form,
            "infographics": infographics,
            "tool_calls": tool_calls_made,
            "needs_confirmation": needs_confirmation,
            "followups": followups,
            "messages": messages,
        }

    except Exception as e:
        logger.error("Stream agent error", error=str(e), exc_info=True)
        yield {"type": "error", "message": str(e)}


async def run_agent(messages: list, user_message: str, smartsheet_token: str = None) -> dict:
    """Main agentic loop with retry handling."""
    from datetime import date, timedelta
    today = date.today()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)

    date_context = f"""

CURRENT DATE CONTEXT (use these exact values — never guess):
- Today: {today.strftime('%Y-%m-%d')} ({today.strftime('%A, %d %B %Y')})
- Tomorrow: {tomorrow.strftime('%Y-%m-%d')}
- Yesterday: {yesterday.strftime('%Y-%m-%d')}
- Current month: {today.strftime('%B %Y')}
- Current year: {today.year}
When user says "today", "tomorrow", "yesterday", "this week", "next week" — use these exact dates."""

    dynamic_system = SYSTEM_PROMPT + date_context
    client = get_anthropic_client()
    messages.append({"role": "user", "content": user_message})

    MAX_PAIRS = 10
    if len(messages) > MAX_PAIRS * 2:
        trimmed = messages[-(MAX_PAIRS * 2):]
        start = 0
        for i, msg in enumerate(trimmed):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    start = i
                    break
        messages = trimmed[start:]

    _DATA_TOOLS = {"get_sheet_summary", "filter_rows", "aggregate_column",
                   "get_project_status_summary", "get_sheet", "get_sheet_by_name",
                   "get_sheet_with_links", "find_contact_in_sheet"}

    for msg in messages:
        if msg.get("role") == "user" and isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    cs = block.get("content", "")
                    _tid = block.get("tool_use_id", "")
                    _tname = ""
                    for _msg in messages:
                        if isinstance(_msg.get("content"), list):
                            for _b in _msg["content"]:
                                if isinstance(_b, dict) and _b.get("type") == "tool_use" and _b.get("id") == _tid:
                                    _tname = _b.get("name", "")
                    _trunc_limit = 4000 if _tname in _DATA_TOOLS else 1500
                    if isinstance(cs, str) and len(cs) > _trunc_limit:
                        block["content"] = cs[:_trunc_limit] + "...[truncated for token efficiency]"

    tool_calls_made = []
    chart_data = None
    needs_confirmation = False
    final_text = ""
    iteration = 0
    max_iterations = 8

    while iteration < max_iterations:
        iteration += 1
        logger.info("Agent iteration", iteration=iteration)

        response = _call_claude_with_retry(
            client=client,
            model=settings.claude_model,
            max_tokens=settings.claude_max_tokens,
            system=dynamic_system,
            tools=MCP_TOOLS,
            messages=messages
        )

        text_blocks = [b for b in response.content if b.type == "text"]
        tool_blocks = [b for b in response.content if b.type == "tool_use"]

        messages.append({
            "role": "assistant",
            "content": _serialize_content(response.content)
        })

        if response.stop_reason == "end_turn" or not tool_blocks:
            final_text = "\n".join(b.text for b in text_blocks)
            if "FOLLOWUPS::" not in final_text and final_text.strip():
                is_deep = "###" in final_text or len(final_text) > 2000
                is_table = "|---|" in final_text or "| --- |" in final_text
                if is_deep and not is_table:
                    final_text = final_text.rstrip() + '\nFOLLOWUPS::["Show this analysis as a dashboard","Deep dive into the highest risk finding","Send escalation to relevant stakeholders"]'
                elif is_table:
                    final_text = final_text.rstrip() + '\nFOLLOWUPS::["Filter to items with bottlenecks only","Provision the approved but undeployed projects","Send update requests to stuck PMs"]'
                else:
                    final_text = final_text.rstrip() + '\nFOLLOWUPS::["Show this as a dashboard","Filter to critical items only","Send update requests to delayed PMs"]'
            break

        tool_results = []
        tool_id_map = {}
        for tb in tool_blocks:
            tool_name = tb.name
            tool_input = tb.input
            tool_id_map[tb.id] = tool_name

            logger.info("Executing tool", tool=tool_name)
            tool_calls_made.append({
                "tool": tool_name,
                "input": tool_input,
                "display": _tool_display_name(tool_name)
            })

            result = execute_tool(tool_name, tool_input, smartsheet_token=smartsheet_token)

            if isinstance(result, dict) and "chart_data" in result and not chart_data:
                chart_data = result["chart_data"]

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tb.id,
                "content": json.dumps(result, default=str)
            })

        messages.append({"role": "user", "content": tool_results})

    if not final_text.strip():
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                content_blocks = msg.get("content", [])
                if isinstance(content_blocks, list):
                    texts = [b.get("text", "") for b in content_blocks if isinstance(b, dict) and b.get("type") == "text"]
                    if texts:
                        final_text = "\n".join(t for t in texts if t)
                        break
        if not final_text.strip():
            tool_names = [t["display"] for t in tool_calls_made]
            final_text = f"I ran {len(tool_calls_made)} operations ({', '.join(tool_names)}) but couldn't complete the response. Please try again with a more specific request."

    # Parse CHART::
    if "CHART::" in final_text:
        try:
            chart_start = final_text.index("CHART::") + 7
            brace_count = 0
            chart_end = chart_start
            for i, c in enumerate(final_text[chart_start:], chart_start):
                if c == "{":
                    brace_count += 1
                elif c == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        chart_end = i + 1
                        break
            raw_chart = json.loads(final_text[chart_start:chart_end])
            if "datasets" in raw_chart and not "values" in raw_chart:
                raw_chart["values"] = raw_chart["datasets"][0].get("values", [])
            chart_data = raw_chart
            final_text = (final_text[:final_text.index("CHART::")] + final_text[chart_end:]).strip()
        except Exception as e:
            try:
                chart_idx = final_text.index("CHART::")
                final_text = final_text[:chart_idx].strip()
            except Exception:
                pass
            logger.warning("Chart parse failed", error=str(e))

    # Parse DASHBOARD::
    dashboard_data = None
    if "DASHBOARD::" in final_text:
        try:
            db_idx = final_text.index("DASHBOARD::")
            db_start_idx = db_idx + 11
            obj_start = final_text.index("{", db_start_idx)
            brace_count = 0
            obj_end = obj_start
            for i, c in enumerate(final_text[obj_start:], obj_start):
                if c == "{": brace_count += 1
                elif c == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        obj_end = i + 1
                        break
            raw_json = final_text[obj_start:obj_end]
            dashboard_data = json.loads(raw_json)
            final_text = (final_text[:db_idx] + final_text[obj_end:]).strip()
            logger.info("Dashboard parsed", panels=len(dashboard_data.get("panels", [])), kpis=len(dashboard_data.get("kpis", [])))
        except Exception as e:
            logger.warning("Dashboard parse failed", error=str(e), snippet=final_text[final_text.find("DASHBOARD::"):][:100] if "DASHBOARD::" in final_text else "")
            try:
                final_text = final_text[:final_text.index("DASHBOARD::")].strip()
            except Exception:
                pass

    # Scrub raw IDs and emails — strip emails but KEEP person names intact
    final_text = re.sub(r'\b\d{10,}\b', '[ID]', final_text)
    final_text = re.sub(r'\(?\s*(?:sheet[_\s]?id|workspace[_\s]?id|folder[_\s]?id|row[_\s]?id|id)\s*[:\-]?\s*\[ID\]\s*\)?', '', final_text, flags=re.IGNORECASE)
    final_text = re.sub(r'^\s*\[ID\]\s*$', '', final_text, flags=re.MULTILINE)
    # Remove emails in parentheses/brackets: "Name (email@x.com)" → "Name"
    final_text = re.sub(r'\s*[\(\[]\s*[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\s*[\)\]]', '', final_text)
    # Remove standalone email addresses — keep names intact
    final_text = re.sub(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b', '', final_text)
    final_text = re.sub(r'\(\s*\)', '', final_text)
    final_text = re.sub(r',\s*,', ',', final_text)
    final_text = re.sub(r'\n{3,}', '\n\n', final_text).strip()

    # Parse INFOGRAPHIC::
    infographics = []
    _ig_positions = []
    _search_pos = 0
    while True:
        _tag_idx = final_text.find('INFOGRAPHIC::', _search_pos)
        if _tag_idx == -1: break
        _brace_idx = final_text.find('{', _tag_idx)
        if _brace_idx == -1: break
        _depth = 0
        _end_idx = _brace_idx
        for _ci, _ch in enumerate(final_text[_brace_idx:], _brace_idx):
            if _ch == '{': _depth += 1
            elif _ch == '}':
                _depth -= 1
                if _depth == 0: _end_idx = _ci + 1; break
        _json_str = final_text[_brace_idx:_end_idx]
        try:
            _ig = json.loads(_json_str)
            infographics.append(_ig)
            _ig_positions.append((_tag_idx, _end_idx))
        except Exception as _e:
            logger.warning("Infographic parse failed", error=str(_e), snippet=_json_str[:80])
        _search_pos = _end_idx
    for _start, _end in reversed(_ig_positions):
        final_text = (final_text[:_start] + final_text[_end:]).strip()
    final_text = re.sub(r'^,\s*\{[^}]*\}', '', final_text, flags=re.MULTILINE).strip()

    # Parse FORM::
    input_form = None
    if "FORM::" in final_text:
        try:
            fm_idx = final_text.index("FORM::")
            obj_start = final_text.index("{", fm_idx)
            brace_count = 0
            obj_end = obj_start
            for i, c in enumerate(final_text[obj_start:], obj_start):
                if c == "{": brace_count += 1
                elif c == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        obj_end = i + 1
                        break
            input_form = json.loads(final_text[obj_start:obj_end])
            final_text = (final_text[:fm_idx] + final_text[obj_end:]).strip()
            logger.info("Form parsed", title=input_form.get("title", ""), fields=len(input_form.get("fields", [])))
        except Exception as e:
            logger.warning("Form parse failed", error=str(e))
            try:
                final_text = final_text[:final_text.index("FORM::")].strip()
            except Exception:
                pass

    # Parse FOLLOWUPS::
    followups = []
    if "FOLLOWUPS::" in final_text:
        try:
            fu_idx = final_text.index("FOLLOWUPS::")
            fu_start = fu_idx + 11
            while fu_start < len(final_text) and final_text[fu_start] in (' ', '\t'):
                fu_start += 1
            fu_end = final_text.index("]", fu_start) + 1
            raw = final_text[fu_start:fu_end]
            raw = raw.replace("'", '"')
            followups = json.loads(raw)
            if not isinstance(followups, list):
                followups = []
            final_text = (final_text[:fu_idx] + final_text[fu_end:]).strip()
        except Exception as e:
            logger.warning("Followups parse failed", error=str(e))
            try:
                final_text = final_text[:final_text.index("FOLLOWUPS::")].strip()
            except Exception:
                pass

    if "CONFIRM_REQUIRED" in final_text:
        needs_confirmation = True
        final_text = final_text.replace("CONFIRM_REQUIRED", "").strip()

    return {
        "response": final_text,
        "chart_data": chart_data,
        "dashboard_data": dashboard_data,
        "input_form": input_form,
        "infographics": infographics,
        "tool_calls": tool_calls_made,
        "needs_confirmation": needs_confirmation,
        "followups": followups,
        "messages": messages,
        "iterations": iteration
    }