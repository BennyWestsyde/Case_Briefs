#!/usr/bin/env python3
"""
Tufup repository setup and build script for CaseBriefs.

This script helps set up the tufup repository structure and generates
the necessary metadata for secure updates.
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
import tempfile
import json
import shutil
from typing import Dict, Any

try:
    import tufup.repo
    import tufup.utils
    TUFUP_AVAILABLE = True
except ImportError:
    TUFUP_AVAILABLE = False


def setup_tufup_repo(repo_dir: Path, app_name: str, app_version: str):
    """
    Set up a tufup repository structure.
    
    Args:
        repo_dir: Directory to create the repository in
        app_name: Name of the application
        app_version: Version of the application (for reference)
    """
    if not TUFUP_AVAILABLE:
        print("ERROR: tufup is not available. Please install it first.")
        sys.exit(1)
    
    # Create repository directory
    repo_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize tufup repository
    repo = tufup.repo.Repository(
        app_name=app_name,
        repo_dir=repo_dir,
        keys_dir=repo_dir / "keys"
    )
    
    # Generate keys if they don't exist
    keys_dir = repo_dir / "keys"
    if not keys_dir.exists():
        print("Generating tufup signing keys...")
        # Note: In a real deployment, keys should be managed securely
        repo.create_key("root")
        repo.create_key("timestamp")
        repo.create_key("snapshot")
        repo.create_key("targets")
        print(f"Keys generated in {keys_dir}")
    
    return repo


def build_app_archive(dist_dir: Path, app_name: str, platform: str) -> Path:
    """
    Create an archive of the built application.
    
    Args:
        dist_dir: Directory containing the built application
        app_name: Name of the application
        platform: Platform identifier (e.g., macos-x86_64, windows-x86_64)
        
    Returns:
        Path to the created archive
    """
    # Determine the correct source directory and archive format
    if "macos" in platform:
        source_path = dist_dir / f"{app_name}.app"
        archive_name = f"{app_name}-{platform}.tar.gz"
        
        # Create tar.gz archive for macOS
        archive_path = dist_dir / archive_name
        subprocess.run([
            "tar", "-czf", str(archive_path),
            "-C", str(dist_dir),
            f"{app_name}.app"
        ], check=True)
        
    else:  # Windows
        source_path = dist_dir / app_name
        archive_name = f"{app_name}-{platform}.zip"
        
        # Create zip archive for Windows
        archive_path = dist_dir / archive_name
        shutil.make_archive(
            str(archive_path.with_suffix('')),
            'zip',
            str(source_path)
        )
    
    print(f"Created application archive: {archive_path}")
    return archive_path


def add_bundle_to_repo(repo, bundle_path: Path, version: str):
    """
    Add an application bundle to the tufup repository.
    
    Args:
        repo: Tufup repository instance
        bundle_path: Path to the application bundle/archive
        version: Version string
    """
    print(f"Adding bundle {bundle_path} to repository as version {version}")
    
    # Add the bundle to the repository
    repo.add_bundle(
        new_version=version,
        bundle_path=bundle_path
    )
    
    print(f"Bundle added successfully for version {version}")


def create_metadata_files(repo_dir: Path, app_name: str, version: str, platform: str):
    """
    Create additional metadata files for the GitHub release.
    
    Args:
        repo_dir: Repository directory
        app_name: Application name
        version: Version string
        platform: Platform identifier
    """
    metadata_dir = repo_dir / "metadata"
    
    # Create a simple version info file
    version_info = {
        "app_name": app_name,
        "version": version,
        "platform": platform,
        "tufup_version": "0.9.0"  # Current tufup version
    }
    
    version_file = metadata_dir / f"version-{platform}.json"
    with open(version_file, 'w') as f:
        json.dump(version_info, f, indent=2)
    
    print(f"Created version info: {version_file}")


def main():
    parser = argparse.ArgumentParser(description="Set up tufup repository for CaseBriefs")
    parser.add_argument("--app-name", default="CaseBriefs", help="Application name")
    parser.add_argument("--version", required=True, help="Application version")
    parser.add_argument("--platform", required=True, help="Platform identifier")
    parser.add_argument("--dist-dir", type=Path, required=True, help="Distribution directory")
    parser.add_argument("--repo-dir", type=Path, default=Path("tufup-repo"), help="Repository directory")
    parser.add_argument("--setup-only", action="store_true", help="Only set up repository, don't add bundle")
    
    args = parser.parse_args()
    
    print(f"Setting up tufup repository for {args.app_name} v{args.version}")
    
    if not TUFUP_AVAILABLE:
        print("INFO: tufup is not available in this environment.")
        print("Creating minimal repository structure for compatibility...")
        # Create minimal structure for development/CI compatibility
        args.repo_dir.mkdir(parents=True, exist_ok=True)
        (args.repo_dir / "metadata").mkdir(exist_ok=True)
        (args.repo_dir / "targets").mkdir(exist_ok=True)
        
        # Create basic metadata file
        create_metadata_files(args.repo_dir, args.app_name, args.version, args.platform)
        print(f"Created minimal repository structure at {args.repo_dir}")
        return
    
    # Set up the repository (when tufup is available)
    try:
        repo = setup_tufup_repo(args.repo_dir, args.app_name, args.version)
        
        if not args.setup_only:
            # Build application archive
            archive_path = build_app_archive(args.dist_dir, args.app_name, args.platform)
            
            # Add bundle to repository
            add_bundle_to_repo(repo, archive_path, args.version)
        
        # Create additional metadata
        create_metadata_files(args.repo_dir, args.app_name, args.version, args.platform)
        
        print(f"Tufup repository setup complete at {args.repo_dir}")
        
    except Exception as e:
        print(f"Warning: Full tufup setup failed: {e}")
        print("Creating minimal structure for compatibility...")
        
        # Fallback to minimal structure
        args.repo_dir.mkdir(parents=True, exist_ok=True)
        (args.repo_dir / "metadata").mkdir(exist_ok=True)
        (args.repo_dir / "targets").mkdir(exist_ok=True)
        create_metadata_files(args.repo_dir, args.app_name, args.version, args.platform)
        print(f"Created minimal repository structure at {args.repo_dir}")


if __name__ == "__main__":
    main()