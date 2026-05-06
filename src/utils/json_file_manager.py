"""
Safe JSON file operations with atomic writes, validation, and backup.
Prevents data corruption and data loss issues.
"""

import json
import os
import logging
import tempfile
from typing import Any, Dict, Optional, Callable
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class JSONFileManager:
    """
    Manages JSON file operations safely with:
    - Atomic writes (write to temp file, then rename)
    - Backup creation before writes
    - Validation of JSON structure
    - Automatic recovery from corruption
    """
    
    def __init__(self, filepath: str, create_backups: bool = True):
        """
        Initialize JSON file manager.
        
        Args:
            filepath: Path to JSON file
            create_backups: Whether to create .bak files before writes
        """
        self.filepath = Path(filepath)
        self.create_backups = create_backups
        self.backup_path = Path(str(filepath) + ".bak")
        self.tmp_path = Path(str(filepath) + ".tmp")
    
    def ensure_directory(self) -> bool:
        """Create directory if it doesn't exist."""
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create directory {self.filepath.parent}: {e}")
            return False
    
    def read(self, default: Any = None, validate_fn: Optional[Callable] = None) -> Any:
        """
        Safely read JSON file with validation.
        
        Args:
            default: Default value if file not found or invalid
            validate_fn: Optional validation function(data) -> bool
        
        Returns:
            Parsed JSON data or default
        """
        try:
            if not self.filepath.exists():
                logger.warning(f"JSON file not found: {self.filepath}")
                return default
            
            if self.filepath.stat().st_size == 0:
                logger.warning(f"JSON file is empty: {self.filepath}")
                return default
            
            with open(self.filepath, 'r') as f:
                data = json.load(f)
            
            # Validate if function provided
            if validate_fn and not validate_fn(data):
                logger.error(f"JSON validation failed for {self.filepath}")
                return default
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(
                f"JSON corruption in {self.filepath}: {e.msg} at position {e.pos}"
            )
            # Try to recover from backup
            return self._recover_from_backup(default)
        except IOError as e:
            logger.error(f"Cannot read {self.filepath}: {e}")
            return default
        except Exception as e:
            logger.error(f"Unexpected error reading {self.filepath}: {e}")
            return default
    
    def write(self, data: Any, validate_fn: Optional[Callable] = None) -> bool:
        """
        Safely write JSON file with atomic operations.
        
        Args:
            data: Data to write
            validate_fn: Optional validation function(data) -> bool
        
        Returns:
            True if successful, False otherwise
        """
        # Validate data first
        if validate_fn and not validate_fn(data):
            logger.error(f"Data validation failed before write: {data}")
            return False
        
        try:
            # Ensure directory exists
            if not self.ensure_directory():
                return False
            
            # Write to temporary file
            self.tmp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.tmp_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            # Verify temp file is valid JSON
            try:
                with open(self.tmp_path, 'r') as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Written JSON is invalid: {e}")
                self.tmp_path.unlink(missing_ok=True)
                return False
            
            # Create backup of existing file
            if self.create_backups and self.filepath.exists():
                try:
                    if self.backup_path.exists():
                        self.backup_path.unlink()
                    self.filepath.rename(self.backup_path)
                    logger.debug(f"Created backup: {self.backup_path}")
                except Exception as e:
                    logger.warning(f"Failed to create backup: {e}")
                    # Continue anyway - important to write new file
            
            # Atomic rename
            try:
                self.tmp_path.replace(self.filepath)
                logger.debug(f"Successfully wrote {self.filepath}")
                return True
            except Exception as e:
                logger.error(f"Failed to replace file: {e}")
                # Clean up temp file
                self.tmp_path.unlink(missing_ok=True)
                return False
                
        except Exception as e:
            logger.error(f"Failed to write {self.filepath}: {e}")
            # Clean up temp file
            self.tmp_path.unlink(missing_ok=True)
            return False
    
    def _recover_from_backup(self, default: Any = None) -> Any:
        """Try to recover data from backup file."""
        if not self.backup_path.exists():
            logger.warning(f"No backup available for recovery: {self.backup_path}")
            return default
        
        try:
            logger.info(f"Attempting recovery from backup: {self.backup_path}")
            with open(self.backup_path, 'r') as f:
                data = json.load(f)
            logger.info("Successfully recovered from backup")
            return data
        except Exception as e:
            logger.error(f"Failed to recover from backup: {e}")
            return default
    
    def append(self, item: Any, array_key: str = None) -> bool:
        """
        Append item to JSON array file (or nested array).
        
        Args:
            item: Item to append
            array_key: Key of array to append to (for nested arrays)
        
        Returns:
            True if successful
        """
        try:
            data = self.read(default=[] if not array_key else {array_key: []})
            
            if array_key:
                if not isinstance(data, dict):
                    data = {array_key: []}
                if array_key not in data:
                    data[array_key] = []
                if not isinstance(data[array_key], list):
                    data[array_key] = []
                data[array_key].append(item)
            else:
                if not isinstance(data, list):
                    data = []
                data.append(item)
            
            return self.write(data)
        except Exception as e:
            logger.error(f"Failed to append to {self.filepath}: {e}")
            return False
    
    def delete(self) -> bool:
        """Delete the JSON file and backup."""
        try:
            if self.filepath.exists():
                self.filepath.unlink()
            if self.backup_path.exists():
                self.backup_path.unlink()
            if self.tmp_path.exists():
                self.tmp_path.unlink()
            logger.info(f"Deleted {self.filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {self.filepath}: {e}")
            return False
    
    def exists(self) -> bool:
        """Check if file exists."""
        return self.filepath.exists()
    
    def get_file_size(self) -> int:
        """Get file size in bytes."""
        try:
            return self.filepath.stat().st_size if self.filepath.exists() else 0
        except Exception as e:
            logger.error(f"Failed to get file size: {e}")
            return 0
    
    def get_last_modified(self) -> Optional[datetime]:
        """Get last modification time."""
        try:
            if self.filepath.exists():
                return datetime.fromtimestamp(self.filepath.stat().st_mtime)
        except Exception as e:
            logger.error(f"Failed to get modification time: {e}")
        return None


def validate_json_structure(
    data: Any,
    required_type: type = dict,
    required_keys: set = None,
    key_types: Dict[str, type] = None
) -> bool:
    """
    Validate JSON structure.
    
    Args:
        data: Data to validate
        required_type: Expected type of data
        required_keys: Required keys (for dict)
        key_types: Expected types for specific keys
    
    Returns:
        True if valid
    """
    # Check type
    if not isinstance(data, required_type):
        logger.error(f"Expected {required_type.__name__}, got {type(data).__name__}")
        return False
    
    # Check required keys (for dict)
    if required_type == dict and required_keys:
        missing = required_keys - set(data.keys())
        if missing:
            logger.error(f"Missing required keys: {missing}")
            return False
    
    # Check key types
    if key_types:
        for key, expected_type in key_types.items():
            if key in data:
                if not isinstance(data[key], expected_type):
                    logger.error(
                        f"Key '{key}': expected {expected_type.__name__}, "
                        f"got {type(data[key]).__name__}"
                    )
                    return False
    
    return True


# Helper functions for common operations

def safe_load_json(filepath: str, default: Any = None) -> Any:
    """Load JSON file safely."""
    manager = JSONFileManager(filepath)
    return manager.read(default)


def safe_save_json(filepath: str, data: Any) -> bool:
    """Save JSON file safely."""
    manager = JSONFileManager(filepath)
    return manager.write(data)


def safe_append_to_json(filepath: str, item: Any, array_key: str = None) -> bool:
    """Append item to JSON array file safely."""
    manager = JSONFileManager(filepath)
    return manager.append(item, array_key)
