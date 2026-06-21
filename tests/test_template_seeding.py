"""Tests for lazy default-template seeding in ``meeting_template_service``."""
import os
import tempfile
import uuid

import pytest

from app import db
from app.models.club import Club
from app.services import meeting_template_service as tpl_service


def _make_club():
    """Create a fresh club with no templates dir on disk; return its id."""
    club = Club(club_no=f"SEED{uuid.uuid4().hex[:6]}", club_name="Seed Test Club")
    db.session.add(club)
    db.session.commit()
    db.session.refresh(club)
    return club.id


def _cleanup_club_templates(club_dir):
    """Remove only the files this test created in the given templates dir.

    Never ``rmtree`` — ``club_resources/<id>/`` may contain other real
    resources for these IDs in dev.
    """
    if not os.path.isdir(club_dir):
        return
    for name in os.listdir(club_dir):
        path = os.path.join(club_dir, name)
        if os.path.isfile(path):
            os.remove(path)


def test_empty_club_gets_seeded(app):
    """A club with no CSVs gets both real seed CSVs copied in."""
    with app.app_context():
        club_id = _make_club()
        club_dir = tpl_service._club_dir(club_id)
        # Pre-clean: prior tests (or other suites using the same id) may
        # have left files in this dir; we want to start from empty.
        _cleanup_club_templates(club_dir)
        try:
            # Sanity: club 0's templates dir is the real seed source.
            seed_dir = tpl_service._seed_dir()
            assert os.path.isdir(seed_dir)
            seed_names = {
                n for n in os.listdir(seed_dir)
                if n.endswith('.csv') and not n.startswith('.')
            }
            assert seed_names, "test relies on at least one real seed CSV"

            seeded = tpl_service.ensure_default_templates(club_id)
            assert seeded == len(seed_names)

            listed = tpl_service.list_templates(club_id)
            listed_names = {t.filename for t in listed}
            assert listed_names == seed_names

            # Files actually exist on disk under the club's templates dir.
            for name in seed_names:
                assert os.path.isfile(os.path.join(club_dir, name))
        finally:
            _cleanup_club_templates(club_dir)


def test_existing_templates_are_preserved(app):
    """A non-empty club's templates are not overwritten."""
    with app.app_context():
        club_id = _make_club()
        club_dir = tpl_service._club_dir(club_id)
        _cleanup_club_templates(club_dir)
        try:
            # 1. A user-created template that has no analog in the seed dir.
            custom_name = f"custom_{uuid.uuid4().hex}.csv"
            custom_path = os.path.join(club_dir, custom_name)
            custom_body = "user-written,do-not-touch\n"
            with open(custom_path, 'w', encoding='utf-8') as f:
                f.write(custom_body)

            # 2. A pre-existing file that collides with a real seed file,
            #    with a sentinel byte to detect any overwrite.
            collision_name = "keynote_speech.csv"
            collision_path = os.path.join(club_dir, collision_name)
            sentinel = b"SENTINEL-PRESERVE-ME\n"
            with open(collision_path, 'wb') as f:
                f.write(sentinel)

            seeded = tpl_service.ensure_default_templates(club_id)
            # The dir is already non-empty (custom + collision), so the
            # seeder must leave it alone.
            assert seeded == 0

            assert os.path.isfile(custom_path)
            with open(custom_path, 'rb') as f:
                assert f.read() == custom_body.encode('utf-8')

            with open(collision_path, 'rb') as f:
                assert f.read() == sentinel
        finally:
            _cleanup_club_templates(club_dir)


def test_idempotent(app):
    """Calling ``ensure_default_templates`` twice is a no-op the second time."""
    with app.app_context():
        club_id = _make_club()
        club_dir = tpl_service._club_dir(club_id)
        _cleanup_club_templates(club_dir)
        try:
            first = tpl_service.ensure_default_templates(club_id)
            assert first > 0

            second = tpl_service.ensure_default_templates(club_id)
            assert second == 0

            # File count is unchanged.
            listed_count = len(tpl_service.list_templates(club_id))
            on_disk_count = sum(
                1 for n in os.listdir(club_dir)
                if n.endswith('.csv') and not n.startswith('.')
            )
            assert on_disk_count == listed_count == first
        finally:
            _cleanup_club_templates(club_dir)


def test_missing_seed_dir_does_not_raise(app, monkeypatch):
    """When ``club_resources/0/templates/`` doesn't exist, return 0 quietly."""
    with app.app_context():
        club_id = _make_club()
        # Capture the real club dir BEFORE monkeypatching _static_root, so
        # cleanup runs against the real path (which is what we want — the
        # test never wrote any files there).
        real_club_dir = tpl_service._club_dir(club_id)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                monkeypatch.setattr(tpl_service, '_static_root', lambda: tmp)

                # Sanity: with the patched root, the seed dir really is absent.
                assert not os.path.exists(os.path.join(tmp, '0', 'templates'))

                seeded = tpl_service.ensure_default_templates(club_id)
                assert seeded == 0

                listed = tpl_service.list_templates(club_id)
                assert listed == []
        finally:
            _cleanup_club_templates(real_club_dir)