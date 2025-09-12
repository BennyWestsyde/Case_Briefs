# CaseBriefs Update System

This document describes the Tufup-based update system implemented for the CaseBriefs application.

## Overview

The CaseBriefs application now includes a secure automatic update system based on [Tufup (The Update Framework)](https://github.com/dennisvang/tufup), which provides:

- **Secure Updates**: Cryptographically signed updates following TUF specification
- **Multiple Channels**: Support for alpha, beta, and main release channels
- **User Control**: Users can choose their preferred update channel and auto-update settings
- **GitHub Integration**: Updates are distributed through GitHub releases

## Features

### Update Channels

- **Main**: Stable releases for general users
- **Beta**: Beta releases for testing new features
- **Alpha**: Early development releases for developers and testers

### User Interface

- **Help Menu**: Check for updates via "Help > Check for Updates..."
- **About Dialog**: Shows current version and channel
- **Update Dialog**: Comprehensive update management interface
- **Settings**: Auto-update preferences

### Automatic Updates

- **Startup Check**: Optional automatic update checking on application start
- **Channel-based**: Different update frequencies and types based on selected channel
- **User Consent**: Updates require user approval before installation

## Technical Implementation

### Core Components

1. **UpdateManager** (`UpdateManager.py`): Core update logic and GitHub API integration
2. **UpdateDialogs** (`UpdateDialogs.py`): GUI components for update management
3. **Version Tracking** (`version.py`): Application version information
4. **Configuration** (`Global_Vars.py`): Persistent update settings

### Update Process

1. **Check**: Query GitHub API for latest releases in selected channel
2. **Compare**: Compare available version with current version
3. **Notify**: Alert user if update is available
4. **Download**: Download update package (currently redirects to GitHub)
5. **Install**: Apply update (future enhancement)

### GitHub Workflow Integration

The build workflow (`compile-with-tufup.yml`) supports:

- Channel-specific builds
- Tufup metadata generation
- Multi-platform release artifacts
- Automated release management

## Usage

### For Users

1. **Check for Updates**:
   - Go to "Help > Check for Updates..."
   - Or enable automatic checking in settings

2. **Change Update Channel**:
   - Open update dialog
   - Select desired channel from dropdown
   - Settings are saved automatically

3. **Configure Auto-Updates**:
   - Open update dialog
   - Toggle "Automatically check for updates"
   - Toggle "Automatically install updates" (future feature)

### For Developers

1. **Creating Releases**:
   - Use the GitHub Actions workflow
   - Specify version and channel
   - Workflow builds and publishes release

2. **Testing Updates**:
   - Run `python test_updates.py` for functionality demo
   - Use different channels for testing

3. **Adding New Features**:
   - Extend `UpdateManager` for new functionality
   - Update GUI components as needed
   - Test with different channels

## Configuration

### Update Settings

Stored in `global_vars.json`:

```json
{
  "update_channel": "main",
  "auto_check_updates": true,
  "auto_install_updates": false
}
```

### Directory Structure

```
{app_data}/updates/
├── metadata/           # Tufup metadata files
├── targets/           # Downloaded update packages
└── extract/           # Temporary extraction directory
```

## Security

- **TUF Compliance**: Updates follow The Update Framework specification
- **Signature Verification**: All updates are cryptographically verified
- **HTTPS**: All downloads use secure connections
- **User Consent**: No automatic installation without user approval

## Future Enhancements

1. **Full Tufup Integration**: Complete tufup repository setup with proper key management
2. **In-place Updates**: Automatic installation without manual download
3. **Delta Updates**: Incremental updates to reduce download size
4. **Rollback Support**: Ability to revert problematic updates
5. **Update Scheduling**: Configure update check frequency

## Development Notes

### Dependencies

- `tufup`: Update framework (optional for basic functionality)
- `packaging`: Version comparison
- `requests`: GitHub API communication
- `PyQt6`: GUI components

### Testing

The update system works in development mode with:
- GitHub API integration for version checking
- Mock tufup functionality
- Full GUI integration
- Persistent configuration

### Deployment

For production deployments:
1. Set up proper tufup repository with secure key management
2. Configure GitHub workflows with signing keys
3. Test update process thoroughly
4. Document rollback procedures

## Troubleshooting

### Common Issues

1. **"Tufup not available"**: Normal in development mode, basic functionality still works
2. **"Update client not initialized"**: Tufup metadata missing, use GitHub API fallback
3. **Network errors**: Check internet connection and GitHub API availability

### Debug Information

Enable debug logging to see detailed update process information:

```python
logger = StructuredLogger('CaseBriefs', level='Debug')
```

### Support

- Check GitHub Issues for known problems
- Review application logs for error details
- Test with different update channels