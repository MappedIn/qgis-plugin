# Mappedin MVF Importer - QGIS Plugin

A comprehensive QGIS plugin for importing Mappedin MVF (Mappedin Venue Format) v3 packages into QGIS as organized, styled vector layers.

## Description

This plugin provides seamless integration between Mappedin's indoor mapping platform and QGIS. Import MVF v3 packages either from local files or directly from the Mappedin API, with automatic layer organization, intelligent styling, and multi-floor visibility management for optimal visualization of indoor mapping data.

## Features

### 🗺️ **Dual Import Methods**
- **File Import**: Load MVF v3 packages from local ZIP files
- **API Import**: Direct download from Mappedin cloud with token caching

### 🏗️ **Smart Layer Organization**
- **Floor-based Grouping**: Automatically organizes layers by floor levels
- **Layer Categorization**: Separates doors, windows, walls, connections, spaces, and locations
- **Multi-floor Visibility**: Auto-hides upper floors, shows ground floor by default

### 🎨 **Intelligent Styling**
- **Doors**: White lines (1.4 width) with proper categorization
- **Windows**: Blue lines (1.2 width) for clear identification  
- **Walls**: Dark grey lines for structural elements
- **Connections**: Green arrow markers (size 4) for stairs/elevators only
- **Locations**: Styled point markers with labeling

### 🔧 **Advanced Features**
- **Token Caching**: Persistent API authentication across sessions
- **Door Navigation Filtering**: Excludes API navigation points from visualization
- **Empty Layer Prevention**: Only creates layers with actual data
- **Venue Selection**: User-friendly dropdown with fetch functionality

## Installation

### From QGIS Plugin Repository
1. In QGIS, go to **Plugins** → **Manage and Install Plugins**
2. Search for "Mappedin MVF Importer"
3. Click **Install Plugin**
4. Enable the plugin

### From ZIP File
1. Download the latest release ZIP file
2. In QGIS, go to **Plugins** → **Manage and Install Plugins**
3. Click **Install from ZIP**
4. Select the downloaded ZIP file
5. Enable the plugin

### Development Installation
1. Clone this repository:
   ```bash
   git clone https://github.com/mappedin/qgis-plugin.git
   ```
2. Copy the plugin folder to your QGIS plugins directory:
   - **Windows**: `C:\Users\{username}\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
3. Restart QGIS
4. Enable the plugin in **Plugins** → **Manage and Install Plugins**

## Usage

### File Import
1. Open QGIS
2. Go to **Plugins** → **Mappedin MVF Importer**
3. Select **Import from File**
4. Click **Browse** to select your MVF ZIP file
5. Click **Import** - layers will be automatically organized and styled

### API Import
1. Open QGIS
2. Go to **Plugins** → **Mappedin MVF Importer**
3. Select **Import from API**
4. Enter your **API Key** (starts with `mik_`)
5. Enter your **API Secret** (starts with `mis_`)
6. Click **Fetch Venues** to load available venues
7. Select a venue from the dropdown
8. Click **Import** - MVF will be downloaded and processed automatically

### Layer Organization
The plugin creates a comprehensive layer structure:

```
📁 {Venue Name}
├── 📁 Level 1 Group (visible by default)
│   ├── 📍 Level 1 - Locations
│   ├── 🚪 Level 1 - Doors (white lines)
│   ├── 🪟 Level 1 - Windows (blue lines)  
│   ├── 🧱 Level 1 - Walls (grey lines)
│   ├── ⬆️ Level 1 - Connections (green arrows)
│   └── 🏠 Level 1 - Spaces (polygons)
├── 📁 Level 2 Group (hidden by default)
│   └── ... (same structure)
└── 📐 Floor Boundaries (hidden by default)
```

### Multi-Floor Management
- **Ground floor** (Level 1) is visible by default
- **Upper floors** are automatically hidden to prevent overlap
- **Toggle visibility** using checkboxes in the Layers Panel
- **Floor boundaries** are hidden by default but available for reference

## API Configuration

### Getting API Credentials
1. Sign in to your [Mappedin account](https://app.mappedin.com)
2. Navigate to **Developer** → **API Keys**
3. Create a new API key/secret pair
4. Copy the generated credentials

### Token Management
- **Automatic Caching**: Tokens are cached for 2 hours to avoid repeated authentication
- **Secure Storage**: Credentials are saved locally using QGIS settings
- **Auto-Refresh**: Expired tokens are automatically refreshed when needed

## MVF v3 Format Support

This plugin supports the full [Mappedin MVF v3 specification](https://developer.mappedin.com/docs/mvf/v3/mvf-v3-specification/mvf-overview):

- **Core Extension**: Manifest, floors, geometry
- **Locations Extension**: Points of interest, categories
- **Navigation Data**: Connections, pathways, accessibility
- **Spatial Relationships**: Floor-to-floor connections
- **Metadata**: Venue information, floor names, styling

## Troubleshooting

### Common Issues

**"No venues available"**
- Verify your API credentials are correct
- Ensure your account has access to venues
- Check your internet connection

**"Failed to download MVF package"**
- Verify the venue ID is correct
- Ensure you have read permissions for the venue
- Try refreshing your venues list

**"Empty layers created"**
- Some MVF packages may not contain all layer types
- This is normal - only layers with data are created
- Check the original MVF package for data completeness

### Debug Information

If you encounter issues:
1. Open the QGIS **Log Messages Panel** (View → Panels → Log Messages)
2. Look for messages from the "Mappedin MVF Importer" tab
3. Include relevant log messages when reporting issues

## Development

### Building from Source

```bash
# Clone the repository
git clone https://github.com/mappedin/qgis-plugin.git
cd qgis-plugin

# Install to QGIS plugins directory
make dev-deploy

# Clean build artifacts
make dclean
```

### Project Structure

```
mappedin_mvf_importer/
├── __init__.py                          # Plugin initialization
├── mappedin_mvf_importer.py            # Main plugin class
├── mappedin_mvf_importer_dialog.py     # UI dialog
├── mappedin_mvf_importer_dialog_base.ui # UI layout
├── mappedin_api.py                     # API client
├── mvf_parser_v3.py                    # MVF parsing logic
├── resources.py                        # Qt resources
├── metadata.txt                        # Plugin metadata
└── README.md                           # Documentation
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Requirements

- **QGIS**: 3.16 or later
- **Python**: 3.7+
- **Dependencies**: requests (for API functionality)

## License

This project is licensed under the GPL v3 License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: [Mappedin Developer Docs](https://developer.mappedin.com)
- **Issues**: [GitHub Issues](https://github.com/mappedin/qgis-plugin/issues)
- **API Support**: [Mappedin Support](https://mappedin.com/support)

## Changelog

### v1.0.0
- Initial release with MVF v3 support
- File and API import methods
- Intelligent layer organization and styling
- Multi-floor visibility management
- Token caching and API authentication
- Door/window/wall categorization
- Navigation point filtering