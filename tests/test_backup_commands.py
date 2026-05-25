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

def test_cli_commands(app):
    from click.testing import CliRunner
    from app.commands.backup import resources
    
    runner = CliRunner()
    
    # Help commands verification
    result = runner.invoke(resources, ['--help'])
    assert result.exit_code == 0
    assert 'db' in result.output
    assert 'system' in result.output
    assert 'club' in result.output
    assert 'all' in result.output
    
    # Test db group help
    result = runner.invoke(resources, ['db', '--help'])
    assert result.exit_code == 0
    assert 'backup' in result.output
    assert 'restore' in result.output

    # Test system group help
    result = runner.invoke(resources, ['system', '--help'])
    assert result.exit_code == 0
    assert 'backup' in result.output
    assert 'restore' in result.output
