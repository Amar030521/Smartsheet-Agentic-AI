"""
Smartsheet MCP Server
─────────────────────
Exposes Smartsheet operations as MCP tools that Claude can call natively.
Run standalone:  python mcp/smartsheet_mcp_server.py
Or embedded in FastAPI via MCPClient.

Claude connects to this server and decides which tools to call
based on user intent — no hardcoded intent mapping needed.
"""
import asyncio
import json
import sys
import os
from typing import Any

# Add parent to path when running standalone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import smartsheet as ss
from utils.config import get_settings
from utils.logger import get_logger
from utils.smartsheet_client import (
    get_client, get_column_map, get_reverse_column_map,
    normalize_row, invalidate_column_cache
)

import threading
logger = get_logger(__name__)

# Per-request Smartsheet token storage — thread-safe
_request_local = threading.local()

def _get_current_client():
    """Get Smartsheet client for current request — uses per-user token if set."""
    token = getattr(_request_local, 'smartsheet_token', None)
    if token:
        from utils.smartsheet_client import get_client_for_token
        return get_client_for_token(token)
    return get_client()
settings = get_settings()


# ─── COLUMN METADATA CACHE ──────────────────────────────────────
# Avoids repeated API calls for the same sheet's column structure
_col_meta_cache: dict = {}  # sheet_id -> {col_title: col_object}
_col_meta_cache_time: dict = {}  # sheet_id -> timestamp

def get_col_meta(client, sheet_id: int) -> dict:
    """Get column metadata with caching (5 min TTL). Returns {title: col_object}."""
    import time
    now = time.time()
    sid = int(sheet_id)
    
    # Return cached if fresh (within 5 minutes)
    if sid in _col_meta_cache and (now - _col_meta_cache_time.get(sid, 0)) < 300:
        return _col_meta_cache[sid]
    
    # Try get_columns first (fast), fall back to get_sheet
    try:
        result = client.Sheets.get_columns(sid, include_all=True)
        meta = {col.title: col for col in result.data}
    except Exception as e1:
        try:
            # Fallback: get full sheet and extract columns
            sheet = client.Sheets.get_sheet(sid)
            meta = {col.title: col for col in sheet.columns}
        except Exception as e2:
            logger.error("get_col_meta failed", sheet_id=sid, error1=str(e1), error2=str(e2))
            return {}  # Return empty dict — caller handles missing columns
    
    _col_meta_cache[sid] = meta
    _col_meta_cache_time[sid] = now
    
    # Also update the column ID cache
    from utils.smartsheet_client import _column_cache
    _column_cache[sid] = {col.title: col.id_ for col in meta.values()}
    
    return meta



def safe_cell_value(cell) -> str:
    """Safely extract display value from any cell type including CONTACT_LIST, PICKLIST etc."""
    try:
        # display_value is always a plain string if present
        if cell.display_value is not None:
            return cell.display_value
        # For objectValue types (CONTACT_LIST etc), extract meaningful value
        if cell.object_value is not None:
            ov = cell.object_value
            if hasattr(ov, 'email'):
                return ov.email or str(ov)
            if hasattr(ov, 'name'):
                return ov.name or str(ov)
            if isinstance(ov, (list, tuple)):
                return ', '.join(str(x) for x in ov)
            return str(ov)
        # Plain value
        if cell.value is not None:
            return str(cell.value)
        return ''
    except Exception:
        try:
            return str(cell.value) if cell.value else ''
        except Exception:
            return ''


# ═══════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# Each function = one MCP tool Claude can call
# ═══════════════════════════════════════════════════════════════

def tool_list_workspaces() -> dict:
    """List all workspaces the user has access to."""
    client = _get_current_client()
    result = client.Workspaces.list_workspaces(include_all=True)
    return {
        "workspaces": [
            {"id": str(ws.id), "name": ws.name, "permalink": ws.permalink}
            for ws in result.data
        ],
        "count": len(result.data)
    }


def _recurse_folder(client, folder_id: int, folder_name: str, depth: int = 0) -> dict:
    """Recursively get all contents of a folder."""
    try:
        folder = client.Folders.get_folder(folder_id)
        sheets = [{"id": str(s.id), "name": s.name} for s in (folder.sheets or [])]
        reports = [{"id": str(r.id), "name": r.name} for r in (folder.reports or [])]
        dashboards = [{"id": str(s.id), "name": s.name} for s in (folder.sights or [])]
        result = {
            "folder_id": str(folder_id),
            "folder_name": folder_name,
            "sheets": sheets,
            "reports": reports,
            "dashboards": dashboards,
            "sub_folders": [],
            "sheet_names": [s["name"] for s in sheets],
            "summary": f"Folder '{folder_name}': {len(sheets)} sheets, {len(reports)} reports, {len(dashboards)} dashboards"
        }
        if depth < 3:
            for sub in (folder.folders or []):
                result["sub_folders"].append(_recurse_folder(client, sub.id, sub.name, depth + 1))
        return result
    except Exception as e:
        return {"folder_id": str(folder_id), "folder_name": folder_name, "error": str(e)}


def tool_get_workspace_contents(workspace_id: str, shallow: bool = True) -> dict:
    """
    Get contents of a workspace.
    shallow=True (default): returns folder names only — fast, use first.
    shallow=False: recursively fetches all sheets inside every folder — slower.
    Always start with shallow=True, then use get_folder_contents for specific folders.
    """
    client = _get_current_client()
    ws = client.Workspaces.get_workspace(int(workspace_id))

    if shallow:
        # Fast path — just top-level items + folder names, no recursion
        folders = [{"id": str(f.id), "name": f.name} for f in (ws.folders or [])]
        sheets = [{"id": str(s.id), "name": s.name} for s in (ws.sheets or [])]
        reports = [{"id": str(r.id), "name": r.name} for r in (ws.reports or [])]
        dashboards = [{"id": str(s.id), "name": s.name} for s in (ws.sights or [])]
        
        # Build clean summary for display
        summary_parts = []
        if folders: summary_parts.append(f"{len(folders)} folder(s): {', '.join(f['name'] for f in folders)}")
        if sheets: summary_parts.append(f"{len(sheets)} sheet(s): {', '.join(s['name'] for s in sheets)}")
        if reports: summary_parts.append(f"{len(reports)} report(s): {', '.join(r['name'] for r in reports)}")
        if dashboards: summary_parts.append(f"{len(dashboards)} dashboard(s): {', '.join(d['name'] for d in dashboards)}")
        
        return {
            "workspace_name": ws.name,
            "folders": folders,
            "top_level_sheets": sheets,
            "top_level_reports": reports,
            "top_level_dashboards": dashboards,
            "display_summary": f"**{ws.name}** contains: " + " | ".join(summary_parts),
            "folder_names": [f["name"] for f in folders],
            "note": "To see sheets inside a folder, use get_folder_contents with the folder id."
        }
    else:
        # Deep path — recurse into all folders
        folders = []
        for f in (ws.folders or []):
            folders.append(_recurse_folder(client, f.id, f.name))
        return {
            "workspace_id": workspace_id,
            "workspace_name": ws.name,
            "top_level_sheets": [{"id": str(s.id), "name": s.name} for s in (ws.sheets or [])],
            "top_level_reports": [{"id": str(r.id), "name": r.name} for r in (ws.reports or [])],
            "top_level_dashboards": [{"id": str(s.id), "name": s.name} for s in (ws.sights or [])],
            "folders": folders,
            "note": "Full recursive contents of all folders."
        }


def tool_get_folder_contents(folder_id: str) -> dict:
    """Get all sheets, reports and sub-folders inside a specific folder by folder ID."""
    client = _get_current_client()
    return _recurse_folder(client, int(folder_id), f"Folder {folder_id}")


def tool_list_sheets() -> dict:
    """List all sheets across all workspaces."""
    client = _get_current_client()
    result = client.Sheets.list_sheets(include_all=True)
    return {
        "sheets": [
            {"id": str(s.id), "name": s.name, "modified_at": str(s.modified_at)}
            for s in result.data
        ],
        "count": len(result.data)
    }


def tool_get_sheet(sheet_id: str, max_rows: int = 500) -> dict:
    """
    Get full sheet data: columns with metadata + rows.
    Returns column names, types, writeability, and all row data.
    ALWAYS call this before create_row to get actual column names.
    """
    client = _get_current_client()
    try:
        sheet = client.Sheets.get_sheet(int(sheet_id))
    except Exception as e:
        error_str = str(e)
        # Try without int conversion in case of overflow
        try:
            sheet = client.Sheets.get_sheet(sheet_id)
        except Exception as e2:
            return {
                "error": error_str,
                "error2": str(e2),
                "sheet_id": sheet_id,
                "hint": f"Failed to fetch sheet {sheet_id}. Try: 1) Verify you have access to this sheet, 2) Use search_sheets to find it by name instead."
            }

    # Build column maps from single API call (avoid double call)
    col_id_to_name = {col.id_: col.title for col in sheet.columns}
    # Update cache
    from utils.smartsheet_client import _column_cache
    _column_cache[int(sheet_id)] = {col.title: col.id_ for col in sheet.columns}

    UNWRITABLE_SYSTEM = {"AUTO_NUMBER","CREATED_DATE","MODIFIED_DATE","CREATED_BY","MODIFIED_BY"}

    columns_meta = []
    for col in sheet.columns:
        try:
            has_formula = bool(col.formula)
            has_system = str(col.system_column_type) in UNWRITABLE_SYSTEM if col.system_column_type else False
            has_autonum = bool(col.auto_number_format)

            meta = {
                "id": str(col.id_),
                "title": str(col.title or ""),
                "type": str(col.type_ or "TEXT_NUMBER"),
                "primary": bool(col.primary),
                "hidden": bool(col.hidden),
                "writable": not (has_formula or has_system or has_autonum),
                "auto_filled": has_formula or has_system or has_autonum
            }
            if has_system:
                meta["skip_reason"] = f"system ({col.system_column_type})"
            elif has_autonum:
                meta["skip_reason"] = "auto-number"
            elif has_formula:
                meta["skip_reason"] = "formula — auto-calculated"
                meta["formula"] = str(col.formula)

            # Safe options extraction
            if col.options:
                try:
                    meta["options"] = [str(o) for o in col.options]
                except Exception:
                    pass
            columns_meta.append(meta)
        except Exception as col_err:
            # Never let a bad column crash the whole sheet fetch
            columns_meta.append({
                "id": str(getattr(col, 'id_', '?')),
                "title": str(getattr(col, 'title', '?')),
                "type": "TEXT_NUMBER",
                "writable": True,
                "auto_filled": False,
                "parse_error": str(col_err)
            })

    user_cols = [c["title"] for c in columns_meta if c.get("writable") and not c.get("auto_filled")]
    auto_cols = [{"title": c["title"], "reason": c.get("skip_reason", "")} for c in columns_meta if not c.get("writable")]
    formula_cols = [c["title"] for c in columns_meta if c.get("auto_filled") and c.get("writable")]

    # Parse rows — safe, one bad cell never kills the whole row
    rows = []
    for row in (sheet.rows or [])[:max_rows]:
        try:
            row_data = {"_row_id": str(row.id), "_row_number": row.row_number}
            for cell in row.cells:
                try:
                    col_name = col_id_to_name.get(cell.column_id, str(cell.column_id))
                    row_data[col_name] = safe_cell_value(cell)
                except Exception:
                    pass
            rows.append(row_data)
        except Exception:
            pass

    return {
        "sheet_id": sheet_id,
        "sheet_name": sheet.name,
        "total_columns": len(sheet.columns),
        "columns_metadata": columns_meta,
        "user_fillable_columns": user_cols,
        "auto_filled_unwritable": auto_cols,
        "formula_columns_overrideable": formula_cols,
        "row_count": len(sheet.rows or []),
        "rows": rows,
        "instruction": f"To create a row, ask user for these columns only: {user_cols}"
    }


def tool_filter_rows(sheet_id: str, filters: dict, overdue_column: str = None,
                     group_by: str = None) -> dict:
    """
    Filter rows with rich conditions. Returns matched rows with pattern insights.

    filters: {"Status": "~Delayed", "Region": "Canada", "Budget": ">100000"}
      ~ prefix = contains, numeric: >, >=, <, <=, !=
      Special value "OVERDUE" on a date column = rows where date is past today

    overdue_column: flag rows where this date column is past today
    group_by: group results by column after filtering (e.g. "Region", "Division")
              reveals which group has the most issues
    """
    from datetime import date as _date, datetime as _datetime
    import re as _re

    data = tool_get_sheet(sheet_id, max_rows=settings.smartsheet_max_rows)
    today = _date.today()
    today_str = today.isoformat()
    results = []

    for row in data["rows"]:
        match = True
        for col, val in filters.items():
            cell_val = str(row.get(col, ""))
            val_str = str(val)

            if val_str.upper() == "OVERDUE":
                cell_date = cell_val.strip()[:10]
                if not (cell_date and cell_date < today_str):
                    match = False; break

            elif val_str.startswith("~"):
                if val_str[1:].lower() not in cell_val.lower():
                    match = False; break

            elif val_str and val_str[0] in "><!=":
                nm = _re.match(r'^([><=!]{1,2})([0-9.]+)$', val_str.strip())
                if nm:
                    op, n = nm.group(1), float(nm.group(2))
                    try:
                        cv = float(cell_val.replace(",","").replace("$","").replace("₹","").strip())
                        passed = (
                            (op==">" and cv>n) or (op==">=" and cv>=n) or
                            (op=="<" and cv<n) or (op=="<=" and cv<=n) or
                            (op in ("=","==") and cv==n) or (op in ("!=","<>") and cv!=n)
                        )
                        if not passed: match = False; break
                    except (ValueError, TypeError):
                        if cell_val.lower() != val_str.lower(): match = False; break
                else:
                    if cell_val.lower() != val_str.lower(): match = False; break
            else:
                if cell_val.lower() != val_str.lower(): match = False; break

        if match and overdue_column:
            cell_date = str(row.get(overdue_column, "")).strip()[:10]
            if not (cell_date and cell_date < today_str):
                match = False

        if match:
            results.append(row)

    # Compute days overdue
    overdue_col = overdue_column or next(
        (c for c, v in filters.items() if str(v).upper() == "OVERDUE"), None)
    if overdue_col:
        for row in results:
            cell_date = str(row.get(overdue_col, "")).strip()[:10]
            try:
                delta = (today - _datetime.strptime(cell_date, "%Y-%m-%d").date()).days
                row["_days_overdue"] = delta
            except Exception:
                pass
        results.sort(key=lambda r: r.get("_days_overdue", 0), reverse=True)

    # Group results
    group_summary = None
    pattern_insight = None
    if group_by and results:
        groups = {}
        for row in results:
            key = str(row.get(group_by, "Unknown"))
            groups.setdefault(key, []).append(row)
        group_summary = {k: {"count": len(v), "rows": v} for k, v in
                         sorted(groups.items(), key=lambda x: -x[1]["count"])}
        if len(group_summary) > 1:
            worst_k, worst_v = next(iter(group_summary.items()))
            pct = int(worst_v["count"] / len(results) * 100)
            pattern_insight = (
                f"{worst_k} accounts for {worst_v['count']}/{len(results)} ({pct}%) of matches — "
                f"this concentration suggests a systemic issue in {worst_k}"
            )

    return {
        "sheet_name": data["sheet_name"],
        "filters_applied": filters,
        "overdue_column": overdue_col,
        "matching_rows": results,
        "count": len(results),
        "total_rows": data["row_count"],
        "pct_matching": f"{int(len(results)/data['row_count']*100)}%" if data["row_count"] else "0%",
        "grouped_by": group_summary,
        "pattern_insight": pattern_insight
    }


def tool_aggregate_column(sheet_id: str, metric_column: str, group_by: str = None,
                          group_by_2: str = None, compare_column: str = None) -> dict:
    """
    Compute sum/avg/min/max/count for a numeric column with advanced grouping.

    group_by: primary grouping (e.g. "Region", "Division", "Country")
    group_by_2: secondary grouping for cross-tab analysis (e.g. group_by="Region", group_by_2="Status")
    compare_column: compare metric_column vs compare_column per row (budget vs actual spend)
                    reveals over/under-budget patterns per group
    Returns chart_data, pattern_insights, and variance analysis.
    """
    data = tool_get_sheet(sheet_id, max_rows=settings.smartsheet_max_rows)
    rows = data["rows"]

    def parse_num(v):
        try: return float(str(v).replace(",","").replace("$","").replace("₹","").strip())
        except: return None

    # Variance analysis (budget vs actual)
    variance_analysis = None
    if compare_column:
        variance_groups = {}
        for row in rows:
            base = parse_num(row.get(metric_column))
            comp = parse_num(row.get(compare_column))
            if base is None or comp is None: continue
            grp_key = str(row.get(group_by, "All")) if group_by else "All"
            variance_groups.setdefault(grp_key, {"base": [], "comp": []})
            variance_groups[grp_key]["base"].append(base)
            variance_groups[grp_key]["comp"].append(comp)

        variance_analysis = {}
        for grp, vals in variance_groups.items():
            total_base = sum(vals["base"])
            total_comp = sum(vals["comp"])
            diff = total_comp - total_base
            pct = round((diff / total_base * 100), 1) if total_base else 0
            variance_analysis[grp] = {
                f"total_{metric_column}": round(total_base, 2),
                f"total_{compare_column}": round(total_comp, 2),
                "variance": round(diff, 2),
                "variance_pct": f"{'+' if pct>=0 else ''}{pct}%",
                "status": "over" if pct > 5 else "under" if pct < -5 else "on_track"
            }

        # Pattern: which groups consistently overspend?
        over_groups = [k for k,v in variance_analysis.items() if v["status"] == "over"]
        if over_groups:
            variance_analysis["_pattern"] = (
                f"OVERSPEND PATTERN: {', '.join(over_groups)} consistently exceed budget. "
                f"Recommend budget buffer or tighter controls for these groups."
            )

    # Standard single-group aggregation
    if group_by:
        groups = {}
        for row in rows:
            key = str(row.get(group_by, "Unknown"))
            val = parse_num(row.get(metric_column))
            if val is not None:
                groups.setdefault(key, []).append(val)

        # Secondary grouping (cross-tab)
        cross_tab = None
        if group_by_2:
            ct = {}
            for row in rows:
                k1 = str(row.get(group_by, "Unknown"))
                k2 = str(row.get(group_by_2, "Unknown"))
                val = parse_num(row.get(metric_column))
                if val is not None:
                    ct.setdefault(k1, {}).setdefault(k2, []).append(val)
            cross_tab = {
                k1: {k2: {"sum": round(sum(vs),2), "count": len(vs), "avg": round(sum(vs)/len(vs),2)}
                     for k2, vs in sub.items()}
                for k1, sub in ct.items()
            }

        summary = {}
        for k, vals in sorted(groups.items(), key=lambda x: -sum(x[1])):
            total = sum(vals)
            avg = total / len(vals) if vals else 0
            summary[k] = {
                "count": len(vals),
                "sum": round(total, 2),
                "avg": round(avg, 2),
                "min": min(vals),
                "max": max(vals)
            }

        # Pattern insight: identify outliers
        avgs = [v["avg"] for v in summary.values()]
        overall_avg = sum(avgs) / len(avgs) if avgs else 0
        outliers = []
        for k, v in summary.items():
            if overall_avg and abs(v["avg"] - overall_avg) / overall_avg > 0.3:
                direction = "above" if v["avg"] > overall_avg else "below"
                pct = int(abs(v["avg"] - overall_avg) / overall_avg * 100)
                outliers.append(f"{k} is {pct}% {direction} average")

        chart_data = {
            "chart_type": "bar",
            "chart_title": f"{metric_column} by {group_by}",
            "labels": list(summary.keys()),
            "values": [v["sum"] for v in summary.values()]
        }

        return {
            "sheet_name": data["sheet_name"],
            "metric": metric_column,
            "group_by": group_by,
            "grouped_summary": summary,
            "cross_tab": cross_tab,
            "variance_analysis": variance_analysis,
            "outliers": outliers,
            "pattern_insight": f"Outliers detected: {'; '.join(outliers)}" if outliers else None,
            "chart_data": chart_data
        }

    # Flat aggregation
    values = [parse_num(row.get(metric_column)) for row in rows]
    values = [v for v in values if v is not None]
    if not values:
        return {"error": f"No numeric data in column '{metric_column}'"}

    total = sum(values)
    avg = total / len(values)
    return {
        "sheet_name": data["sheet_name"],
        "column": metric_column,
        "count": len(values),
        "sum": round(total, 2),
        "average": round(avg, 2),
        "min": min(values),
        "max": max(values),
        "variance_analysis": variance_analysis,
        "chart_data": {
            "chart_type": "bar",
            "chart_title": f"{metric_column} Summary",
            "labels": [str(r.get(list(r.keys())[2], i)) for i, r in enumerate(rows[:20])],
            "values": [parse_num(r.get(metric_column, 0)) or 0 for r in rows[:20]]
        }
    }


def tool_get_project_status_summary(sheet_id: str, status_column: str = "Status",
                                     name_column: str = "Project Name") -> dict:
    """
    Specialized tool: returns project portfolio health summary.
    Perfect for 'What's the status of my projects?' queries.
    Returns counts by status + list of delayed/at-risk projects.
    """
    data = tool_get_sheet(sheet_id, max_rows=settings.smartsheet_max_rows)
    rows = data["rows"]

    status_groups: dict = {}
    delayed = []
    over_budget = []

    for row in rows:
        status = str(row.get(status_column, "Unknown")).strip()
        name = str(row.get(name_column, f"Row {row.get('_row_number', '')}"))
        status_groups[status] = status_groups.get(status, 0) + 1

        status_lower = status.lower()
        if any(w in status_lower for w in ["delay", "behind", "at risk", "red"]):
            delayed.append({"name": name, "status": status, **{k: v for k, v in row.items() if not k.startswith("_")}})
        if "over" in status_lower and "budget" in status_lower:
            over_budget.append({"name": name, **{k: v for k, v in row.items() if not k.startswith("_")}})

    total = len(rows)
    on_track = status_groups.get("On Track", status_groups.get("Green", 0))

    return {
        "sheet_name": data["sheet_name"],
        "total_projects": total,
        "status_breakdown": status_groups,
        "on_track_count": on_track,
        "delayed_projects": delayed,
        "over_budget_projects": over_budget,
        "chart_data": {
            "chart_type": "pie",
            "chart_title": "Project Status Overview",
            "labels": list(status_groups.keys()),
            "values": list(status_groups.values())
        }
    }


def _format_cell_value(col_type: str, value, col_options: list = None):
    """
    Format a value correctly for a given Smartsheet column type.
    Returns (cell_value, object_value) tuple.
    """
    if value is None or value == "":
        return None, None

    col_type = (col_type or "").upper()

    # CONTACT_LIST — must be {"objectType": "CONTACT", "email": "..."}
    if col_type == "CONTACT_LIST":
        if isinstance(value, str) and "@" in value:
            return None, {"objectType": "CONTACT", "email": value.strip()}
        elif isinstance(value, str):
            return None, {"objectType": "CONTACT", "name": value.strip()}
        return None, value

    # CHECKBOX — must be boolean
    if col_type == "CHECKBOX":
        if isinstance(value, bool):
            return value, None
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "checked"), None
        return bool(value), None

    # PICKLIST / DROPDOWN — must match one of the allowed options exactly
    if col_type in ("PICKLIST", "MULTI_PICKLIST"):
        if col_options and isinstance(value, str):
            # Match by number (user types "1", "2" etc)
            if value.strip().isdigit():
                idx = int(value.strip()) - 1
                if 0 <= idx < len(col_options):
                    return col_options[idx], None
            # Case-insensitive match to allowed options
            for opt in col_options:
                if opt.lower() == value.lower():
                    return opt, None
            # Partial match
            for opt in col_options:
                if value.lower() in opt.lower():
                    return opt, None
        return str(value), None

    # DATE columns — ensure YYYY-MM-DD format
    if col_type == "DATE":
        val = str(value).strip().lower()
        from datetime import date, timedelta
        today = date.today()
        # Natural language dates
        if val in ("today", "now"):        return today.strftime("%Y-%m-%d"), None
        if val in ("tomorrow"):            return (today + timedelta(days=1)).strftime("%Y-%m-%d"), None
        if val in ("yesterday"):           return (today - timedelta(days=1)).strftime("%Y-%m-%d"), None
        val = str(value).strip()
        # Already correct format
        if len(val) == 10 and val[4] == "-": return val, None
        # Convert common formats
        try:
            from datetime import datetime
            for fmt in ["%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %b %Y", "%B %d %Y"]:
                try:
                    return datetime.strptime(val, fmt).strftime("%Y-%m-%d"), None
                except:
                    pass
        except:
            pass
        return val, None

    # DURATION — numeric
    if col_type == "DURATION":
        try:
            return float(str(value).replace(",", "").replace("$", "").strip()), None
        except:
            return str(value), None

    # TEXT_NUMBER / default — plain value
    try:
        # Strip currency/comma formatting for numbers
        clean = str(value).replace(",", "").replace("$", "").strip()
        if clean.replace(".", "").isdigit():
            return float(clean) if "." in clean else int(clean), None
    except:
        pass
    return str(value), None


def tool_create_row(sheet_id: str, row_data: dict) -> dict:
    """Create a new row. row_data: {col_name: value}."""
    import smartsheet as ss_lib
    client = _get_current_client()

    # Fetch sheet to get column metadata
    try:
        sheet = client.Sheets.get_sheet(int(sheet_id))
    except Exception as e:
        return {"success": False, "error": f"Cannot access sheet: {e}"}

    # Build column lookup: title -> col object
    col_map = {col.title: col for col in sheet.columns}

    UNWRITABLE = {"AUTO_NUMBER","CREATED_DATE","MODIFIED_DATE","CREATED_BY","MODIFIED_BY"}

    cells = []
    skipped = []

    for col_name, value in row_data.items():
        if value is None or str(value).strip() == "" or str(value).lower() in ("skip", "blank", "none", "n/a"):
            skipped.append(f"{col_name} (empty)")
            continue

        col = col_map.get(col_name)
        if not col:
            skipped.append(f"{col_name} (not found)")
            continue

        # Skip system columns
        if str(col.system_column_type) in UNWRITABLE:
            skipped.append(f"{col_name} (system)")
            continue

        # Skip auto-number columns
        if col.auto_number_format:
            skipped.append(f"{col_name} (auto-number)")
            continue

        # Skip formula columns
        if col.formula:
            skipped.append(f"{col_name} (formula)")
            continue

        try:
            cell = ss_lib.models.Cell()
            cell.column_id = col.id_
            cell.strict = False

            col_type = str(col.type_) if col.type_ else "TEXT_NUMBER"

            if col_type == "CONTACT_LIST":
                val = str(value).strip()
                if "@" in val:
                    cell.object_value = {"objectType": "CONTACT", "email": val}
                else:
                    cell.object_value = {"objectType": "CONTACT", "name": val}

            elif col_type == "CHECKBOX":
                v = str(value).lower().strip()
                cell.value = v in ("true", "yes", "1", "checked")

            elif col_type in ("PICKLIST", "MULTI_PICKLIST"):
                val = str(value).strip()
                # Match by number
                if val.isdigit() and col.options:
                    idx = int(val) - 1
                    val = col.options[idx] if 0 <= idx < len(col.options) else val
                elif col.options:
                    # Case-insensitive match
                    for opt in col.options:
                        if opt.lower() == val.lower():
                            val = opt
                            break
                cell.value = val

            elif col_type == "DATE":
                from datetime import date, timedelta
                v = str(value).strip().lower()
                today = date.today()
                if v in ("today", "now"):
                    cell.value = today.strftime("%Y-%m-%d")
                elif v == "tomorrow":
                    cell.value = (today + timedelta(days=1)).strftime("%Y-%m-%d")
                elif v == "yesterday":
                    cell.value = (today - timedelta(days=1)).strftime("%Y-%m-%d")
                elif "month" in v or "months" in v:
                    # e.g. "after 3 months"
                    import re
                    nums = re.findall(r'[0-9]+', v)
                    months = int(nums[0]) if nums else 1
                    future = date(today.year + (today.month + months - 1) // 12,
                                  (today.month + months - 1) % 12 + 1, today.day)
                    cell.value = future.strftime("%Y-%m-%d")
                else:
                    # Try common date formats
                    v = str(value).strip()
                    if len(v) == 10 and v[4] == "-":
                        cell.value = v
                    else:
                        from datetime import datetime
                        parsed = None
                        for fmt in ["%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]:
                            try:
                                parsed = datetime.strptime(v, fmt).strftime("%Y-%m-%d")
                                break
                            except Exception:
                                pass
                        cell.value = parsed or v

            else:
                # TEXT_NUMBER — strip currency/commas for numbers
                v = str(value).strip()
                clean = v.replace(",", "").replace("$", "").strip()
                try:
                    cell.value = float(clean) if "." in clean else int(clean)
                except Exception:
                    cell.value = v

            cells.append(cell)

        except Exception as e:
            skipped.append(f"{col_name} (error: {e})")

    if not cells:
        return {
            "success": False,
            "error": "No writable cells. All columns were skipped.",
            "skipped": skipped
        }

    # Create the row
    new_row = ss_lib.models.Row()
    new_row.to_bottom = True
    new_row.cells = cells

    try:
        result = client.Sheets.add_rows(int(sheet_id), [new_row])
        if not result.data:
            return {
                "success": False,
                "error": "Smartsheet accepted the request but returned no row data.",
                "result_code": getattr(result, 'result_code', None),
                "skipped": skipped
            }
        created = result.data[0]
        logger.info("Row created", sheet_id=sheet_id, row_id=str(created.id), row_number=created.row_number)
        return {
            "success": True,
            "row_id": str(created.id),
            "row_number": created.row_number,
            "message": f"✅ Row created at position {created.row_number}",
            "columns_written": len(cells),
            "skipped": skipped
        }
    except Exception as e:
        return {"success": False, "error": str(e), "skipped": skipped}


def tool_update_row(sheet_id: str, row_id: str, updates: dict) -> dict:
    """Update cells in a row. updates: {col_name: value}."""
    import smartsheet as ss_lib
    client = _get_current_client()

    try:
        sheet = client.Sheets.get_sheet(int(sheet_id))
    except Exception as e:
        return {"success": False, "error": f"Cannot access sheet: {e}"}

    col_map = {col.title: col for col in sheet.columns}
    UNWRITABLE = {"AUTO_NUMBER","CREATED_DATE","MODIFIED_DATE","CREATED_BY","MODIFIED_BY"}

    cells = []
    skipped = []

    for col_name, value in updates.items():
        if value is None or str(value).strip() == "":
            skipped.append(f"{col_name} (empty)")
            continue

        col = col_map.get(col_name)
        if not col:
            skipped.append(f"{col_name} (not found)")
            continue

        if str(col.system_column_type) in UNWRITABLE:
            skipped.append(f"{col_name} (system)")
            continue

        if col.auto_number_format:
            skipped.append(f"{col_name} (auto-number)")
            continue

        # Formula columns CAN be updated (user explicitly wants to override)
        try:
            cell = ss_lib.models.Cell()
            cell.column_id = col.id_
            cell.strict = False

            col_type = str(col.type_) if col.type_ else "TEXT_NUMBER"

            if col_type == "CONTACT_LIST":
                val = str(value).strip()
                if "@" in val:
                    cell.object_value = {"objectType": "CONTACT", "email": val}
                else:
                    cell.object_value = {"objectType": "CONTACT", "name": val}

            elif col_type == "CHECKBOX":
                v = str(value).lower().strip()
                cell.value = v in ("true", "yes", "1", "checked")

            elif col_type in ("PICKLIST", "MULTI_PICKLIST"):
                val = str(value).strip()
                if val.isdigit() and col.options:
                    idx = int(val) - 1
                    val = col.options[idx] if 0 <= idx < len(col.options) else val
                elif col.options:
                    for opt in col.options:
                        if opt.lower() == val.lower():
                            val = opt
                            break
                cell.value = val

            elif col_type == "DATE":
                from datetime import date, timedelta
                v = str(value).strip().lower()
                today = date.today()
                if v in ("today", "now"):
                    cell.value = today.strftime("%Y-%m-%d")
                elif v == "tomorrow":
                    cell.value = (today + timedelta(days=1)).strftime("%Y-%m-%d")
                else:
                    v = str(value).strip()
                    if len(v) == 10 and v[4] == "-":
                        cell.value = v
                    else:
                        from datetime import datetime
                        for fmt in ["%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]:
                            try:
                                cell.value = datetime.strptime(v, fmt).strftime("%Y-%m-%d")
                                break
                            except Exception:
                                pass
                        else:
                            cell.value = v

            else:
                v = str(value).strip()
                clean = v.replace(",", "").replace("$", "").replace("₹", "").strip()
                try:
                    cell.value = float(clean) if "." in clean else int(clean)
                except Exception:
                    cell.value = v

            cells.append(cell)

        except Exception as e:
            skipped.append(f"{col_name} (error: {e})")

    if not cells:
        return {"success": False, "error": "No valid cells to update.", "skipped": skipped}

    try:
        row = ss_lib.models.Row()
        row.id = int(row_id)
        row.cells = cells
        result = client.Sheets.update_rows(int(sheet_id), [row])
        logger.info("Row updated", sheet_id=sheet_id, row_id=row_id, fields=list(updates.keys()))
        return {
            "success": True,
            "row_id": row_id,
            "updated_fields": [c for c in updates.keys() if c not in [s.split(" (")[0] for s in skipped]],
            "skipped": skipped,
            "message": f"✅ Row updated successfully"
        }
    except Exception as e:
        return {"success": False, "error": str(e), "skipped": skipped}


def tool_delete_row(sheet_id: str, row_id: str) -> dict:
    """Delete a row from a sheet. Always confirm with user before calling."""
    client = _get_current_client()
    client.Sheets.delete_rows(int(sheet_id), [int(row_id)])
    logger.info("Row deleted", sheet_id=sheet_id, row_id=row_id)
    return {"success": True, "message": f"Row {row_id} deleted from sheet {sheet_id}"}


def tool_list_dashboards() -> dict:
    """List all dashboards (Sights) in the account."""
    client = _get_current_client()
    result = client.Sights.list_sights(include_all=True)
    return {
        "dashboards": [{"id": str(s.id), "name": s.name} for s in result.data],
        "count": len(result.data)
    }


def tool_get_dashboard(sight_id: str, fetch_data: bool = False) -> dict:
    """
    Get dashboard widgets.
    fetch_data=False (default): fast — returns widget list with names and types only.
    fetch_data=True: slow — fetches actual data from linked reports/sheets per widget.
    Use fetch_data=False first to show the dashboard, then fetch_data=True only if user asks for data.
    """
    client = _get_current_client()
    try:
        sight = client.Sights.get_sight(int(sight_id))
    except Exception as e:
        return {"error": str(e), "sight_id": sight_id}

    widgets_summary = []
    for w in (sight.widgets or []):
        try:
            contents = w.to_dict().get("contents", {})
        except Exception:
            contents = {}
        widget_info = {
            "id": str(w.id_),
            "type": w.type,
            "title": w.title or "",
            "has_report": bool(contents.get("reportId")),
            "has_sheet": bool(contents.get("sheetId")),
            "report_id": str(contents.get("reportId","")) if contents.get("reportId") else None,
            "sheet_id": str(contents.get("sheetId","")) if contents.get("sheetId") else None,
        }
        
        # Fetch data only if requested
        if fetch_data:
            report_id = contents.get("reportId")
            sheet_id = contents.get("sheetId")
            if report_id:
                try:
                    report = client.Reports.get_report(report_id, page_size=50)
                    col_map = {col.virtual_id: col.title for col in (report.columns or [])}
                    rows = []
                    for row in (report.rows or [])[:20]:
                        row_data = {}
                        for cell in (row.cells or []):
                            col_name = col_map.get(cell.virtual_column_id, str(cell.virtual_column_id))
                            row_data[col_name] = safe_cell_value(cell)
                        rows.append(row_data)
                    widget_info["data"] = rows
                    widget_info["row_count"] = len(report.rows or [])
                    widget_info["report_name"] = report.name
                except Exception as e:
                    widget_info["data_error"] = str(e)
            elif sheet_id:
                try:
                    sheet = client.Sheets.get_sheet(int(sheet_id))
                    col_map = {col.id_: col.title for col in sheet.columns}
                    rows = []
                    for row in (sheet.rows or [])[:15]:
                        row_data = {}
                        for cell in row.cells:
                            row_data[col_map.get(cell.column_id,str(cell.column_id))] = safe_cell_value(cell)
                        rows.append(row_data)
                    widget_info["data"] = rows
                    widget_info["sheet_name"] = sheet.name
                except Exception as e:
                    widget_info["data_error"] = str(e)
        
        widgets_summary.append(widget_info)

    return {
        "dashboard_id": sight_id,
        "dashboard_name": sight.name,
        "permalink": sight.permalink,
        "widget_count": len(widgets_summary),
        "widgets": widgets_summary,
        "note": "Use fetch_data=True to load actual data from report/sheet widgets."
    }


def tool_create_dashboard(name: str, workspace_id: str = None) -> dict:
    """
    Note: Smartsheet API does not support creating dashboards programmatically.
    Dashboards must be created in the Smartsheet web interface.
    This tool returns instructions for the user.
    """
    workspace_hint = f" in workspace {workspace_id}" if workspace_id else ""
    return {
        "success": False,
        "api_limitation": True,
        "message": f"Smartsheet's API does not support creating dashboards programmatically.",
        "instructions": [
            f"1. Open Smartsheet and navigate to your workspace{workspace_hint}",
            f"2. Click the + icon or 'Add' button",
            f"3. Select 'Dashboard'",
            f"4. Name it '{name}'",
            "5. Add widgets by clicking the widget panel on the right",
            "6. Use CHART/METRIC/REPORT widgets linked to your sheets"
        ],
        "what_i_can_do": [
            "List your existing dashboards",
            "Show data from a dashboard's linked sheets/reports",
            "Add widgets to an existing dashboard (limited API support)",
            "Analyze your sheet data so you know what to display"
        ],
        "existing_dashboards_tip": "Say 'show my dashboards' to see what you already have"
    }


def tool_list_scc_programs() -> dict:
    """List all Control Center programs."""
    client = _get_current_client()
    try:
        result = client.request("GET", "/programs", params={"includeAll": "true"})
        programs = result.get("data", []) if isinstance(result, dict) else []
        return {
            "programs": [
                {"id": str(p.get("id")), "name": p.get("name"), "type": p.get("type")}
                for p in programs
            ],
            "count": len(programs)
        }
    except Exception as e:
        return {"error": str(e), "hint": "Ensure Control Center is enabled on this Smartsheet account"}


def tool_list_blueprints(program_id: str) -> dict:
    """List blueprints available in a Control Center program."""
    client = _get_current_client()
    try:
        result = client.request("GET", f"/programs/{program_id}/blueprints")
        blueprints = result.get("data", []) if isinstance(result, dict) else []
        return {
            "program_id": program_id,
            "blueprints": [
                {"id": str(b.get("id")), "name": b.get("name"), "description": b.get("description", "")}
                for b in blueprints
            ]
        }
    except Exception as e:
        return {"error": str(e)}


def tool_rollout_project(intake_sheet_id: str, profile_data: dict,
                         approval_column: str = "Approved",
                         approval_value: str = "true") -> dict:
    """
    Roll out a new project via Control Center auto-provisioning.

    HOW IT WORKS:
    1. Writes a new row to the intake sheet with the project profile data
    2. Sets the approval column to the trigger value
    3. Control Center detects the approval and auto-provisions the project

    PREREQUISITE: Auto-provisioning must be enabled in Control Center
    (Program Lead goes to Manage Program → Automations → New Automation → enable for blueprint).

    intake_sheet_id: ID of the SCC intake sheet (get from get_sheet_by_name)
    profile_data: {column_name: value} — all profile fields for the new project
                  e.g. {"Project Name": "Site Mumbai", "PM": "Rahul", "Start Date": "2026-05-01", "Budget": "500000"}
    approval_column: Name of the approval column on the intake sheet (default: "Approved")
    approval_value: Value that triggers provisioning — "true" for checkbox, or dropdown value like "Approved"
    """
    import smartsheet as ss_lib
    client = _get_current_client()

    try:
        # Step 1: Fetch the intake sheet to get column metadata
        sheet = client.Sheets.get_sheet(int(intake_sheet_id))
        col_map = {col.title: col for col in sheet.columns}

        UNWRITABLE = {"AUTO_NUMBER","CREATED_DATE","MODIFIED_DATE","CREATED_BY","MODIFIED_BY"}

        # Step 2: Build cells for profile data
        cells = []
        skipped = []
        approval_cell = None

        for col_name, value in profile_data.items():
            col = col_map.get(col_name)
            if not col:
                skipped.append(f"{col_name} (column not found)")
                continue
            if str(col.system_column_type) in UNWRITABLE:
                skipped.append(f"{col_name} (system)")
                continue

            cell = ss_lib.models.Cell()
            cell.column_id = col.id_
            cell.strict = False

            col_type = str(col.type_) if col.type_ else "TEXT_NUMBER"
            if col_type == "CONTACT_LIST":
                val = str(value).strip()
                cell.object_value = {"objectType": "CONTACT", "email": val} if "@" in val else {"objectType": "CONTACT", "name": val}
            elif col_type == "DATE":
                from datetime import date, timedelta
                v = str(value).strip().lower()
                today = date.today()
                if v == "today": cell.value = today.strftime("%Y-%m-%d")
                elif v == "tomorrow": cell.value = (today + timedelta(1)).strftime("%Y-%m-%d")
                elif len(str(value).strip()) == 10 and str(value).strip()[4] == "-": cell.value = str(value).strip()
                else:
                    from datetime import datetime
                    for fmt in ["%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]:
                        try: cell.value = datetime.strptime(str(value).strip(), fmt).strftime("%Y-%m-%d"); break
                        except: pass
                    else: cell.value = str(value)
            else:
                v = str(value).strip()
                clean = v.replace(",","").replace("$","").replace("₹","").strip()
                try: cell.value = float(clean) if "." in clean else int(clean)
                except: cell.value = v
            cells.append(cell)

        if not cells:
            return {"success": False, "error": "No writable cells built from profile_data", "skipped": skipped}

        # Step 3: Add approval column cell
        approval_col = col_map.get(approval_column)
        if approval_col:
            ap_cell = ss_lib.models.Cell()
            ap_cell.column_id = approval_col.id_
            ap_cell.strict = False
            col_type = str(approval_col.type_) if approval_col.type_ else "TEXT_NUMBER"
            if col_type == "CHECKBOX":
                ap_cell.value = approval_value.lower() in ("true","yes","1","checked")
            else:
                ap_cell.value = approval_value
            cells.append(ap_cell)
        else:
            # Approval column not found — still create the row, warn user
            skipped.append(f"{approval_column} (approval column not found — project may need manual approval in SCC)")

        # Step 4: Create the row
        new_row = ss_lib.models.Row()
        new_row.to_bottom = True
        new_row.cells = cells

        result = client.Sheets.add_rows(int(intake_sheet_id), [new_row])
        if not result.data:
            return {"success": False, "error": "Row created but no data returned", "skipped": skipped}

        created = result.data[0]
        project_name = profile_data.get("Project Name", profile_data.get("Name", "New Project"))

        logger.info("Project intake row created", sheet_id=intake_sheet_id, row_id=str(created.id), project=project_name)

        approval_msg = (
            f"✅ Approval column '{approval_column}' set to trigger auto-provisioning."
            if approval_col
            else f"⚠️ Approval column '{approval_column}' not found — set it manually in Smartsheet to trigger provisioning."
        )

        return {
            "success": True,
            "row_id": str(created.id),
            "row_number": created.row_number,
            "project_name": project_name,
            "approval_status": approval_msg,
            "skipped": skipped,
            "message": f"✅ Project '{project_name}' added to intake sheet (row {created.row_number}). {approval_msg} Control Center will auto-provision within seconds if auto-provisioning is enabled.",
            "next_steps": [
                "Check Control Center to confirm provisioning started",
                "Use list_scc_projects to see the new project once ready",
                "If provisioning didn't trigger, ensure auto-provisioning is enabled in SCC Automations"
            ]
        }

    except Exception as e:
        return {"success": False, "error": str(e), "hint": "Ensure intake_sheet_id is correct and you have write access"}


def tool_list_scc_projects(program_id: str) -> dict:
    """List rolled-out projects."""
    client = _get_current_client()
    try:
        result = client.request("GET", f"/programs/{program_id}/projects")
        projects = result.get("data", []) if isinstance(result, dict) else []
        return {
            "program_id": program_id,
            "projects": [
                {"id": str(p.get("id")), "name": p.get("name"), "status": p.get("status")}
                for p in projects
            ],
            "count": len(projects)
        }
    except Exception as e:
        return {"error": str(e)}


def tool_search_sheets(query: str) -> dict:
    """Search across all sheets for a keyword."""
    client = _get_current_client()
    result = client.Search.search(query)
    results = []
    for item in (result.results or [])[:20]:
        results.append({
            "object_type": item.object_type,
            "object_id": str(item.object_id),
            "text": item.text,
            "context_data": [str(c) for c in (item.context_data or [])]
        })
    return {"query": query, "results": results, "count": len(results)}




def tool_add_widget_to_dashboard(sight_id: str, widget_type: str, title: str, sheet_id: str = None) -> dict:
    """Add a widget to an existing dashboard."""
    import requests as req_lib
    from utils.config import get_settings
    settings = get_settings()

    headers = {
        "Authorization": f"Bearer {settings.smartsheet_api_token}",
        "Content-Type": "application/json"
    }

    # Build widget payload based on type
    widget = {
        "type": widget_type.upper(),
        "title": title,
        "showTitle": True,
        "showTitleStyle": True,
        "titleFormat": ",,1,,,,,,,",
        "version": 1
    }

    if widget_type.upper() == "TITLE":
        widget["contents"] = {
            "htmlContent": f"<h2>{title}</h2>",
            "backgroundColor": "#003087"
        }
    elif sheet_id and widget_type.upper() in ["METRIC", "CHART", "REPORT"]:
        widget["contents"] = {
            "sheetId": int(sheet_id),
            "columnId": None
        }

    url = f"https://api.smartsheet.com/2.0/sights/{sight_id}"
    try:
        # First get existing widgets
        get_resp = req_lib.get(url, headers=headers)
        sight_data = get_resp.json()
        existing_widgets = sight_data.get("widgets", [])
        existing_widgets.append(widget)

        # Update sight with new widget
        put_resp = req_lib.put(url, json={"widgets": existing_widgets}, headers=headers)
        data = put_resp.json()
        if put_resp.status_code in (200, 201):
            return {
                "success": True,
                "dashboard_id": sight_id,
                "widget_type": widget_type,
                "title": title,
                "message": f"Widget '{title}' of type {widget_type} added to dashboard"
            }
        else:
            return {"error": data.get("message", str(data)), "status": put_resp.status_code}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# AUTOMATION TOOLS
# ═══════════════════════════════════════════════════════════════

def tool_list_automations(sheet_id: str) -> dict:
    """List all automation rules on a sheet."""
    client = _get_current_client()
    try:
        result = client.Sheets.list_automation_rules(int(sheet_id))
        rules = []
        for rule in (result.data or []):
            action = rule.action if rule.action else None
            rules.append({
                "id": str(rule.id_),
                "name": rule.name,
                "enabled": rule.enabled,
                "action_type": action.type_ if action else None,
                "action_message": action.message if action else None,
                "action_subject": action.subject if action else None,
            })
        return {
            "sheet_id": sheet_id,
            "automation_rules": rules,
            "count": len(rules)
        }
    except Exception as e:
        return {"error": str(e)}


def tool_create_automation(sheet_id: str, rule_name: str, action_type: str,
                           message: str, subject: str = None,
                           trigger_type: str = "WHEN_ROWS_ADDED",
                           trigger_column: str = None,
                           notify_all_users: bool = False,
                           recipient_emails: list = None,
                           frequency: str = "IMMEDIATELY") -> dict:
    """
    NOTE: Smartsheet API does NOT support creating new automation rules programmatically.
    This is an official API limitation — only list, update, and delete are supported.

    This tool returns the exact configuration needed so the user can create it manually
    in Smartsheet (Automation → Create Workflow) in under 2 minutes.

    What CAN be done via API:
    - list_automations: list all existing rules
    - update_automation: enable/disable, change message/subject/recipients
    - delete_automation: remove a rule
    """
    client = _get_current_client()

    # Resolve trigger column display
    trigger_col_info = ""
    if trigger_column:
        try:
            sheet = client.Sheets.get_sheet(int(sheet_id))
            cols = {col.title for col in sheet.columns}
            if trigger_column in cols:
                trigger_col_info = f" watching column '{trigger_column}'"
            else:
                trigger_col_info = f" (column '{trigger_column}' not found — check name)"
        except Exception:
            pass

    # Format recipients cleanly
    recipient_list = []
    if recipient_emails:
        recipient_list = [e.strip() for e in recipient_emails if e.strip()]

    trigger_display = {
        "WHEN_ROWS_ADDED": "When a row is added",
        "WHEN_ROWS_CHANGED": "When a row is changed",
        "WHEN_ROWS_DELETED": "When a row is deleted",
        "WHEN_CELL_CHANGED": f"When a cell changes{trigger_col_info}",
    }.get(trigger_type.upper(), trigger_type)

    action_display = {
        "NOTIFICATION": "Send notification",
        "UPDATE_REQUEST": "Send update request",
        "APPROVAL_REQUEST": "Send approval request",
    }.get(action_type.upper(), action_type)

    return {
        "success": False,
        "api_limitation": "Smartsheet API does not support creating automation rules programmatically. This is a confirmed official limitation.",
        "what_you_can_do": "Create this automation manually in Smartsheet — it takes under 2 minutes.",
        "manual_steps": "Automation tab → Create Workflow → Create from scratch",
        "config_to_create": {
            "name": rule_name,
            "trigger": trigger_display,
            "frequency": frequency,
            "action": action_display,
            "subject": subject or rule_name,
            "message": message,
            "recipients": recipient_list if recipient_list else ("All shared users" if notify_all_users else "Set in Smartsheet UI"),
            "include_all_columns": True
        },
        "api_capabilities": {
            "list_automations": "✅ Supported — use list_automations",
            "update_automation": "✅ Supported — can change message, subject, recipients, enable/disable",
            "delete_automation": "✅ Supported — use delete_automation",
            "create_automation": "❌ Not supported by Smartsheet API"
        }
    }


def tool_update_automation(sheet_id: str, rule_id: str,
                           enabled: bool = None, message: str = None) -> dict:
    """Enable, disable or update an existing automation rule."""
    client = _get_current_client()
    try:
        # Get existing rule first
        rule = client.Sheets.get_automation_rule(int(sheet_id), int(rule_id))
        if enabled is not None:
            rule.enabled = enabled
        if message and rule.action:
            rule.action.message = message
        client.Sheets.update_automation_rule(int(sheet_id), int(rule_id), rule)
        return {
            "success": True,
            "rule_id": rule_id,
            "enabled": enabled,
            "message": f"Automation rule {rule_id} updated"
        }
    except Exception as e:
        return {"error": str(e)}


def tool_delete_automation(sheet_id: str, rule_id: str) -> dict:
    """Delete an automation rule from a sheet. ALWAYS confirm before calling."""
    client = _get_current_client()
    try:
        client.Sheets.delete_automation_rule(int(sheet_id), int(rule_id))
        return {
            "success": True,
            "message": f"Automation rule {rule_id} deleted from sheet {sheet_id}"
        }
    except Exception as e:
        return {"error": str(e)}


def tool_create_webhook(sheet_id: str, name: str, callback_url: str) -> dict:
    """
    Create a webhook on a sheet.
    Webhook fires on any row change and POSTs to callback_url.
    Useful for real-time integrations.
    """
    client = _get_current_client()
    try:
        import smartsheet as ss_lib
        webhook = ss_lib.models.Webhook({
            "name": name,
            "callbackUrl": callback_url,
            "scope": "sheet",
            "scopeObjectId": int(sheet_id),
            "events": ["*.*"],
            "version": 1
        })
        result = client.Webhooks.create_webhook(webhook)
        wh = result.data
        return {
            "success": True,
            "webhook_id": str(wh.id),
            "name": wh.name,
            "status": wh.status,
            "callback_url": callback_url,
            "message": f"Webhook '{name}' created. It will fire on every sheet change."
        }
    except Exception as e:
        return {"error": str(e)}


def tool_list_webhooks() -> dict:
    """List all webhooks in the account."""
    client = _get_current_client()
    try:
        result = client.Webhooks.list_webhooks(include_all=True)
        return {
            "webhooks": [
                {
                    "id": str(w.id),
                    "name": w.name,
                    "status": w.status,
                    "scope_object_id": str(w.scope_object_id),
                    "callback_url": w.callback_url
                }
                for w in (result.data or [])
            ],
            "count": len(result.data or [])
        }
    except Exception as e:
        return {"error": str(e)}




# ═══════════════════════════════════════════════════════════════
# CROSS-SHEET LINK TOOLS
# ═══════════════════════════════════════════════════════════════

def tool_get_sheet_with_links(sheet_id: str, max_rows: int = 200) -> dict:
    """
    Get sheet data WITH cross-sheet link values resolved.
    For cells that pull data from another sheet (link_in_from_cell),
    this returns the actual linked value + the source sheet info.
    Use this instead of get_sheet when a sheet has cross-sheet references.
    """
    client = _get_current_client()
    # include=["objectValue"] resolves cross-sheet linked cell values
    sheet = client.Sheets.get_sheet(int(sheet_id))
    rev_map = {col.id_: col.title for col in sheet.columns}

    # Rich column metadata
    columns_meta = []
    for col in sheet.columns:
        meta = {
            "id": str(col.id_),
            "title": col.title,
            "type": col.type_,
            "auto_filled": False
        }
        if col.formula:
            meta["formula"] = col.formula
            meta["auto_filled"] = True
            meta["skip_reason"] = "formula — auto-calculated"
        elif col.system_column_type:
            meta["system_column_type"] = col.system_column_type
            meta["auto_filled"] = True
            meta["skip_reason"] = f"system column ({col.system_column_type})"
        elif col.auto_number_format:
            meta["auto_filled"] = True
            meta["skip_reason"] = "auto-number"
        if col.options:
            meta["options"] = col.options
        columns_meta.append(meta)

    # Parse rows including link info
    rows = []
    linked_cells_found = []
    for row in (sheet.rows or [])[:max_rows]:
        row_data = {"_row_id": str(row.id), "_row_number": row.row_number}
        for cell in row.cells:
            col_name = rev_map.get(cell.column_id, str(cell.column_id))
            val = safe_cell_value(cell)

            # Cross-sheet link inbound (this cell pulls from another sheet)
            if cell.link_in_from_cell:
                link = cell.link_in_from_cell
                row_data[col_name] = val
                row_data[f"_link_{col_name}"] = {
                    "linked_from_sheet_id": str(link.sheet_id),
                    "linked_from_sheet_name": link.sheet_name,
                    "linked_from_row_id": str(link.row_id),
                    "status": link.status  # OK, BROKEN, PARTIAL
                }
                if link.status != "OK":
                    linked_cells_found.append({
                        "column": col_name,
                        "row": row.row_number,
                        "source_sheet": link.sheet_name,
                        "status": link.status
                    })
            # Cross-sheet link outbound (this cell sends to other sheets)
            elif cell.links_out_to_cells:
                row_data[col_name] = val
                row_data[f"_sends_{col_name}"] = [
                    {"sheet_id": str(l.sheet_id), "sheet_name": l.sheet_name}
                    for l in cell.links_out_to_cells
                ]
            else:
                row_data[col_name] = val
        rows.append(row_data)

    # Get cross-sheet references defined on this sheet
    xrefs = []
    try:
        xref_result = client.Sheets.list_cross_sheet_references(int(sheet_id))
        for xr in (xref_result.data or []):
            xrefs.append({
                "name": xr.name,
                "source_sheet_id": str(xr.source_sheet_id),
                "status": xr.status
            })
    except Exception:
        pass

    broken = [c for c in linked_cells_found if c["status"] != "OK"]

    return {
        "sheet_id": sheet_id,
        "sheet_name": sheet.name,
        "columns_metadata": columns_meta,
        "user_fillable_columns": [c["title"] for c in columns_meta if not c.get("auto_filled")],
        "auto_filled_columns": [{"title": c["title"], "reason": c.get("skip_reason")} for c in columns_meta if c.get("auto_filled")],
        "cross_sheet_references": xrefs,
        "broken_links": broken,
        "rows": rows,
        "row_count": len(sheet.rows or []),
        "note": "Cells with _link_ prefix show their source sheet. Broken links mean the source data is unavailable."
    }


def tool_list_cross_sheet_references(sheet_id: str) -> dict:
    """
    List all cross-sheet references (VLOOKUP-like formulas) defined on a sheet.
    Shows which other sheets this sheet pulls data from and the status of each reference.
    """
    client = _get_current_client()
    try:
        result = client.Sheets.list_cross_sheet_references(int(sheet_id))
        refs = []
        for xr in (result.data or []):
            refs.append({
                "id": str(xr.id_),
                "name": xr.name,
                "source_sheet_id": str(xr.source_sheet_id),
                "status": xr.status,
                "start_row_id": str(xr.start_row_id) if xr.start_row_id else None,
                "end_row_id": str(xr.end_row_id) if xr.end_row_id else None,
                "start_column_id": str(xr.start_column_id) if xr.start_column_id else None,
                "end_column_id": str(xr.end_column_id) if xr.end_column_id else None,
            })
        return {
            "sheet_id": sheet_id,
            "cross_sheet_references": refs,
            "count": len(refs),
            "note": "These are the ranges this sheet references from other sheets. Status OK means data is live."
        }
    except Exception as e:
        return {"error": str(e)}


def tool_get_linked_sheet_value(sheet_id: str, row_id: str, column_name: str) -> dict:
    """
    Get the source value of a cross-sheet linked cell — follows the link to its origin sheet.
    Use when a cell shows a value linked from another sheet and you need to know the source.
    """
    client = _get_current_client()
    try:
        sheet = client.Sheets.get_sheet(int(sheet_id))
        col_map = {col.title: col.id_ for col in sheet.columns}
        rev_map = {col.id_: col.title for col in sheet.columns}

        col_id = col_map.get(column_name)
        if not col_id:
            return {"error": f"Column '{column_name}' not found in sheet"}

        for row in (sheet.rows or []):
            if str(row.id) == str(row_id):
                for cell in row.cells:
                    if cell.column_id == col_id and cell.link_in_from_cell:
                        link = cell.link_in_from_cell
                        # Fetch source sheet to get the actual value
                        try:
                            src_sheet = client.Sheets.get_sheet(int(link.sheet_id))
                            src_rev_map = {col.id_: col.title for col in src_sheet.columns}
                            for src_row in (src_sheet.rows or []):
                                if str(src_row.id) == str(link.row_id):
                                    for src_cell in src_row.cells:
                                        if str(src_cell.column_id) == str(link.column_id):
                                            return {
                                                "column": column_name,
                                                "display_value": safe_cell_value(cell),
                                                "source_sheet_id": str(link.sheet_id),
                                                "source_sheet_name": link.sheet_name,
                                                "source_value": safe_cell_value(src_cell),
                                                "link_status": link.status
                                            }
                        except Exception as e:
                            return {"error": f"Could not fetch source sheet: {e}", "link_status": link.status}
        return {"error": "Row or linked cell not found"}
    except Exception as e:
        return {"error": str(e)}



def tool_get_sheet_by_name(sheet_name: str, workspace_id: str = None) -> dict:
    """
    Find and fetch a sheet by name. workspace_id: if provided, searches only within that workspace (recommended to avoid finding wrong sheets). Without workspace_id searches globally.
    """
    client = _get_current_client()
    try:
        if workspace_id:
            # Scoped search — only look in this workspace
            ws = client.Workspaces.get_workspace(int(workspace_id), load_all=True)
            # Collect all sheets recursively from workspace
            all_sheet_refs = list(ws.sheets or [])
            def collect_from_folder(folder):
                refs = list(folder.sheets or [])
                for sub in (folder.folders or []):
                    refs.extend(collect_from_folder(sub))
                return refs
            for folder in (ws.folders or []):
                all_sheet_refs.extend(collect_from_folder(folder))
            matches = [s for s in all_sheet_refs if sheet_name.lower() in s.name.lower()]
        else:
            # Global search — searches all sheets in account
            all_sheets = client.Sheets.list_sheets(include_all=True)
            matches = [s for s in all_sheets.data
                       if sheet_name.lower() in s.name.lower()]
        
        if not matches:
            return {
                "error": f"No sheet found with name containing '{sheet_name}'",
                "hint": "Try a shorter search term or check the exact sheet name"
            }
        
        # Exact match preferred
        exact = [s for s in matches if s.name.lower() == sheet_name.lower()]
        
        # If no exact match and multiple partial matches — return list for user to choose
        if not exact and len(matches) > 1:
            return {
                "error": "multiple_matches",
                "message": f"Found {len(matches)} sheets matching '{sheet_name}'. Please confirm which one:",
                "matches": [{"name": s.name, "id": str(s.id)} for s in matches[:5]],
                "hint": "Use the exact sheet name to avoid ambiguity"
            }
        
        target = exact[0] if exact else matches[0]
        
        # If partial match, confirm what was found
        if not exact:
            found_note = f"Note: No exact match for '{sheet_name}'. Using closest match: '{target.name}'"
        else:
            found_note = None
        
        # Now fetch the full sheet
        sheet = client.Sheets.get_sheet(target.id)
        col_id_to_name = {col.id_: col.title for col in sheet.columns}
        
        UNWRITABLE = {"AUTO_NUMBER","CREATED_DATE","MODIFIED_DATE","CREATED_BY","MODIFIED_BY"}
        columns_meta = []
        for col in sheet.columns:
            try:
                has_formula = bool(col.formula)
                has_system = bool(col.system_column_type and str(col.system_column_type) in UNWRITABLE)
                has_autonum = bool(col.auto_number_format)
                meta = {
                    "id": str(col.id_),
                    "title": str(col.title or ""),
                    "type": str(col.type_ or "TEXT_NUMBER"),
                    "writable": not (has_formula or has_system or has_autonum),
                    "auto_filled": has_formula or has_system or has_autonum
                }
                if has_system:
                    meta["skip_reason"] = f"system ({col.system_column_type})"
                elif has_autonum:
                    meta["skip_reason"] = "auto-number"
                elif has_formula:
                    meta["skip_reason"] = "formula"
                if col.options:
                    try: meta["options"] = [str(o) for o in col.options]
                    except Exception: pass
                # Contact list restricted contacts
                if col.contact_options:
                    try:
                        contacts = []
                        for co in col.contact_options:
                            name = getattr(co, 'name', '') or ''
                            email = getattr(co, 'email', '') or ''
                            if email:
                                contacts.append({"name": name, "email": email, "label": f"{name} ({email})" if name else email})
                            elif name:
                                contacts.append({"name": name, "email": "", "label": name})
                        if contacts:
                            meta["contact_options"] = contacts
                    except Exception:
                        pass
                columns_meta.append(meta)
            except Exception:
                columns_meta.append({"id": str(getattr(col,'id_','?')), "title": str(getattr(col,'title','?')), "type": "TEXT_NUMBER", "writable": True, "auto_filled": False})

        user_cols = [c["title"] for c in columns_meta if c.get("writable") and not c.get("auto_filled")]
        auto_cols = [c["title"] for c in columns_meta if not c.get("writable")]

        OPTIONAL_KEYWORDS = ["comment","link","note","remark","deadline","actual","archive","business impact","description"]
        AUTO_STATUS_KEYWORDS = ["status","approval","approved","provisioned","provision","created","modified","director app","vp approval","full project","project created","project link","assigned to ops","record date"]
        required_cols, optional_cols = [], []
        for c in columns_meta:
            if not c.get("writable") or c.get("auto_filled"): continue
            # Skip status/approval — auto-set by Smartsheet automations
            if any(k in c["title"].lower() for k in AUTO_STATUS_KEYWORDS):
                continue
            if c.get("type") == "CHECKBOX" or any(k in c["title"].lower() for k in OPTIONAL_KEYWORDS):
                optional_cols.append(c["title"])
            else:
                required_cols.append(c["title"])

        rows = []
        for row in (sheet.rows or [])[:100]:
            try:
                row_data = {"_row_id": str(row.id), "_row_number": row.row_number}
                for cell in row.cells:
                    try:
                        col_name = col_id_to_name.get(cell.column_id, str(cell.column_id))
                        row_data[col_name] = safe_cell_value(cell)
                    except Exception: pass
                rows.append(row_data)
            except Exception: pass

        # Identify auto-status fields to show in form info box
        auto_status_fields = [c["title"] for c in columns_meta
                              if not c.get("auto_filled") and any(k in c["title"].lower() for k in AUTO_STATUS_KEYWORDS)]

                # Build rich column definitions for FORM:: generation
        form_fields = []
        for c in columns_meta:
            if c.get("auto_filled"): continue
            # Skip status/approval columns — update automatically via SCC or automation
            if any(k in c["title"].lower() for k in AUTO_STATUS_KEYWORDS):
                continue
            field = {
                "name": c["title"],
                "label": c["title"],
                "col_type": c["type"],
                "required": c["title"] in required_cols
            }
            t = c["type"].upper()
            if t in ("PICKLIST", "MULTI_PICKLIST") and c.get("options"):
                field["field_type"] = "select"
                field["options"] = c["options"]
                if t == "MULTI_PICKLIST":
                    field["multi"] = True
            elif t == "CONTACT_LIST":
                field["field_type"] = "contact"
                if c.get("contact_options"):
                    field["options"] = c["contact_options"]
            elif t == "CHECKBOX":
                field["field_type"] = "checkbox"
            elif t == "DATE":
                field["field_type"] = "date"
            elif t == "TEXT_NUMBER":
                field["field_type"] = "text"
            else:
                field["field_type"] = "text"
            form_fields.append(field)

        return {
            "sheet_id": str(target.id),
            "sheet_name": target.name,
            "required_columns": required_cols,
            "optional_columns": optional_cols,
            "auto_filled_columns": auto_cols,
            "columns_metadata": columns_meta,
            "form_fields": form_fields,
            "auto_status_fields": auto_status_fields,
            "row_count": len(sheet.rows or []),
            "rows": rows,
            "instruction": f"sheet_id={target.id}. Use form_fields to build FORM:: — field_type and options are already set. required_columns={required_cols}"
        }
    except Exception as e:
        return {"error": str(e), "sheet_name": sheet_name}



# ═══════════════════════════════════════════════════════════════
# EMAIL / NUDGE TOOLS
# ═══════════════════════════════════════════════════════════════

def tool_send_row_email(sheet_id: str, row_ids: list, recipient_emails: list,
                        subject: str, message: str, cc_me: bool = False) -> dict:
    """
    Email specific rows from a sheet to one or more recipients.
    Use to nudge a PM about a delayed project, share status with stakeholders,
    or alert someone about a specific record.
    row_ids: list of row IDs (strings) to include in the email.
    recipient_emails: list of email addresses to send to.
    """
    import smartsheet as ss_lib
    client = _get_current_client()
    try:
        email_obj = ss_lib.models.MultiRowEmail()
        email_obj.send_to = [
            ss_lib.models.Recipient({'email': e.strip()}) for e in recipient_emails
        ]
        email_obj.subject = subject
        email_obj.message = message
        email_obj.cc_me = cc_me
        email_obj.include_attachments = False
        email_obj.include_discussions = False
        email_obj.row_ids = [int(r) for r in row_ids]

        result = client.Sheets.send_rows(int(sheet_id), email_obj)
        logger.info("Row email sent", sheet_id=sheet_id, recipients=recipient_emails, rows=row_ids)
        return {
            "success": True,
            "message": f"✅ Email sent to {', '.join(recipient_emails)} with {len(row_ids)} row(s) from sheet {sheet_id}",
            "subject": subject,
            "recipients": recipient_emails
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_request_row_update(sheet_id: str, row_ids: list, recipient_emails: list,
                             subject: str, message: str) -> dict:
    """
    Send an update request to recipients — they receive an email with a link
    to edit specific rows directly without needing Smartsheet access.
    Perfect for: asking a PM to update project status, requesting budget approval,
    or nudging someone to fill in missing fields.
    """
    import requests as req_lib
    from utils.config import get_settings
    settings = get_settings()

    headers = {
        "Authorization": f"Bearer {settings.smartsheet_api_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "sendTo": [{"email": e.strip()} for e in recipient_emails],
        "subject": subject,
        "message": message,
        "rowIds": [int(r) for r in row_ids],
        "includeAttachments": False,
        "includeDiscussions": False,
        "ccMe": False
    }

    url = f"https://api.smartsheet.com/2.0/sheets/{sheet_id}/updaterequests"
    try:
        response = req_lib.post(url, json=payload, headers=headers)
        data = response.json()
        if response.status_code in (200, 201):
            logger.info("Update request sent", sheet_id=sheet_id, recipients=recipient_emails)
            return {
                "success": True,
                "message": f"✅ Update request sent to {', '.join(recipient_emails)} — they can edit the row(s) directly via email link",
                "subject": subject,
                "recipients": recipient_emails,
                "rows": len(row_ids)
            }
        else:
            return {"success": False, "error": data.get("message", str(data)), "status": response.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_find_contact_in_sheet(sheet_id: str, name_or_email: str) -> dict:
    """
    Search a sheet for a contact by name or partial email match.
    Returns matching rows with contact email addresses.
    Use before send_row_email to find the right PM email from a sheet.
    """
    client = _get_current_client()
    try:
        sheet = client.Sheets.get_sheet(int(sheet_id))
        col_map = {col.id_: col.title for col in sheet.columns}
        matches = []
        query = name_or_email.lower()

        for row in (sheet.rows or []):
            row_data = {"_row_id": str(row.id), "_row_number": row.row_number}
            found = False
            for cell in row.cells:
                val = safe_cell_value(cell)
                row_data[col_map.get(cell.column_id, str(cell.column_id))] = val
                if query in val.lower():
                    found = True
            if found:
                matches.append(row_data)

        return {
            "query": name_or_email,
            "matches": matches[:10],
            "count": len(matches),
            "hint": "Use _row_id from matching rows with send_row_email or request_row_update"
        }
    except Exception as e:
        return {"error": str(e)}



def tool_get_sheet_summary(sheet_id: str) -> dict:
    """
    Get a compact analytical summary of a sheet — perfect for dashboard creation.
    Returns: column list, row count, status breakdowns, numeric aggregations,
    top values per column, and sample rows. Much smaller than get_sheet.
    Use this instead of get_sheet when building a DASHBOARD::.
    """
    client = _get_current_client()
    try:
        sheet = client.Sheets.get_sheet(int(sheet_id))
    except Exception as e:
        return {"error": str(e)}

    col_id_map = {col.id_: col.title for col in sheet.columns}
    UNWRITABLE = {"AUTO_NUMBER","CREATED_DATE","MODIFIED_DATE","CREATED_BY","MODIFIED_BY"}

    columns_info = []
    for col in sheet.columns:
        ci = {
            "title": col.title,
            "type": str(col.type_ or "TEXT_NUMBER"),
            "writable": not (col.formula or (col.system_column_type and str(col.system_column_type) in UNWRITABLE) or col.auto_number_format)
        }
        if col.options:
            try: ci["options"] = [str(o) for o in col.options]
            except: pass
        columns_info.append(ci)

    # Parse all rows for aggregation
    all_rows = []
    for row in (sheet.rows or []):
        rd = {}
        for cell in row.cells:
            col_name = col_id_map.get(cell.column_id, str(cell.column_id))
            rd[col_name] = safe_cell_value(cell)
        if rd:
            all_rows.append(rd)

    row_count = len(all_rows)
    if row_count == 0:
        return {"sheet_id": sheet_id, "sheet_name": sheet.name, "row_count": 0,
                "columns": columns_info, "message": "Sheet is empty"}

    # Per-column analysis
    column_analysis = {}
    for col in sheet.columns:
        title = col.title
        col_type = str(col.type_ or "")
        values = [r[title] for r in all_rows if r.get(title, "")]

        if not values:
            continue

        if col_type in ("PICKLIST", "TEXT_NUMBER", "MULTI_PICKLIST") or col_type == "":
            # Value frequency count
            freq = {}
            for v in values:
                freq[v] = freq.get(v, 0) + 1
            # Sort by count
            top = sorted(freq.items(), key=lambda x: -x[1])[:10]
            column_analysis[title] = {
                "type": "categorical",
                "distinct_values": len(freq),
                "value_counts": dict(top),
                "total_filled": len(values),
                "fill_rate": f"{int(len(values)/row_count*100)}%"
            }

        elif col_type == "CHECKBOX":
            true_count = sum(1 for v in values if str(v).lower() in ("true","yes","1"))
            column_analysis[title] = {
                "type": "boolean",
                "true_count": true_count,
                "false_count": len(values) - true_count,
                "true_pct": f"{int(true_count/len(values)*100)}%" if values else "0%"
            }

        elif col_type == "DATE":
            column_analysis[title] = {
                "type": "date",
                "earliest": min(values),
                "latest": max(values),
                "filled": len(values)
            }

        else:
            # Try numeric
            nums = []
            for v in values:
                try: nums.append(float(str(v).replace(",","").replace("$","").replace("₹","")))
                except: pass
            if nums:
                column_analysis[title] = {
                    "type": "numeric",
                    "count": len(nums),
                    "sum": round(sum(nums), 2),
                    "avg": round(sum(nums)/len(nums), 2),
                    "min": min(nums),
                    "max": max(nums),
                    "fill_rate": f"{int(len(nums)/row_count*100)}%"
                }

    # Sample rows (first 5 + last 3)
    sample_rows = all_rows[:5]
    if len(all_rows) > 5:
        sample_rows += all_rows[-3:]

    return {
        "sheet_id": sheet_id,
        "sheet_name": sheet.name,
        "row_count": row_count,
        "column_count": len(sheet.columns),
        "columns": columns_info,
        "column_analysis": column_analysis,
        "sample_rows": sample_rows,
        "instruction": "Use column_analysis value_counts for chart labels/values. Build DASHBOARD:: from this data — compute percentages and insights yourself."
    }


# ═══════════════════════════════════════════════════════════════
# MCP TOOL REGISTRY
# This is what Claude sees as available tools
# ═══════════════════════════════════════════════════════════════

MCP_TOOLS = [
    {
        "name": "list_workspaces",
        "description": "List all Smartsheet workspaces the user has access to. Call this first to get workspace IDs.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },    {
        "name": "get_workspace_contents",
        "description": "Get contents of a workspace. shallow=True (default)=fast folder list. shallow=False=full recursive (slow).",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "shallow": {"type": "boolean", "description": "True=fast folder names only (default). False=slow full recursive listing."}
            },
            "required": ["workspace_id"]
        }
    },
    {
        "name": "get_folder_contents",
        "description": "Get sheets/reports inside a folder by folder_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder_id": {"type": "string", "description": "Folder ID from get_workspace_contents"}
            },
            "required": ["folder_id"]
        }
    },
    {
        "name": "list_sheets",
        "description": "List all sheets across all workspaces.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_sheet",
        "description": "Get full sheet data including all columns and rows. Use for reading data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "max_rows": {"type": "integer", "default": 500, "description": "Max rows to fetch"}
            },
            "required": ["sheet_id"]
        }
    },
    {
        "name": "filter_rows",
        "description": "Filter rows. Use OVERDUE on date cols for past-due. group_by groups results and finds concentration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "filters": {"type": "object", "description": "Column->value pairs. ~ prefix=contains, numeric ops: >100 <50. Special: 'OVERDUE' on date cols finds past-due rows."},
                "overdue_column": {"type": "string", "description": "Date column to check for overdue rows (date < today)"},
                "group_by": {"type": "string", "description": "Group results by this column to find concentration e.g. 'Region', 'Division'"}
            },
            "required": ["sheet_id", "filters"]
        }
    },
    {
        "name": "aggregate_column",
        "description": "Aggregate numeric column. group_by groups results. compare_column compares budget vs actual spend for variance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "metric_column": {"type": "string", "description": "Column to aggregate (e.g. 'Budget', 'Actual Spend')"},
                "group_by": {"type": "string", "description": "Primary group e.g. 'Region', 'Division', 'Country'"},
                "group_by_2": {"type": "string", "description": "Secondary group for cross-tab e.g. 'Status'"},
                "compare_column": {"type": "string", "description": "Compare metric_column vs this column e.g. 'Budget' vs 'Actual' — reveals over/under-budget patterns"}
            },
            "required": ["sheet_id", "metric_column"]
        }
    },
    {
        "name": "get_project_status_summary",
        "description": "Project status summary with chart_data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "status_column": {"type": "string", "default": "Status"},
                "name_column": {"type": "string", "default": "Project Name"}
            },
            "required": ["sheet_id"]
        }
    },
    {
        "name": "create_row",
        "description": "Create a new row in a sheet. Use column names as keys.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "row_data": {"type": "object", "description": "Column name to value map"}
            },
            "required": ["sheet_id", "row_data"]
        }
    },
    {
        "name": "update_row",
        "description": "Update specific cells in a row. Requires row_id from get_sheet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "row_id": {"type": "string"},
                "updates": {"type": "object", "description": "Column name to new value map"}
            },
            "required": ["sheet_id", "row_id", "updates"]
        }
    },
    {
        "name": "delete_row",
        "description": "Delete row. Always confirm first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "row_id": {"type": "string"}
            },
            "required": ["sheet_id", "row_id"]
        }
    },
    {
        "name": "list_dashboards",
        "description": "List all dashboards.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_dashboard",
        "description": "Get dashboard widgets. fetch_data=False(default)=fast. fetch_data=True=loads widget data from linked reports/sheets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sight_id": {"type": "string", "description": "Dashboard ID"},
                "fetch_data": {"type": "boolean", "description": "True=fetch data from widgets. Default false."}
            },
            "required": ["sight_id"]
        }
    },
    {
        "name": "create_dashboard",
        "description": "Create a new dashboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "workspace_id": {"type": "string", "description": "Optional workspace to place it in"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "add_widget_to_dashboard",
        "description": "Add widget to dashboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sight_id": {"type": "string"},
                "widget_type": {"type": "string", "enum": ["TITLE", "METRIC", "CHART", "REPORT", "SHORTCUT"]},
                "title": {"type": "string"},
                "sheet_id": {"type": "string"}
            },
            "required": ["sight_id", "widget_type", "title"]
        }
    },
    {
        "name": "list_scc_programs",
        "description": "List Control Center programs.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "list_blueprints",
        "description": "List blueprints in a program.",
        "input_schema": {
            "type": "object",
            "properties": {"program_id": {"type": "string"}},
            "required": ["program_id"]
        }
    },
    {
        "name": "rollout_project",
        "description": "Rollout project via intake sheet auto-provisioning. Writes row + sets approval to trigger SCC. Confirm first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "intake_sheet_id": {"type": "string", "description": "Sheet ID of the SCC intake sheet — get via get_sheet_by_name"},
                "profile_data": {
                    "type": "object",
                    "description": "Project profile fields matching intake sheet columns e.g. {'Project Name': 'Site Mumbai', 'PM': 'Rahul Singh', 'Start Date': '2026-05-01', 'Budget': '500000', 'Region': 'West'}"
                },
                "approval_column": {"type": "string", "description": "Name of the approval column on the intake sheet (default: Approved)", "default": "Approved"},
                "approval_value": {"type": "string", "description": "Value that triggers auto-provisioning — 'true' for checkbox, or dropdown value like 'Approved'", "default": "true"}
            },
            "required": ["intake_sheet_id", "profile_data"]
        }
    },
    {
        "name": "list_scc_projects",
        "description": "List rolled-out projects.",
        "input_schema": {
            "type": "object",
            "properties": {"program_id": {"type": "string"}},
            "required": ["program_id"]
        }
    },
    {
        "name": "list_automations",
        "description": "List automations on a sheet.",
        "input_schema": {
            "type": "object",
            "properties": {"sheet_id": {"type": "string"}},
            "required": ["sheet_id"]
        }
    },
    {
        "name": "create_automation",
        "description": "Create automation with trigger and optional conditions. trigger_type: WHEN_ROWS_ADDED/CHANGED/DELETED/WHEN_CELL_CHANGED.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "rule_name": {"type": "string"},
                "action_type": {"type": "string", "description": "NOTIFICATION, UPDATE_REQUEST, APPROVAL_REQUEST, LOCK_ROW"},
                "message": {"type": "string"},
                "subject": {"type": "string"},
                "trigger_type": {"type": "string", "description": "WHEN_ROWS_ADDED (default), WHEN_ROWS_CHANGED, WHEN_ROWS_DELETED, WHEN_CELL_CHANGED"},
                "trigger_column": {"type": "string", "description": "For WHEN_CELL_CHANGED: column name to watch"},
                "condition_column": {"type": "string", "description": "Only fire when this column equals condition_value. e.g. 'Status'"},
                "condition_value": {"type": "string", "description": "Value to match for condition. e.g. 'Approved'"},
                "notify_all_users": {"type": "boolean", "description": "Notify all shared users"},
                "recipient_emails": {"type": "array", "items": {"type": "string"}, "description": "Specific emails to notify"},
                "frequency": {"type": "string", "description": "IMMEDIATELY (default), DAILY, WEEKLY"}
            },
            "required": ["sheet_id", "rule_name", "action_type", "message"]
        }
    },
    {
        "name": "update_automation",
        "description": "Enable/disable/update an automation rule.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "rule_id": {"type": "string"},
                "enabled": {"type": "boolean"},
                "message": {"type": "string"}
            },
            "required": ["sheet_id", "rule_id"]
        }
    },
    {
        "name": "delete_automation",
        "description": "Delete automation rule. Confirm first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "rule_id": {"type": "string"}
            },
            "required": ["sheet_id", "rule_id"]
        }
    },
    {
        "name": "create_webhook",
        "description": "Create webhook on sheet for real-time events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "name": {"type": "string"},
                "callback_url": {"type": "string", "description": "URL to POST events to"}
            },
            "required": ["sheet_id", "name", "callback_url"]
        }
    },
    {
        "name": "list_webhooks",
        "description": "List all webhooks.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_sheet_with_links",
        "description": "Get sheet data with cross-sheet links resolved.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "max_rows": {"type": "integer", "default": 200}
            },
            "required": ["sheet_id"]
        }
    },
    {
        "name": "list_cross_sheet_references",
        "description": "List cross-sheet references and their status.",
        "input_schema": {
            "type": "object",
            "properties": {"sheet_id": {"type": "string"}},
            "required": ["sheet_id"]
        }
    },
    {
        "name": "get_linked_sheet_value",
        "description": "Follow cross-sheet cell link to source.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "row_id": {"type": "string"},
                "column_name": {"type": "string"}
            },
            "required": ["sheet_id", "row_id", "column_name"]
        }
    },
    {
        "name": "get_sheet_by_name",
        "description": "Find sheet by name. Pass workspace_id to scope search. Returns form_fields with column types and options.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string", "description": "Exact or partial sheet name"},
                "workspace_id": {"type": "string", "description": "Workspace ID to scope search. Pass this whenever the user is working within a specific workspace."}
            },
            "required": ["sheet_name"]
        }
    },
    {
        "name": "get_sheet_summary",
        "description": "Compact sheet analytics: value counts, numeric stats. Use for DASHBOARD:: instead of get_sheet to avoid token overflow.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string", "description": "Sheet ID to summarise"}
            },
            "required": ["sheet_id"]
        }
    },
    {
        "name": "search_sheets",
        "description": "Search all Smartsheet content.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    },
    {
        "name": "send_row_email",
        "description": "Email specific rows via Smartsheet. No external email needed. Use to nudge delayed PMs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "row_ids": {"type": "array", "items": {"type": "string"}, "description": "Row IDs to include in email"},
                "recipient_emails": {"type": "array", "items": {"type": "string"}, "description": "Email addresses to send to"},
                "subject": {"type": "string", "description": "Email subject line"},
                "message": {"type": "string", "description": "Personal message to include above the row data"},
                "cc_me": {"type": "boolean", "description": "CC the API token owner", "default": False}
            },
            "required": ["sheet_id", "row_ids", "recipient_emails", "subject", "message"]
        }
    },
    {
        "name": "request_row_update",
        "description": "Send update request — PM edits rows directly via email link. No Smartsheet login needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "row_ids": {"type": "array", "items": {"type": "string"}, "description": "Row IDs the recipient should update"},
                "recipient_emails": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "message": {"type": "string", "description": "Message explaining what needs to be updated and why"}
            },
            "required": ["sheet_id", "row_ids", "recipient_emails", "subject", "message"]
        }
    },
    {
        "name": "find_contact_in_sheet",
        "description": "Search a sheet for a contact by name or email. Use before send_row_email to find the right PM or owner email address.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_id": {"type": "string"},
                "name_or_email": {"type": "string", "description": "Name or partial email to search for"}
            },
            "required": ["sheet_id", "name_or_email"]
        }
    }
]

# Dispatcher: tool name -> function
MCP_TOOL_DISPATCH = {
    "list_workspaces": lambda **kw: tool_list_workspaces(),
    "get_workspace_contents": lambda **kw: tool_get_workspace_contents(**kw),
    "get_folder_contents": lambda **kw: tool_get_folder_contents(**kw),
    "list_sheets": lambda **kw: tool_list_sheets(),
    "get_sheet": lambda **kw: tool_get_sheet(**kw),
    "filter_rows": lambda **kw: tool_filter_rows(**kw),
    "aggregate_column": lambda **kw: tool_aggregate_column(**kw),
    "get_project_status_summary": lambda **kw: tool_get_project_status_summary(**kw),
    "create_row": lambda **kw: tool_create_row(**kw),
    "update_row": lambda **kw: tool_update_row(**kw),
    "delete_row": lambda **kw: tool_delete_row(**kw),
    "list_dashboards": lambda **kw: tool_list_dashboards(),
    "get_dashboard": lambda **kw: tool_get_dashboard(**kw),
    "create_dashboard": lambda **kw: tool_create_dashboard(**kw),
    "add_widget_to_dashboard": lambda **kw: tool_add_widget_to_dashboard(**kw),
    "list_scc_programs": lambda **kw: tool_list_scc_programs(),
    "list_blueprints": lambda **kw: tool_list_blueprints(**kw),
    "rollout_project": lambda **kw: tool_rollout_project(**kw),
    "list_scc_projects": lambda **kw: tool_list_scc_projects(**kw),
    "get_sheet_with_links": lambda **kw: tool_get_sheet_with_links(**kw),
    "list_cross_sheet_references": lambda **kw: tool_list_cross_sheet_references(**kw),
    "get_linked_sheet_value": lambda **kw: tool_get_linked_sheet_value(**kw),
    "get_sheet_by_name": lambda **kw: tool_get_sheet_by_name(**kw),
    "get_sheet_summary": lambda **kw: tool_get_sheet_summary(**kw),
    "search_sheets": lambda **kw: tool_search_sheets(**kw),
    "list_automations": lambda **kw: tool_list_automations(**kw),
    "create_automation": lambda **kw: tool_create_automation(**kw),
    "update_automation": lambda **kw: tool_update_automation(**kw),
    "delete_automation": lambda **kw: tool_delete_automation(**kw),
    "create_webhook": lambda **kw: tool_create_webhook(**kw),
    "list_webhooks": lambda **kw: tool_list_webhooks(),
    "send_row_email": lambda **kw: tool_send_row_email(**kw),
    "request_row_update": lambda **kw: tool_request_row_update(**kw),
    "find_contact_in_sheet": lambda **kw: tool_find_contact_in_sheet(**kw),
}


def execute_tool(name: str, input_args: dict, smartsheet_token: str = None) -> dict:
    """Execute a tool by name.
    If smartsheet_token provided, stores it in thread-local so all get_client()
    calls within this request use the user's own token.
    """
    fn = MCP_TOOL_DISPATCH.get(name)
    if not fn:
        return {"error": f"Unknown tool: {name}"}
    try:
        # Set per-user token in thread-local storage
        _request_local.smartsheet_token = smartsheet_token if smartsheet_token else None
        result = fn(**input_args)
        logger.info("Tool executed", tool=name, success=True)
        return result
    except Exception as e:
        logger.error("Tool execution failed", tool=name, error=str(e))
        return {"error": str(e), "tool": name}
    finally:
        # Always clear token after tool execution
        _request_local.smartsheet_token = None


# ═══════════════════════════════════════════════════════════════
# STANDALONE MCP SERVER (runs via stdio for Claude Desktop)
# ═══════════════════════════════════════════════════════════════

async def run_mcp_stdio_server():
    """
    Run as a stdio MCP server compatible with Claude Desktop.
    Claude Desktop config:
    {
      "mcpServers": {
        "smartsheet": {
          "command": "python",
          "args": ["/path/to/mcp/smartsheet_mcp_server.py"],
          "env": {
            "SMARTSHEET_API_TOKEN": "...",
            "ANTHROPIC_API_KEY": "..."
          }
        }
      }
    }
    """
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        import mcp.types as types

        server = Server("smartsheet-agent")

        @server.list_tools()
        async def list_tools():
            return [
                types.Tool(
                    name=t["name"],
                    description=t["description"],
                    inputSchema=t["input_schema"]
                )
                for t in MCP_TOOLS
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict):
            result = execute_tool(name, arguments)
            return [types.TextContent(type="text", text=json.dumps(result, default=str, indent=2))]

        logger.info("Starting Smartsheet MCP stdio server")
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    except ImportError:
        logger.error("mcp package not installed. Run: pip install mcp")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_mcp_stdio_server())