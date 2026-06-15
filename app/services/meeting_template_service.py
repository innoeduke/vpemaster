"""Meeting template I/O service.

Single source of truth for reading, writing, and listing the per-club CSV
meeting templates stored under ``app/static/club_resources/<club_id>/templates/``.
Centralizes filename sanitization, path-traversal safety, atomic writes, and
header validation so the meeting creation flow and the new Template Manager
page share one well-tested code path.
"""
import csv
import logging
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

from flask import current_app

logger = logging.getLogger(__name__)

TEMPLATES_SUBDIR = 'templates'
GLOBAL_SEED_CLUB_ID = 0

CSV_HEADER = [
    'Type', 'Title', 'Role', 'Owner', 'Duration_Min', 'Duration_Max', 'Hidden'
]


class TemplateError(Exception):
    """Base class for template service errors."""


class TemplateNameInvalid(TemplateError):
    """Raised when a template name fails sanitization."""


class TemplatePathEscape(TemplateError):
    """Raised when a path resolves outside the club's templates directory."""


class TemplateNotFound(TemplateError):
    """Raised when a requested template does not exist on disk."""


@dataclass
class TemplateInfo:
    filename: str
    display_name: str
    row_count: int
    mtime: float
    mtime_display: str = ''


def _static_root() -> str:
    return current_app.static_folder


def _club_dir(club_id: int) -> str:
    """Return (and create) the templates directory for the given club."""
    path = os.path.join(_static_root(), 'club_resources', str(club_id), TEMPLATES_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def _seed_dir() -> str:
    path = os.path.join(_static_root(), 'club_resources', str(GLOBAL_SEED_CLUB_ID), TEMPLATES_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def sanitize_filename(name: str) -> str:
    """Normalize a user-supplied template name into a safe filename stem.

    Rules:
    - Strip whitespace and a trailing ``.csv``.
    - Replace interior whitespace with ``_``.
    - Reject empty, path separators, ``..``, and leading ``.``.
    """
    if name is None:
        raise TemplateNameInvalid("Template name is required")

    cleaned = name.strip()
    if cleaned.lower().endswith('.csv'):
        cleaned = cleaned[:-4]
    cleaned = re.sub(r'\s+', '_', cleaned)

    if not cleaned:
        raise TemplateNameInvalid("Template name is required")
    if cleaned.startswith('.'):
        raise TemplateNameInvalid("Template name must not start with '.'")
    if '/' in cleaned or '\\' in cleaned or '..' in cleaned:
        raise TemplateNameInvalid("Template name contains invalid characters")

    return cleaned + '.csv'


def _safe_join(club_id: int, filename: str) -> str:
    """Join club dir + filename, refusing to escape the club's templates dir."""
    safe_name = sanitize_filename(filename)

    club_dir = os.path.abspath(_club_dir(club_id))
    target = os.path.abspath(os.path.join(club_dir, safe_name))

    if os.path.commonpath([club_dir, target]) != club_dir:
        raise TemplatePathEscape(f"Path escapes club templates directory: {filename}")

    return target


def seed_club_from_global(club_id: int) -> None:
    """Copy the global seed templates into the club's templates dir on first use."""
    club_dir = _club_dir(club_id)
    if os.listdir(club_dir):
        return

    seed = _seed_dir()
    if not os.path.exists(seed):
        return

    for item in os.listdir(seed):
        src = os.path.join(seed, item)
        dst = os.path.join(club_dir, item)
        if os.path.isfile(src) and item.endswith('.csv') and not os.path.exists(dst):
            shutil.copy2(src, dst)


def _filename_to_display(filename: str) -> str:
    stem = filename[:-4] if filename.lower().endswith('.csv') else filename
    return stem.replace('_', ' ').title()


def list_templates(club_id: int) -> List[TemplateInfo]:
    """List the templates available to ``club_id`` (in display order)."""
    seed_club_from_global(club_id)
    club_dir = _club_dir(club_id)
    results: List[TemplateInfo] = []
    try:
        entries = sorted(os.listdir(club_dir))
    except OSError as exc:
        logger.warning("Could not list templates for club %s: %s", club_id, exc)
        return results

    for filename in entries:
        if not filename.endswith('.csv') or filename.startswith('.'):
            continue
        full = os.path.join(club_dir, filename)
        try:
            stat = os.stat(full)
        except OSError:
            continue
        with open(full, 'r', encoding='utf-8') as f:
            row_count = max(0, sum(1 for _ in f) - 1)
        results.append(TemplateInfo(
            filename=filename,
            display_name=_filename_to_display(filename),
            row_count=row_count,
            mtime=stat.st_mtime,
            mtime_display=datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
        ))

    results.sort(key=lambda t: t.display_name.lower())
    return results


def get_template_filename_map(club_id: int) -> Dict[str, str]:
    """Return ``{display_name: filename}`` for legacy callers (chat, CLI)."""
    return {t.display_name: t.filename for t in list_templates(club_id)}


def list_seed_templates() -> List[TemplateInfo]:
    """List the global seed templates (club id 0)."""
    seed = _seed_dir()
    results: List[TemplateInfo] = []
    if not os.path.exists(seed):
        return results
    for filename in sorted(os.listdir(seed)):
        if not filename.endswith('.csv') or filename.startswith('.'):
            continue
        full = os.path.join(seed, filename)
        if not os.path.isfile(full):
            continue
        with open(full, 'r', encoding='utf-8') as f:
            row_count = max(0, sum(1 for _ in f) - 1)
        results.append(TemplateInfo(
            filename=filename,
            display_name=_filename_to_display(filename),
            row_count=row_count,
            mtime=os.path.getmtime(full),
            mtime_display=datetime.fromtimestamp(os.path.getmtime(full)).strftime('%Y-%m-%d %H:%M'),
        ))
    results.sort(key=lambda t: t.display_name.lower())
    return results


def get_template(club_id: int, filename: str) -> Dict:
    """Read a template into ``{header, rows}`` dicts.

    Reads by column position so legacy / hand-edited CSVs that lack the
    ``Hidden`` column or use ``Min``/``Max`` aliases still parse. Missing
    trailing columns are treated as empty; a totally empty file returns the
    canonical header and an empty row list.
    """
    path = _safe_join(club_id, filename)
    if not os.path.exists(path):
        raise TemplateNotFound(filename)

    rows: List[Dict] = []
    try:
        with open(path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            first = next(reader, None)
            if first is None:
                return {'header': CSV_HEADER, 'rows': []}

            # Heuristic: if the first row looks like a header (any non-empty
            # cell matches one of our known column names, case-insensitive),
            # treat it as a header and skip it. Otherwise it's a data row.
            known = {h.lower() for h in CSV_HEADER} | {'min', 'max'}
            first_lower = {cell.strip().lower() for cell in first if cell.strip()}
            if first_lower and first_lower.issubset(known):
                data_rows = list(reader)
            else:
                data_rows = [first] + list(reader)

            for raw in data_rows:
                if not any(cell.strip() for cell in raw):
                    continue
                rows.append({
                    'type': raw[0].strip() if len(raw) > 0 else '',
                    'title': raw[1].strip() if len(raw) > 1 else '',
                    'role': raw[2].strip() if len(raw) > 2 else '',
                    'owner': raw[3].strip() if len(raw) > 3 else '',
                    'duration_min': raw[4].strip() if len(raw) > 4 else '',
                    'duration_max': raw[5].strip() if len(raw) > 5 else '',
                    'hidden': (raw[6].strip().lower() == 'true') if len(raw) > 6 else False,
                })
    except (OSError, csv.Error) as exc:
        logger.warning("Could not read template %s for club %s: %s", filename, club_id, exc)
        return {'header': CSV_HEADER, 'rows': []}

    return {'header': CSV_HEADER, 'rows': rows}


def save_template(club_id: int, filename: str, rows: List[Dict]) -> None:
    """Write ``rows`` back to ``filename`` atomically (tmp + os.replace)."""
    path = _safe_join(club_id, filename)
    club_dir = os.path.dirname(path)
    tmp = path + '.tmp'

    with open(tmp, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        for row in rows or []:
            writer.writerow([
                (row.get('type') or '').strip(),
                (row.get('title') or '').strip(),
                (row.get('role') or '').strip(),
                (row.get('owner') or '').strip(),
                row.get('duration_min') if row.get('duration_min') not in (None, '') else '',
                row.get('duration_max') if row.get('duration_max') not in (None, '') else '',
                'true' if row.get('hidden') else '',
            ])

    os.replace(tmp, path)


def delete_template(club_id: int, filename: str) -> None:
    path = _safe_join(club_id, filename)
    if not os.path.exists(path):
        raise TemplateNotFound(filename)
    os.remove(path)


def create_from_seed(club_id: int, seed_filename: str, new_name: str) -> str:
    """Copy a global seed template into the club's templates dir."""
    seed_path = os.path.join(_seed_dir(), sanitize_filename(seed_filename))
    if not os.path.exists(seed_path):
        raise TemplateNotFound(seed_filename)

    target_name = sanitize_filename(new_name)
    target = _safe_join(club_id, target_name)
    if os.path.exists(target):
        raise TemplateNameInvalid(f"Template '{target_name}' already exists")

    shutil.copy2(seed_path, target)
    return target_name


def parse_template_rows(club_id: int, filename: str) -> List[Dict]:
    """Return the rows of a template as a list of dicts.

    Used by ``_generate_logs_from_template`` in agenda_routes to keep the
    meeting-creation business logic in that file.
    """
    return get_template(club_id, filename)['rows']


def logs_to_template_rows(logs) -> List[Dict]:
    """Adapt ``SessionLog`` rows to the shape ``save_template`` writes."""
    rows: List[Dict] = []
    for log in logs:
        st = log.session_type
        type_title = st.Title if st else ''
        session_title = log.Session_Title or ''
        if type_title and type_title not in ('Section', 'Generic'):
            session_title = type_title
        role_name = st.role.name if st and st.role else ''

        rows.append({
            'type': type_title,
            'title': session_title,
            'role': role_name,
            'owner': '',
            'duration_min': log.Duration_Min if log.Duration_Min is not None else '',
            'duration_max': log.Duration_Max if log.Duration_Max is not None else '',
            'hidden': bool(log.hidden),
        })
    return rows


def export_meeting_logs(club_id: int, logs, new_name: str) -> str:
    """Persist a meeting's SessionLog rows as a new club template.

    The route supplies the logs (sorted by Meeting_Seq) so the service stays
    free of DB session dependencies. Returns the new filename.
    """
    target_name = sanitize_filename(new_name)
    target = _safe_join(club_id, target_name)
    if os.path.exists(target):
        raise TemplateNameInvalid(f"Template '{target_name}' already exists")

    rows = logs_to_template_rows(logs)
    save_template_to_path(target, rows)
    return target_name


def save_template_to_path(path: str, rows: List[Dict]) -> None:
    """Atomic write to an explicit path (used by export from meeting)."""
    tmp = path + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        for row in rows or []:
            writer.writerow([
                (row.get('type') or '').strip(),
                (row.get('title') or '').strip(),
                (row.get('role') or '').strip(),
                (row.get('owner') or '').strip(),
                row.get('duration_min') if row.get('duration_min') not in (None, '') else '',
                row.get('duration_max') if row.get('duration_max') not in (None, '') else '',
                'true' if row.get('hidden') else '',
            ])
    os.replace(tmp, path)


def template_exists(club_id: int, filename: str) -> bool:
    try:
        return os.path.exists(_safe_join(club_id, filename))
    except (TemplateNameInvalid, TemplatePathEscape):
        return False


def resolve_filename_for_meeting_type(club_id: int, meeting_type: str) -> Optional[str]:
    """Return the template filename that maps to a given display name (or None)."""
    return get_template_filename_map(club_id).get(meeting_type)
