#!/usr/bin/env python3
"""
Test script to demonstrate the CaseBriefs update functionality.

This script shows how the update system works without requiring a GUI.
"""

import sys
from pathlib import Path

# Add the current directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from UpdateManager import UpdateManager, UpdateChannel, UpdateStatus
from Global_Vars import Global_Vars
from logger import StructuredLogger


def main():
    """Demonstrate the update functionality."""
    print("CaseBriefs Update System Demo")
    print("=" * 40)
    
    # Initialize components
    logger = StructuredLogger('demo', level='Info')
    global_vars = Global_Vars(logger)
    update_manager = UpdateManager(global_vars, logger)
    
    # Display current configuration
    print(f"Application: {update_manager.app_name}")
    print(f"Current Version: {update_manager.current_version}")
    print(f"Update Channel: {update_manager.channel.value}")
    print(f"Repository: {update_manager.repository_owner}/{update_manager.repository_name}")
    print(f"Auto-check Updates: {global_vars.auto_check_updates}")
    print(f"Auto-install Updates: {global_vars.auto_install_updates}")
    print()
    
    # Test channel switching
    print("Testing Channel Switching:")
    for channel in UpdateChannel:
        update_manager.channel = channel
        print(f"  - Switched to: {channel.value}")
    
    # Reset to main channel
    update_manager.channel = UpdateChannel.MAIN
    print(f"  - Reset to: {update_manager.channel.value}")
    print()
    
    # Test update checking
    print("Checking for Updates:")
    try:
        status, version, error = update_manager.check_for_updates()
        print(f"  Status: {status.value}")
        print(f"  Version: {version}")
        if error:
            print(f"  Error: {error}")
        
        if status == UpdateStatus.UPDATE_AVAILABLE:
            print("  📦 Update available!")
        elif status == UpdateStatus.UP_TO_DATE:
            print("  ✅ Application is up to date")
        else:
            print("  ❌ Error checking for updates")
            
    except Exception as e:
        print(f"  ❌ Exception during update check: {e}")
    
    print()
    
    # Test configuration persistence
    print("Testing Configuration Persistence:")
    original_auto_check = global_vars.auto_check_updates
    global_vars.auto_check_updates = not original_auto_check
    print(f"  - Changed auto-check from {original_auto_check} to {global_vars.auto_check_updates}")
    
    # Create a new instance to test persistence
    new_global_vars = Global_Vars(logger)
    print(f"  - New instance has auto-check: {new_global_vars.auto_check_updates}")
    
    if new_global_vars.auto_check_updates == global_vars.auto_check_updates:
        print("  ✅ Configuration persistence works")
    else:
        print("  ❌ Configuration persistence failed")
    
    # Restore original setting
    global_vars.auto_check_updates = original_auto_check
    print(f"  - Restored auto-check to: {original_auto_check}")
    print()
    
    # Show available channels
    print("Available Update Channels:")
    for channel in update_manager.get_available_channels():
        print(f"  - {channel.value}")
    print()
    
    print("Update System Demo Complete!")
    print("The update system is ready to work with GitHub releases.")


if __name__ == "__main__":
    main()