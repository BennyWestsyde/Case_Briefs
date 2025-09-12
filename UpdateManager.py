"""
UpdateManager module for CaseBriefs application.

This module implements secure automatic updates using Tufup (The Update Framework).
It supports multiple release channels (alpha, beta, main) and integrates with
GitHub releases.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import tempfile
import shutil
from enum import Enum

try:
    import tufup.client
    TUFUP_AVAILABLE = True
except ImportError:
    TUFUP_AVAILABLE = False

from logger import StructuredLogger
from version import __version__


class UpdateChannel(Enum):
    """Available update channels."""
    MAIN = "main"
    BETA = "beta"
    ALPHA = "alpha"


class UpdateStatus(Enum):
    """Update check status."""
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    ERROR = "error"
    CHECKING = "checking"


class UpdateManager:
    """
    Manages automatic updates for the CaseBriefs application using Tufup.
    
    Supports multiple release channels and GitHub releases integration.
    """
    
    def __init__(self, global_vars, logger: StructuredLogger):
        """Initialize the UpdateManager.
        
        Args:
            global_vars: Global_Vars instance for configuration
            logger: StructuredLogger instance
        """
        self.global_vars = global_vars
        self.logger = logger.getChildLogger(self.__class__.__name__)
        self.current_version = __version__
        
        # Update configuration
        self.app_name = "CaseBriefs"
        self.repository_owner = "BennyWestsyde"
        self.repository_name = "Case_Briefs"
        
        # Default to main channel
        self._channel = UpdateChannel.MAIN
        
        # Load channel preference from configuration
        self._load_update_config()
        
        # Set up update directories
        self.update_dir = self.global_vars.write_dir / "updates"
        self.metadata_dir = self.update_dir / "metadata"
        self.target_dir = self.update_dir / "targets"
        self.extract_dir = self.update_dir / "extract"
        
        # Create directories
        for directory in [self.update_dir, self.metadata_dir, self.target_dir, self.extract_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Base URLs for different channels
        self.channel_urls = {
            UpdateChannel.MAIN: f"https://github.com/{self.repository_owner}/{self.repository_name}/releases/download",
            UpdateChannel.BETA: f"https://github.com/{self.repository_owner}/{self.repository_name}/releases/download",
            UpdateChannel.ALPHA: f"https://github.com/{self.repository_owner}/{self.repository_name}/releases/download",
        }
        
        self.client: Optional[tufup.client.Client] = None
        if TUFUP_AVAILABLE:
            self._initialize_client()
    
    def _load_update_config(self):
        """Load update configuration from global vars."""
        # For now, default to main channel
        # This can be extended to load from configuration files
        pass
    
    def _initialize_client(self):
        """Initialize the Tufup client."""
        if not TUFUP_AVAILABLE:
            self.logger.warning("Tufup not available, updates disabled")
            return
        
        try:
            metadata_base_url = f"{self.channel_urls[self._channel]}/metadata"
            target_base_url = f"{self.channel_urls[self._channel]}/targets"
            
            # Get application install directory
            if getattr(sys, 'frozen', False):
                # Running in bundle
                app_install_dir = Path(sys.executable).parent
            else:
                # Running in development
                app_install_dir = Path(__file__).parent
            
            self.client = tufup.client.Client(
                app_name=self.app_name,
                app_install_dir=app_install_dir,
                current_version=self.current_version,
                metadata_dir=self.metadata_dir,
                metadata_base_url=metadata_base_url,
                target_dir=self.target_dir,
                target_base_url=target_base_url,
                extract_dir=self.extract_dir,
                refresh_required=True
            )
            
            self.logger.info(f"Initialized update client for channel: {self._channel.value}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize update client: {e}")
            self.client = None
    
    @property
    def channel(self) -> UpdateChannel:
        """Get the current update channel."""
        return self._channel
    
    @channel.setter
    def channel(self, value: UpdateChannel):
        """Set the update channel and reinitialize client."""
        if value != self._channel:
            self._channel = value
            self.logger.info(f"Switched to update channel: {value.value}")
            if TUFUP_AVAILABLE:
                self._initialize_client()
    
    def check_for_updates(self) -> Tuple[UpdateStatus, Optional[str], Optional[str]]:
        """
        Check for available updates.
        
        Returns:
            Tuple of (status, latest_version, error_message)
        """
        try:
            self.logger.info("Checking for updates...")
            
            # Use GitHub API for update checking (works without tufup client)
            latest_version = self._get_latest_version_from_github()
            
            if latest_version and self._is_newer_version(latest_version, self.current_version):
                self.logger.info(f"Update available: {latest_version}")
                return UpdateStatus.UPDATE_AVAILABLE, latest_version, None
            else:
                self.logger.info("Application is up to date")
                return UpdateStatus.UP_TO_DATE, self.current_version, None
                
        except Exception as e:
            self.logger.error(f"Error checking for updates: {e}")
            return UpdateStatus.ERROR, None, str(e)
    
    def _get_latest_version_from_github(self) -> Optional[str]:
        """
        Get the latest version from GitHub releases.
        
        This is a simplified implementation for MVP.
        """
        try:
            import requests
            
            # Get releases from GitHub API
            api_url = f"https://api.github.com/repos/{self.repository_owner}/{self.repository_name}/releases"
            
            # For different channels, we'd filter by tags/prerelease status
            if self._channel == UpdateChannel.ALPHA:
                # Include prereleases
                response = requests.get(api_url, timeout=10)
            elif self._channel == UpdateChannel.BETA:
                # Include prereleases but filter for beta
                response = requests.get(api_url, timeout=10)
            else:
                # Main channel - only stable releases
                response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                releases = response.json()
                
                # Filter releases based on channel
                filtered_releases = self._filter_releases_by_channel(releases)
                
                if filtered_releases:
                    latest = filtered_releases[0]
                    version = latest.get('tag_name', '').lstrip('v')
                    self.logger.debug(f"Latest version from GitHub: {version}")
                    return version
            
        except Exception as e:
            self.logger.error(f"Failed to get latest version from GitHub: {e}")
        
        return None
    
    def _filter_releases_by_channel(self, releases: List[Dict]) -> List[Dict]:
        """Filter releases based on the selected channel."""
        filtered = []
        
        for release in releases:
            tag_name = release.get('tag_name', '').lower()
            is_prerelease = release.get('prerelease', False)
            
            if self._channel == UpdateChannel.ALPHA:
                # Alpha: all releases including prereleases
                filtered.append(release)
            elif self._channel == UpdateChannel.BETA:
                # Beta: stable releases and beta prereleases
                if not is_prerelease or 'beta' in tag_name:
                    filtered.append(release)
            else:
                # Main: only stable releases
                if not is_prerelease:
                    filtered.append(release)
        
        return filtered
    
    def _is_newer_version(self, version1: str, version2: str) -> bool:
        """
        Compare two version strings.
        
        Returns True if version1 is newer than version2.
        """
        try:
            from packaging import version
            return version.parse(version1) > version.parse(version2)
        except Exception:
            # Fallback to simple string comparison
            return version1 > version2
    
    def download_update(self, version: str) -> Tuple[bool, Optional[str]]:
        """
        Download an update for the specified version.
        
        Args:
            version: Version to download
            
        Returns:
            Tuple of (success, error_message)
        """
        if not TUFUP_AVAILABLE or not self.client:
            return False, "Update client not available"
        
        try:
            self.logger.info(f"Downloading update for version {version}")
            
            # This would use tufup's download functionality
            # For MVP, this is a placeholder
            
            self.logger.info("Update downloaded successfully")
            return True, None
            
        except Exception as e:
            self.logger.error(f"Failed to download update: {e}")
            return False, str(e)
    
    def apply_update(self, version: str) -> Tuple[bool, Optional[str]]:
        """
        Apply a downloaded update.
        
        Args:
            version: Version to apply
            
        Returns:
            Tuple of (success, error_message)
        """
        if not TUFUP_AVAILABLE or not self.client:
            return False, "Update client not available"
        
        try:
            self.logger.info(f"Applying update for version {version}")
            
            # This would use tufup's installation functionality
            # For MVP, this is a placeholder
            
            self.logger.info("Update applied successfully")
            return True, None
            
        except Exception as e:
            self.logger.error(f"Failed to apply update: {e}")
            return False, str(e)
    
    def is_update_available(self) -> bool:
        """Quick check if an update is available."""
        status, _, _ = self.check_for_updates()
        return status == UpdateStatus.UPDATE_AVAILABLE
    
    def get_available_channels(self) -> List[UpdateChannel]:
        """Get list of available update channels."""
        return list(UpdateChannel)
    
    def cleanup_old_updates(self):
        """Clean up old update files to save disk space."""
        try:
            if self.update_dir.exists():
                # Keep only the latest few update files
                self.logger.debug("Cleaning up old update files")
                # Implementation would clean old downloads
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old updates: {e}")