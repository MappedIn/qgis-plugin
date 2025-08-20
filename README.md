# Mappedin MVF Importer - QGIS Plugin

A QGIS plugin for importing Mappedin MVF v3 (Map Venue Format) packages directly into QGIS as vector layers.

## Features

- Import Mappedin MVF v3 packages (ZIP package per spec)
- Automatically create separate layers for:
  - Floor plans (polygon layers)
  - Points of Interest (point layers)
- User-friendly import dialog with options

## Installation

### Option 1: Manual Installation

1. Copy the entire plugin folder to your QGIS plugins directory:
   - **Windows**: `C:\Users\{username}\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

2. Rename the folder to `mappedin_mvf_importer`

3. Open QGIS and go to **Plugins → Manage and Install Plugins → Installed**

4. Find "Mappedin MVF Importer" and enable it

### Option 2: Development Installation

If you're developing or testing the plugin:

1. Clone or download this repository
2. Compile the resources: `make compile`
3. Deploy to QGIS: `make deploy`

## Usage

1. **Open the Import Dialog**:
   - Go to **Vector → Mappedin MVF Importer → Import Mappedin MVF Package**
   - Or click the Mappedin icon in the toolbar

2. **Select MVF v3 Package**:
   - Click "Browse..." to select your MVF package file
   - Supported format: `.zip` (MVF v3 package)

3. **Configure Import Options**:
   - **Import floor plans**: Import building floor polygons
   - **Import points of interest (POIs)**: Import POI point features
   - **Organize layers by floor**: Group layers by floor level

4. **Import**: Click "OK" to import the data

## MVF Package Format Support

Limitations and notes:
- MultiPoint/MultiLineString/MultiPolygon are supported for geometry conversion, but some advanced ring handling may be refined in future versions.
- Locations with multiple geometry anchors will generate a feature per anchor (so multi-floor or multi-geometry associations work).
- Generic extension ingestion is intentionally conservative to avoid importing low-level nodes; only simple FeatureCollections are added.

The plugin supports various MVF package formats:

### ZIP-based MVF Packages
- `venue.json`: Venue metadata
- `floors/*.json`: Floor plan data
- `pois/*.json`: Points of interest data

### Single JSON Files
Expected structure:
```json
{
  "venue": { ... },
  "floors": [ ... ],
  "pois": [ ... ]
}
```

### Supported Geometry Formats
- GeoJSON-style coordinates
- Simple coordinate arrays
- Point objects with x/y properties

## Development

### Requirements
- QGIS 3.0+
- Python 3.6+
- PyQt5

### Building
```bash
# Compile resources
make compile

# Run tests
make test

# Clean generated files
make clean

# Deploy to QGIS
make deploy

# Create distribution package
make package
```

### File Structure
```
mappedin_mvf_importer/
├── __init__.py                          # Plugin initialization
├── mappedin_mvf_importer.py            # Main plugin class
├── mappedin_mvf_importer_dialog.py     # Import dialog
├── mappedin_mvf_importer_dialog_base.ui # UI layout
├── mvf_parser.py                       # MVF parsing logic
├── resources.py                        # Compiled resources
├── resources.qrc                       # Resource definitions
├── metadata.txt                        # Plugin metadata
├── icon.png                           # Plugin icon
├── Makefile                           # Build configuration
└── README.md                          # Documentation
```

## Customization

### Adding New MVF Data Types

To support additional MVF data types, modify `mvf_parser.py`:

1. Add parsing logic in the `MVFParser` class
2. Create field definitions for new data types
3. Implement geometry conversion for new formats

### Modifying the UI

The import dialog can be customized by editing:
- `mappedin_mvf_importer_dialog_base.ui` - UI layout
- `mappedin_mvf_importer_dialog.py` - Dialog behavior

## Troubleshooting

### Common Issues

1. **Plugin not appearing in QGIS**:
   - Ensure the plugin folder is in the correct location
   - Check that the folder is named `mappedin_mvf_importer`
   - Verify the plugin is enabled in the Plugin Manager

2. **Import fails with "Invalid MVF format"**:
   - Check that your MVF file contains valid JSON
   - Ensure geometry data is in a supported format
   - Verify the file is not corrupted

3. **Layers not displaying correctly**:
   - Check the QGIS message log for detailed error information
   - Verify coordinate reference system settings
   - Ensure geometry data is valid

### Debug Mode

For debugging, you can enable Python console output in the plugin code by uncommenting print statements in `mvf_parser.py`.

## License

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.

Trademark and Branding Notice: The Mappedin name and logo (`logowhite.png`) are trademarks of Mappedin. They are included solely for identification within this plugin and are not licensed for reuse, redistribution, or modification outside the plugin.

## Support

For issues and questions:
- Check the troubleshooting section above
- Review QGIS logs for detailed error messages
- Ensure your MVF package format is compatible

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly with various MVF formats
5. Submit a pull request

## Changelog

### Version 1.0.0
- Initial release
- Support for ZIP and JSON MVF packages
- Floor plan and POI import
- Configurable import options
- QGIS 3.x compatibility
