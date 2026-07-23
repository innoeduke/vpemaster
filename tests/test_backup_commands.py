import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta
import pytest
import zipfile
from app.services.backup_service import BackupService

def test_get_backups_sorted_and_rotate(app):
    with app.app_context():
        with tempfile.TemporaryDirectory() as tmpdir:
            # We will generate a mock list of backup files to test rotation
            base_time = datetime(2026, 5, 25, 10, 0, 0)
            
            for i in range(6):
                # Full backup
                ft = base_time + timedelta(hours=i)
                f_name = f"backup_system_full_{ft.strftime('%Y%m%d_%H%M%S')}.zip"
                with open(os.path.join(tmpdir, f_name), 'w') as f:
                    f.write("full")
                # Incremental backup associated with this full backup
                it1 = ft + timedelta(minutes=10)
                it1_name = f"backup_system_inc_{it1.strftime('%Y%m%d_%H%M%S')}.zip"
                with open(os.path.join(tmpdir, it1_name), 'w') as f:
                    f.write("inc")
            
            # Now let's list backups sorted
            backups = BackupService.get_backups_sorted(tmpdir, 'system', 'zip')
            assert len(backups) == 12  # 6 full + 6 inc
            
            # Rotate backups (should keep 5 most recent full backups, meaning the first full backup is deleted,
            # along with its associated incremental backup)
            BackupService._rotate_backups(tmpdir, 'system', 'zip')
            
            remaining = BackupService.get_backups_sorted(tmpdir, 'system', 'zip')
            assert len(remaining) == 10  # 5 full + 5 inc
            
            # Verify the oldest full backup and its incremental were deleted
            oldest_full_time = base_time
            oldest_inc_time = base_time + timedelta(minutes=10)
            
            for b in remaining:
                assert b['timestamp'] != oldest_full_time
                assert b['timestamp'] != oldest_inc_time

def test_file_backups_full_and_incremental(app):
    with app.app_context():
        test_dir_rel = 'static/test_temp_resources'
        test_dir_abs = os.path.join(app.root_path, test_dir_rel)
        os.makedirs(test_dir_abs, exist_ok=True)
        
        try:
            # Create a file in test_dir
            file1 = os.path.join(test_dir_abs, 'file1.txt')
            with open(file1, 'w') as f:
                f.write("file1 content")
                
            # Create a backup directory
            with tempfile.TemporaryDirectory() as backup_dir:
                # 1. Perform full backup
                success, backup1_path = BackupService.create_file_backup(backup_dir, [test_dir_rel], 'test_res', strategy='full')
                assert success
                assert os.path.exists(backup1_path)
                assert 'full' in backup1_path
                
                # Check contents of full backup zip
                with zipfile.ZipFile(backup1_path, 'r') as zf:
                    namelist = zf.namelist()
                    assert f"{test_dir_rel}/file1.txt" in namelist
                    
                # Sleep a short duration to ensure timestamps are distinct
                time.sleep(1.1)
                
                # 2. Try incremental backup without any changes
                success, result = BackupService.create_file_backup(backup_dir, [test_dir_rel], 'test_res', strategy='increment')
                assert success
                assert "no changes detected" in result.lower()
                
                # 3. Add a new file and modify existing file
                file2 = os.path.join(test_dir_abs, 'file2.txt')
                with open(file2, 'w') as f:
                    f.write("file2 content")
                
                # Touch file1.txt to update its mtime
                os.utime(file1, None)
                
                # 4. Perform incremental backup
                success, backup2_path = BackupService.create_file_backup(backup_dir, [test_dir_rel], 'test_res', strategy='increment')
                assert success
                assert os.path.exists(backup2_path)
                assert 'inc' in backup2_path
                
                # Check contents of incremental backup zip: it should contain both modified file1.txt and new file2.txt
                with zipfile.ZipFile(backup2_path, 'r') as zf:
                    namelist = zf.namelist()
                    assert f"{test_dir_rel}/file1.txt" in namelist
                    assert f"{test_dir_rel}/file2.txt" in namelist
                
                # 5. Verify restore of incremental chain
                # First delete the files in source directory
                os.remove(file1)
                os.remove(file2)
                assert not os.path.exists(file1)
                assert not os.path.exists(file2)
                
                # Restore the latest backup (which is incremental)
                success, message = BackupService.restore_file_backup(backup_dir, latest=True, resource_name='test_res')
                assert success
                assert os.path.exists(file1)
                assert os.path.exists(file2)
                
                with open(file1, 'r') as f:
                    assert f.read() == "file1 content"
                with open(file2, 'r') as f:
                    assert f.read() == "file2 content"
                    
        finally:
            if os.path.exists(test_dir_abs):
                shutil.rmtree(test_dir_abs)

def test_file_backups_differential(app):
    with app.app_context():
        test_dir_rel = 'static/test_temp_diff'
        test_dir_abs = os.path.join(app.root_path, test_dir_rel)
        os.makedirs(test_dir_abs, exist_ok=True)

        try:
            file1 = os.path.join(test_dir_abs, 'file1.txt')
            with open(file1, 'w') as f:
                f.write("file1 content")

            with tempfile.TemporaryDirectory() as backup_dir:
                # 1. Full backup at t0 (captures file1 only)
                success, full_path = BackupService.create_file_backup(
                    backup_dir, [test_dir_rel], 'test_diff', strategy='full')
                assert success
                assert 'full' in full_path

                time.sleep(1.1)

                # 2. Add file2, modify file1
                file2 = os.path.join(test_dir_abs, 'file2.txt')
                with open(file2, 'w') as f:
                    f.write("file2 content")
                os.utime(file1, None)

                # 3. Take an incremental backup (since last backup = full)
                success, inc_path = BackupService.create_file_backup(
                    backup_dir, [test_dir_rel], 'test_diff', strategy='increment')
                assert success
                assert 'inc' in inc_path
                with zipfile.ZipFile(inc_path, 'r') as zf:
                    names = zf.namelist()
                    assert f"{test_dir_rel}/file1.txt" in names
                    assert f"{test_dir_rel}/file2.txt" in names

                time.sleep(1.1)

                # 4. Add file3, modify file1 again
                file3 = os.path.join(test_dir_abs, 'file3.txt')
                with open(file3, 'w') as f:
                    f.write("file3 content")
                with open(file1, 'w') as f:
                    f.write("file1 modified again")
                os.utime(file1, None)

                # 5. Take a differential backup — should be a delta against the
                #    *last full*, NOT the last incremental. So it must contain
                #    file1 (modified since full), file2 (added since full),
                #    and file3 (added since full) — even though file2 was
                #    already captured in the incremental.
                success, diff_path = BackupService.create_file_backup(
                    backup_dir, [test_dir_rel], 'test_diff', strategy='differential')
                assert success
                assert 'diff' in diff_path
                with zipfile.ZipFile(diff_path, 'r') as zf:
                    names = set(zf.namelist())
                    assert f"{test_dir_rel}/file1.txt" in names
                    assert f"{test_dir_rel}/file2.txt" in names
                    assert f"{test_dir_rel}/file3.txt" in names

                # 6. Restore the differential — only full + diff are applied.
                os.remove(file1)
                os.remove(file2)
                os.remove(file3)
                assert not os.path.exists(file1)

                success, message = BackupService.restore_file_backup(
                    backup_dir, latest=True, resource_name='test_diff')
                assert success, message
                assert os.path.exists(file1)
                assert os.path.exists(file2)
                assert os.path.exists(file3)
                with open(file1, 'r') as f:
                    assert f.read() == "file1 modified again"
                with open(file2, 'r') as f:
                    assert f.read() == "file2 content"
                with open(file3, 'r') as f:
                    assert f.read() == "file3 content"

                # 7. Differential with no full baseline falls back to a full.
                with tempfile.TemporaryDirectory() as empty_dir:
                    success, result = BackupService.create_file_backup(
                        empty_dir, [test_dir_rel], 'test_diff', strategy='differential')
                    assert success
                    assert 'full' in result

            # 8. Differential taken immediately after a full, before any
            #    further changes, is a no-op ("No changes detected").
            with tempfile.TemporaryDirectory() as fresh_dir:
                success, _ = BackupService.create_file_backup(
                    fresh_dir, [test_dir_rel], 'test_diff2', strategy='full')
                assert success
                success, result = BackupService.create_file_backup(
                    fresh_dir, [test_dir_rel], 'test_diff2', strategy='differential')
                assert success
                assert "no changes detected" in result.lower()
        finally:
            if os.path.exists(test_dir_abs):
                shutil.rmtree(test_dir_abs)


def test_file_backups_auto_default(app):
    with app.app_context():
        test_dir_rel = 'static/test_temp_auto'
        test_dir_abs = os.path.join(app.root_path, test_dir_rel)
        os.makedirs(test_dir_abs, exist_ok=True)

        try:
            file1 = os.path.join(test_dir_abs, 'file1.txt')
            with open(file1, 'w') as f:
                f.write("file1 content")

            with tempfile.TemporaryDirectory() as backup_dir:
                # 1. With no prior backup, 'auto' resolves to a full backup.
                success, first_path = BackupService.create_file_backup(
                    backup_dir, [test_dir_rel], 'test_auto', strategy='auto')
                assert success
                assert 'full' in first_path

                time.sleep(1.1)

                # 2. Touch file1 so there is a change to capture.
                os.utime(file1, None)

                # 3. With a prior full, 'auto' now resolves to an incremental.
                success, second_path = BackupService.create_file_backup(
                    backup_dir, [test_dir_rel], 'test_auto', strategy='auto')
                assert success
                assert 'inc' in second_path

                # 4. Default strategy parameter is 'auto'.
                success, third_path = BackupService.create_file_backup(
                    backup_dir, [test_dir_rel], 'test_auto')
                # No changes since the incremental → skipped, not a new file.
                assert success
                assert "no changes detected" in third_path.lower()
        finally:
            if os.path.exists(test_dir_abs):
                shutil.rmtree(test_dir_abs)


def test_differential_rotation(app):
    with app.app_context():
        with tempfile.TemporaryDirectory() as tmpdir:
            base_time = datetime(2026, 5, 25, 10, 0, 0)

            for i in range(6):
                ft = base_time + timedelta(hours=i)
                full_name = f"backup_system_full_{ft.strftime('%Y%m%d_%H%M%S')}.zip"
                with open(os.path.join(tmpdir, full_name), 'w') as f:
                    f.write("full")
                dt = ft + timedelta(minutes=20)
                diff_name = f"backup_system_diff_{dt.strftime('%Y%m%d_%H%M%S')}.zip"
                with open(os.path.join(tmpdir, diff_name), 'w') as f:
                    f.write("diff")

            backups = BackupService.get_backups_sorted(tmpdir, 'system', 'zip')
            assert len(backups) == 12

            BackupService._rotate_backups(tmpdir, 'system', 'zip')

            remaining = BackupService.get_backups_sorted(tmpdir, 'system', 'zip')
            assert len(remaining) == 10
            oldest_full = base_time
            oldest_diff = base_time + timedelta(minutes=20)
            for b in remaining:
                assert b['timestamp'] != oldest_full
                assert b['timestamp'] != oldest_diff


def test_cli_commands(app):
    from unittest.mock import patch
    from app.commands.backup import resources
    
    runner = app.test_cli_runner()
    
    # Help commands verification
    result = runner.invoke(resources, ['--help'])
    assert result.exit_code == 0
    assert 'backup' in result.output
    assert 'restore' in result.output
    
    # Test backup command help
    result = runner.invoke(resources, ['backup', '--help'])
    assert result.exit_code == 0
    assert '--type' in result.output
    assert '-t' in result.output

    # Test restore command help
    result = runner.invoke(resources, ['restore', '--help'])
    assert result.exit_code == 0
    assert '--type' in result.output
    assert '-t' in result.output

    # Test invalid type option
    result = runner.invoke(resources, ['backup', '--type', 'invalid'])
    assert result.exit_code != 0

    # Test mutually exclusive strategy flags
    result = runner.invoke(resources, ['backup', '-t', 'system', '--increment', '--differential'])
    assert result.exit_code != 0
    result = runner.invoke(resources, ['backup', '-t', 'system', '--full', '--differential'])
    assert result.exit_code != 0

    with patch('app.services.backup_service.BackupService.create_database_backup', return_value=(True, '/path/db.sql')), \
         patch('app.services.backup_service.BackupService.create_file_backup', return_value=(True, '/path/res.zip')), \
         patch('app.services.backup_service.BackupService.restore_database', return_value=(True, 'DB Restored')), \
         patch('app.services.backup_service.BackupService.restore_file_backup', return_value=(True, 'Files Restored')), \
         patch('app.services.backup_service.BackupService.get_latest_backup', return_value='/path/latest_db.sql'):

        # Test backup with --type db
        result = runner.invoke(resources, ['backup', '--type', 'db'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'Creating database backup' in result.output

        # Test backup with -t system
        result = runner.invoke(resources, ['backup', '-t', 'system'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'Creating system resources backup' in result.output
        assert '(auto)' in result.output

        # Test backup with -t system --differential
        result = runner.invoke(resources, ['backup', '-t', 'system', '--differential'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'differential' in result.output

        # Test backup with -t system --diff (alias)
        result = runner.invoke(resources, ['backup', '-t', 'system', '--diff'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'differential' in result.output

        # Test backup with -t club
        result = runner.invoke(resources, ['backup', '-t', 'club'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'Creating club resources backup' in result.output

        # Test backup with -t db at group level (e.g., flask resources -t db backup)
        result = runner.invoke(resources, ['-t', 'db', 'backup'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'Creating database backup' in result.output


        # Test backup with default type (all)
        result = runner.invoke(resources, ['backup'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'Creating database backup' in result.output
        assert 'Creating system resources backup' in result.output
        assert 'Creating club resources backup' in result.output
        assert 'All backups completed' in result.output

        # Test restore with --type db --latest
        result = runner.invoke(resources, ['restore', '--type', 'db', '--latest'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'Restoring database' in result.output

        # Test restore with -t system --latest
        result = runner.invoke(resources, ['restore', '-t', 'system', '--latest'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'Restoring system resources' in result.output

        # Test restore with default type (all) --latest
        result = runner.invoke(resources, ['restore', '--latest'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'Restoring database' in result.output
        assert 'Restoring system resources' in result.output
        assert 'Restoring club resources' in result.output

        # Test smart-default restore (no --file / --latest / --*-file):
        # should behave like --latest for every selected resource.
        result = runner.invoke(resources, ['restore'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'Restoring database' in result.output
        assert 'Restoring system resources' in result.output
        assert 'Restoring club resources' in result.output

        result = runner.invoke(resources, ['-t', 'db', 'restore'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'Restoring database' in result.output

        result = runner.invoke(resources, ['-t', 'system', 'restore'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'Restoring system resources' in result.output

        result = runner.invoke(resources, ['-t', 'club', 'restore'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert 'Restoring club resources' in result.output



