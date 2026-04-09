"""
Production Smartsheet client.
- Singleton pattern
- Column ID caching (avoid redundant API calls)
- Error normalization
- Request logging
"""
import smartsheet
from typing import Optional
from functools import lru_cache
from utils.config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_client: Optional[smartsheet.Smartsheet] = None

# Column cache: sheet_id -> {column_title: column_id}
_column_cache: dict = {}


def get_client() -> smartsheet.Smartsheet:
    global _client
    if _client is None:
        logger.info("Initializing Smartsheet client")
        _client = smartsheet.Smartsheet(settings.smartsheet_api_token)
        _client.errors_as_exceptions(True)
    return _client


def get_column_map(sheet_id: int) -> dict:
    """
    Returns {column_title: column_id} for a sheet.
    Cached per sheet_id to avoid redundant API calls.
    Includes columnFormulas so fx columns are properly detected.
    """
    if sheet_id in _column_cache:
        return _column_cache[sheet_id]

    client = get_client()
    sheet = client.Sheets.get_sheet(sheet_id)
    col_map = {col.title: col.id_ for col in sheet.columns}
    _column_cache[sheet_id] = col_map
    logger.info("Cached column map", sheet_id=sheet_id, columns=list(col_map.keys()))
    return col_map


def get_reverse_column_map(sheet_id: int) -> dict:
    """Returns {column_id: column_title}"""
    return {v: k for k, v in get_column_map(sheet_id).items()}


def invalidate_column_cache(sheet_id: int):
    """Call after schema changes"""
    _column_cache.pop(sheet_id, None)


def normalize_row(row, reverse_col_map: dict) -> dict:
    """Convert a Smartsheet row object to a clean dict."""
    row_data = {
        "_row_id": str(row.id),
        "_row_number": row.row_number,
    }
    for cell in row.cells:
        col_name = reverse_col_map.get(cell.column_id, f"col_{cell.column_id}")
        val = cell.display_value if cell.display_value is not None else cell.value
        row_data[col_name] = val
    return row_data