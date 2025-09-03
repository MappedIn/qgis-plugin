"""
MVF v3 Parser Module - Updated for Real Mappedin MVF v3 Format
Handles parsing of Mappedin MVF v3 packages based on official specification
https://developer.mappedin.com/docs/mvf/v3/mvf-v3-specification/mvf-overview
"""

import os
import json
import zipfile
from typing import List, Dict, Any, Optional, Union

from qgis.core import (
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsField,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsWkbTypes,
    QgsFields,
    QgsLayerTreeGroup,
    QgsPalLayerSettings,
    QgsVectorLayerSimpleLabeling,
    QgsMarkerSymbol,
    QgsSingleSymbolRenderer,
    QgsLineSymbol,
    QgsFillSymbol,
    QgsSymbolLayer,
    QgsProperty
)
from qgis.PyQt.QtCore import QMetaType
from qgis.PyQt.QtGui import QColor, QFont


class MVFv3Parser:
    """
    Parser for Mappedin MVF v3 packages following the official specification.
    
    Supports:
    - Core extension (manifest, floors, geometry)
    - Locations extension (POIs and places of interest)
    - Proper GeoJSON structure
    - Floor-based organization
    - GeometryAnchors and utility types
    """
    
    def __init__(self):
        """Initialize the MVF v3 parser"""
        self.manifest = None
        self.floors = None
        self.geometry = {}  # floor_id -> FeatureCollection
        self.locations = None
        self.venue_name = "Unknown Venue"
        self.kinds = {}  # floor_id -> geometry_id -> kind mapping
        
    def parse_mvf_package(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse an MVF v3 package file
        
        Args:
            file_path (str): Path to the MVF package file
            
        Returns:
            List[Dict[str, Any]]: List of layer data dictionaries for QGIS
        """
        try:
            if file_path.lower().endswith(('.zip', '.mvf')):
                return self._parse_mvf_zip(file_path)
            else:
                raise ValueError(f"Unsupported file format. MVF v3 requires ZIP package: {file_path}")
                
        except Exception as e:
            raise Exception(f"Failed to parse MVF v3 package: {str(e)}")
    
    def _parse_mvf_zip(self, zip_path: str) -> List[Dict[str, Any]]:
        """Parse MVF v3 ZIP package according to specification"""
        layers_data = []
        
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            file_names = zip_file.namelist()
            
            # 1. Parse manifest (required)
            if 'manifest.geojson' in file_names:
                with zip_file.open('manifest.geojson') as f:
                    self.manifest = json.load(f)
                    self._extract_venue_info()
            else:
                pass
            
            # 2. Parse floors (required)
            if 'floors.geojson' in file_names:
                with zip_file.open('floors.geojson') as f:
                    self.floors = json.load(f)
                    layers_data.extend(self._process_floors())
            else:
                pass
            
            # 3. Parse kinds files (geometry type mappings)
            kinds_files = [f for f in file_names if f.startswith('kinds/') and f.endswith('.json')]
            for kinds_file in kinds_files:
                floor_id = self._extract_floor_id_from_filename(kinds_file)
                with zip_file.open(kinds_file) as f:
                    kinds_data = json.load(f)
                    self.kinds[floor_id] = kinds_data

            
            # 4. Parse geometry files (one per floor)
            geometry_files = [f for f in file_names if f.startswith('geometry/') and f.endswith('.geojson')]
            for geom_file in geometry_files:
                floor_id = self._extract_floor_id_from_filename(geom_file)
                with zip_file.open(geom_file) as f:
                    geometry_data = json.load(f)
                    self.geometry[floor_id] = geometry_data
                    layers_data.extend(self._process_geometry(floor_id, geometry_data))
            
            # 5. Parse locations (optional extension) - can be .json or .geojson
            locations_file = None
            if 'locations.geojson' in file_names:
                locations_file = 'locations.geojson'
            elif 'locations.json' in file_names:
                locations_file = 'locations.json'
            
            if locations_file:
                with zip_file.open(locations_file) as f:
                    locations_data = json.load(f)
                    # Handle both list format and object with list
                    if isinstance(locations_data, list):
                        self.locations = {'features': [{'properties': loc} for loc in locations_data]}
                    else:
                        self.locations = locations_data
                    layers_data.extend(self._process_locations())
            
            # 6. Look for other extensions
            for extension_file in file_names:
                if extension_file.endswith('.geojson') and extension_file not in [
                    'manifest.geojson', 'floors.geojson', 'locations.geojson'
                ] and not extension_file.startswith('geometry/'):
                    layers_data.extend(self._process_extension_file(zip_file, extension_file))
        
        return layers_data
    
    def _extract_venue_info(self):
        """Extract venue information from manifest"""
        if self.manifest and 'features' in self.manifest and len(self.manifest['features']) > 0:
            manifest_feature = self.manifest['features'][0]
            properties = manifest_feature.get('properties', {})
            self.venue_name = properties.get('name', 'Unknown Venue')
    
    def _extract_floor_id_from_filename(self, filename: str) -> str:
        """Extract floor ID from geometry filename (e.g., geometry/f_00000001.geojson -> f_00000001)"""
        basename = os.path.basename(filename)
        floor_id = basename.replace('.geojson', '').replace('.json', '')

        return floor_id
    
    def _process_floors(self) -> List[Dict[str, Any]]:
        """Process floors.geojson - creates floor boundary polygons"""
        if not self.floors or 'features' not in self.floors:
            # DEBUG: print("Skipping floor boundaries processing - no floor data found")
            return []
        
        if not self.floors['features']:
            # DEBUG: print("Skipping floor boundaries processing - empty floor features list")
            return []
        
        features = []
        for floor_feature in self.floors['features']:
            geometry = self._convert_geojson_geometry(floor_feature.get('geometry'))
            if geometry:
                properties = floor_feature.get('properties', {})
                floor_id = properties.get('id', 'unknown')
                details = properties.get('details', {})
                
                feature_data = {
                    'geometry': geometry,
                    'attributes': {
                        'floor_id': floor_id,
                        'name': details.get('name', f'Floor {floor_id}'),
                        'elevation': properties.get('elevation', 0),
                        'description': details.get('description', ''),
                        'external_id': details.get('externalId', '')
                    }
                }
                features.append(feature_data)
        
        if features:

            return [{
                'name': f'{self.venue_name} - Floor Boundaries',
                'type': 'polygon',
                'features': features,
                'fields': self._get_floor_fields()
            }]
        else:

        
        return []
    
    def _process_geometry(self, floor_id: str, geometry_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process geometry for a specific floor"""
        if not geometry_data or 'features' not in geometry_data:
            return []
        
        # Check if we have any valid features at all
        if not geometry_data['features']:
            return []
        
        # Group geometry by type AND by kind (doors, windows, walls, etc.)
        polygons = []
        lines = []
        points = []
        doors = []
        windows = []
        walls = []
        
        # Counters for debugging
        total_features = len(geometry_data['features'])
        objects_skipped = 0
        
        # Get kinds data for this floor
        floor_kinds = self.kinds.get(floor_id, {})
        # DEBUG: print(f"Floor {floor_id}: Found {len(floor_kinds)} kind mappings")
        
        # Debug: show what kinds we have
        if floor_kinds:
            kind_counts = {}
            for gid, kind in floor_kinds.items():
                kind_counts[kind] = kind_counts.get(kind, 0) + 1
            # DEBUG: print(f"Kind distribution: {kind_counts}")
        
        for geom_feature in geometry_data['features']:
            geometry = self._convert_geojson_geometry(geom_feature.get('geometry'))
            if not geometry:
                continue
                
            properties = geom_feature.get('properties', {})
            details = properties.get('details', {})
            geom_id = properties.get('id', '')
            
            # Get the kind/type of this geometry
            geom_kind = floor_kinds.get(geom_id, 'unknown')
            
            # Debug: show some examples of kind mapping
            if len(doors) + len(windows) + len(walls) < 5:  # Only show first few
                # DEBUG: print(f"Geometry {geom_id}: kind='{geom_kind}', geom_type={geometry.type()}")
            
            feature_data = {
                'geometry': geometry,
                'attributes': {
                    'geometry_id': geom_id,
                    'floor_id': floor_id,
                    'name': details.get('name', ''),
                    'description': details.get('description', ''),
                    'external_id': details.get('externalId', ''),
                    'icon': details.get('icon', ''),
                    'kind': geom_kind  # Add the kind information
                }
            }
            
            geom_type = geometry.type()
            
            # Skip objects entirely - they clutter the visualization
            kind_lower = geom_kind.lower()
            if 'object' in kind_lower:
                objects_skipped += 1
                continue
            
            # Categorize by kind first, then by geometry type
            if ('door' in kind_lower or 'entrance' in kind_lower or 
                'entry' in kind_lower or 'exit' in kind_lower):
                doors.append(feature_data)
                if len(doors) <= 3:  # Debug first few
                    # DEBUG: print(f"  -> Added to DOORS: {geom_id} (kind: {geom_kind})")
            elif 'window' in kind_lower:
                windows.append(feature_data)
                if len(windows) <= 3:  # Debug first few
                    # DEBUG: print(f"  -> Added to WINDOWS: {geom_id} (kind: {geom_kind})")
            elif 'wall' in kind_lower:
                walls.append(feature_data)
                if len(walls) <= 3:  # Debug first few
                    # DEBUG: print(f"  -> Added to WALLS: {geom_id} (kind: {geom_kind})")
            else:
                # Fallback to geometry type for other features (but only specific types for connections)
                if geom_type == QgsWkbTypes.PolygonGeometry:
                    # Only add non-object polygons
                    if 'object' not in kind_lower:
                        polygons.append(feature_data)
                    else:
                        if len(polygons) < 3:  # Debug what we're filtering
                            # DEBUG: print(f"  -> SKIPPED POLYGON OBJECT: {geom_id} (kind: {geom_kind})")
                elif geom_type == QgsWkbTypes.LineGeometry:
                    # Only add non-object lines
                    if 'object' not in kind_lower:
                        lines.append(feature_data)
                        if len(lines) <= 3:  # Debug first few lines
                            # DEBUG: print(f"  -> Added to LINES: {geom_id} (kind: {geom_kind})")
                    else:
                        if len(lines) < 3:  # Debug what we're filtering
                            # DEBUG: print(f"  -> SKIPPED LINE OBJECT: {geom_id} (kind: {geom_kind})")
                elif geom_type == QgsWkbTypes.PointGeometry:
                    # Skip door navigation points (API MVF creates -p1, -p2 points for doors)
                    is_door_navigation_point = ('-p1' in geom_id or '-p2' in geom_id)
                    
                    if is_door_navigation_point:
                        # DEBUG: print(f"  -> SKIPPED DOOR NAVIGATION POINT: {geom_id} (kind: {geom_kind}) - API door connection point")
                        continue
                    
                    # Add specific connection types OR unknown points (for backwards compatibility)
                    is_known_connection = ('stair' in kind_lower or 'elevator' in kind_lower or 
                                         'escalator' in kind_lower or 'lift' in kind_lower or
                                         'stairs' in kind_lower or 'elevators' in kind_lower)
                    is_unknown_point = (geom_kind == 'unknown' or 'poi' in kind_lower)
                    
                    if is_known_connection or is_unknown_point:
                        points.append(feature_data)
                        if len(points) <= 3:  # Debug first few points
                            connection_type = "known connection" if is_known_connection else "unknown/poi point"
                            # DEBUG: print(f"  -> Added to CONNECTIONS: {geom_id} (kind: {geom_kind}) - {connection_type}")
                    else:
                        if len(points) < 3:  # Debug what we're skipping
                            # DEBUG: print(f"  -> SKIPPED POINT: {geom_id} (kind: {geom_kind}) - filtered out")
                else:
                    pass
        
        # Debug summary
        processed_features = len(doors) + len(windows) + len(walls) + len(polygons) + len(lines) + len(points)
        # DEBUG: print(f"Processing summary: {total_features} total -> {objects_skipped} objects skipped -> {processed_features} features processed")
        
        layers = []
        floor_name = self._get_floor_name(floor_id)
        
        # Create doors layer (red, thick lines)
        if doors:
            layers.append({
                'name': f'{floor_name} - Doors',
                'type': 'linestring',
                'features': doors,
                'fields': self._get_geometry_fields(),
                'style_type': 'door'
            })
            # DEBUG: print(f"Created Doors layer for {floor_name} with {len(doors)} features")
        else:
            # DEBUG: print(f"Skipping empty Doors layer for {floor_name}")
        
        # Create windows layer (blue, thick lines)
        if windows:
            layers.append({
                'name': f'{floor_name} - Windows',
                'type': 'linestring',
                'features': windows,
                'fields': self._get_geometry_fields(),
                'style_type': 'window'
            })
            # DEBUG: print(f"Created Windows layer for {floor_name} with {len(windows)} features")
        else:
            # DEBUG: print(f"Skipping empty Windows layer for {floor_name}")
        
        # Create walls layer (dark grey, normal lines)
        if walls:
            layers.append({
                'name': f'{floor_name} - Walls',
                'type': 'linestring',
                'features': walls,
                'fields': self._get_geometry_fields(),
                'style_type': 'wall'
            })
            # DEBUG: print(f"Created Walls layer for {floor_name} with {len(walls)} features")
        else:
            # DEBUG: print(f"Skipping empty Walls layer for {floor_name}")
        
        # Only create layers if they have actual features
        if polygons:
            layers.append({
                'name': f'{floor_name} - Spaces',
                'type': 'polygon',
                'features': polygons,
                'fields': self._get_geometry_fields()
            })
            # DEBUG: print(f"Created Spaces layer for {floor_name} with {len(polygons)} features")
        else:
            # DEBUG: print(f"Skipping empty Spaces layer for {floor_name}")
        
        if lines:
            layers.append({
                'name': f'{floor_name} - Doors',
                'type': 'linestring',
                'features': lines,
                'fields': self._get_geometry_fields(),
                'style_type': 'line_doors'
            })
            # DEBUG: print(f"Created Doors layer for {floor_name} with {len(lines)} features")
        else:
            # DEBUG: print(f"Skipping empty Doors layer for {floor_name}")
        
        if points:
            layers.append({
                'name': f'{floor_name} - Connections',
                'type': 'point',
                'features': points,
                'fields': self._get_geometry_fields()
            })
            # DEBUG: print(f"Created Connections layer for {floor_name} with {len(points)} features")
        else:
            # DEBUG: print(f"Skipping empty Connections layer for {floor_name}")
        
        return layers
    
    def _process_locations(self) -> List[Dict[str, Any]]:
        """Process locations.json/geojson - POIs and places of interest"""
        if not self.locations:
            # DEBUG: print("Skipping locations processing - no location data found")
            return []
        
        # Handle both list and FeatureCollection formats
        location_list = []
        if 'features' in self.locations:
            location_list = [f.get('properties', {}) for f in self.locations['features']]
        elif isinstance(self.locations, list):
            location_list = self.locations
        else:
            location_list = [self.locations]
        
        if not location_list:
            # DEBUG: print("Skipping locations processing - empty location list")
            return []
        
        features = []
        processed_count = 0
        found_count = 0
        
        for location_data in location_list:
            processed_count += 1
            location_id = location_data.get('id', 'unknown')
            location_name = location_data.get('details', {}).get('name', 'Unnamed')
            
            # Locations use geometryAnchors to link to geometry
            geometry_anchors = location_data.get('geometryAnchors', [])
            if not geometry_anchors:
                continue
            
            # Collect all geometries for all anchors (locations can span multiple)
            geometries = []
            anchor_details = []
            for anchor in geometry_anchors:
                gid = anchor.get('geometryId')
                fid = anchor.get('floorId')
                geom = self._find_geometry_by_id(gid, fid)
                if geom:
                    geometries.append((fid, gid, geom))
                    anchor_details.append((fid, gid))
            if not geometries:
                continue
            found_count += 1
            
            details = location_data.get('details', {})
            categories = location_data.get('categories', [])
            
            # Handle category names - they might be objects or strings
            category_names = []
            for cat in categories:
                if isinstance(cat, dict):
                    category_names.append(cat.get('name', ''))
                else:
                    category_names.append(str(cat))
            
            # Emit a feature for each matched geometry anchor
            for fid, gid, geom in geometries:
                if geom.type() == QgsWkbTypes.PointGeometry:
                    location_geometry = geom
                else:
                    location_geometry = geom.centroid()
                feature_data = {
                    'geometry': location_geometry,
                    'attributes': {
                        'location_id': location_data.get('id', ''),
                        'name': details.get('name', ''),
                        'description': details.get('description', ''),
                        'external_id': details.get('externalId', ''),
                        'icon': details.get('icon', ''),
                        'categories': ', '.join(category_names),
                        'floor_id': fid,
                        'geometry_id': gid,
                        'anchor_count': str(len(geometry_anchors))
                    }
                }
                features.append(feature_data)
        
        if not features:
            # DEBUG: print(f"Skipping locations processing - no valid location features found (processed {processed_count} locations)")
            return []
        
        # Group locations by floor for separate layers
        floor_locations = {}
        for feature_data in features:
            floor_id = feature_data['attributes']['floor_id']
            if floor_id not in floor_locations:
                floor_locations[floor_id] = []
            floor_locations[floor_id].append(feature_data)
        
        # Create separate layers for each floor
        location_layers = []
        for floor_id, floor_features in floor_locations.items():
            # Get floor name from floors data
            floor_name = self._get_floor_name(floor_id)
            
            location_layers.append({
                'name': f'{floor_name} - Locations',
                'type': 'point',
                'features': floor_features,
                'fields': self._get_location_fields()
            })
            # DEBUG: print(f"Created Locations layer for {floor_name} with {len(floor_features)} features")
            
        
        return location_layers
    
    def _configure_location_layer_styling(self, layer: QgsVectorLayer):
        """Configure visual styling for location points"""
        # Create a bright, visible symbol for locations
        symbol = QgsMarkerSymbol.createSimple({
            'name': 'circle',
            'color': '#FF4444',  # Bright red
            'outline_color': '#FFFFFF',  # White outline
            'outline_width': '0.5',
            'size': '4'  # Larger size for visibility
        })
        
        # Apply single symbol renderer
        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        
        # Refresh the layer
        layer.triggerRepaint()
    
    def _configure_location_labels(self, layer: QgsVectorLayer):
        """Configure text labels for location points"""
        # Create label settings
        label_settings = QgsPalLayerSettings()
        
        # Set the field to use for labels (location name)
        label_settings.fieldName = 'name'
        
        # Configure label appearance
        label_settings.enabled = True
        
        # Text formatting
        text_format = label_settings.format()
        text_format.setColor(QColor(0, 0, 0))  # Black text
        text_format.setSize(10)  # Font size
        # Create proper QFont object
        font = QFont()
        font.setFamily('Arial')
        font.setPointSize(10)
        text_format.setFont(font)
        
        # Add white buffer around text for readability
        buffer_settings = text_format.buffer()
        buffer_settings.setEnabled(True)
        buffer_settings.setSize(1)
        buffer_settings.setColor(QColor(255, 255, 255))  # White buffer
        
        text_format.setBuffer(buffer_settings)
        label_settings.setFormat(text_format)
        
        # Label placement - around point
        label_settings.placement = QgsPalLayerSettings.AroundPoint
        
        # Avoid overlaps
        label_settings.displayAll = True
        
        # Apply labeling to layer
        labeling = QgsVectorLayerSimpleLabeling(label_settings)
        layer.setLabelsEnabled(True)
        layer.setLabeling(labeling)
        
        # Refresh the layer
        layer.triggerRepaint()

    def _configure_line_layer_styling(self, layer: QgsVectorLayer):
        """High-contrast styling for floor Lines layers."""
        try:
            symbol = QgsLineSymbol.createSimple({
                'color': '#333333',  # dark grey
                'width': '0.8',
                'capstyle': 'round',
                'joinstyle': 'round'
            })
            # Scale-dependent width: thinner when zoomed out, thicker when zoomed in
            try:
                first_layer = symbol.symbolLayer(0)
                width_expr = QgsProperty.fromExpression('scale_linear(@map_scale, 1000, 100000, 1.1, 0.3)')
                first_layer.setDataDefinedProperty(QgsSymbolLayer.PropertyStrokeWidth, width_expr)
            except Exception:
                pass
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        except Exception:
            pass

    def _configure_space_layer_styling(self, layer: QgsVectorLayer):
        """High-contrast styling for floor Spaces layers."""
        try:
            symbol = QgsFillSymbol.createSimple({
                'color': '#FFFFFF',            # white fill
                'outline_color': '#4D4D4D',    # dark grey outline
                'outline_width': '0.4',
                'style': 'solid'
            })
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            layer.setOpacity(1.0)
        except Exception:
            pass

    def _configure_door_layer_styling(self, layer: QgsVectorLayer):
        """White styling for door layers."""
        try:
            symbol = QgsLineSymbol.createSimple({
                'color': '#FFFFFF',  # white
                'width': '1.4',      # custom width
                'capstyle': 'round',
                'joinstyle': 'round'
            })
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        except Exception:
            pass

    def _configure_window_layer_styling(self, layer: QgsVectorLayer):
        """Blue styling for window layers."""
        try:
            symbol = QgsLineSymbol.createSimple({
                'color': '#0066FF',  # bright blue
                'width': '1.2',      # updated width
                'capstyle': 'round',
                'joinstyle': 'round'
            })
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        except Exception:
            pass

    def _configure_wall_layer_styling(self, layer: QgsVectorLayer):
        """Dark grey styling for wall layers."""
        try:
            symbol = QgsLineSymbol.createSimple({
                'color': '#333333',  # dark grey
                'width': '0.8',
                'capstyle': 'round',
                'joinstyle': 'round'
            })
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        except Exception:
            pass

    def _configure_connections_layer_styling(self, layer: QgsVectorLayer):
        """Green arrow styling for connections layer."""
        try:
            symbol = QgsMarkerSymbol.createSimple({
                'name': 'arrow',
                'color': '#47d200',  # bright green
                'outline_width': '0',  # no outline
                'size': '4'  # size 4
            })
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        except Exception:
            pass

    def _configure_line_doors_layer_styling(self, layer: QgsVectorLayer):
        """White styling for line doors layer."""
        try:
            symbol = QgsLineSymbol.createSimple({
                'color': '#FFFFFF',  # white
                'width': '1.4',      # same as door width
                'capstyle': 'round',
                'joinstyle': 'round'
            })
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        except Exception:
            pass
    
    def _process_extension_file(self, zip_file: zipfile.ZipFile, filename: str) -> List[Dict[str, Any]]:
        """Process additional extension files"""
        try:
            with zip_file.open(filename) as f:
                data = json.load(f)
            
            extension_name = filename.replace('.geojson', '').replace('_', ' ').title()
            
            # Generic processing for unknown extensions
            if 'features' in data:
                features = []
                for feature in data['features']:
                    geometry = self._convert_geojson_geometry(feature.get('geometry'))
                    if geometry:
                        properties = feature.get('properties', {})
                        feature_data = {
                            'geometry': geometry,
                            'attributes': {
                                'id': properties.get('id', ''),
                                'data': json.dumps(properties)  # Store all properties as JSON
                            }
                        }
                        features.append(feature_data)
                
                if features:
                    return [{
                        'name': f'{self.venue_name} - {extension_name}',
                        'type': 'mixed',  # Will be determined by first feature
                        'features': features,
                        'fields': self._get_extension_fields()
                    }]
        
        except Exception as e:
            pass
        
        return []
    
    def _find_geometry_by_id(self, geometry_id: str, floor_id: str) -> Optional[QgsGeometry]:
        """Find geometry by ID within a specific floor's geometry collection"""
        if floor_id not in self.geometry:
            return None
        
        floor_geometry = self.geometry[floor_id]
        if 'features' not in floor_geometry:
            return None
        
        for feature in floor_geometry['features']:
            properties = feature.get('properties', {})
            if properties.get('id') == geometry_id:
                return self._convert_geojson_geometry(feature.get('geometry'))
        
        return None
    
    def _get_floor_name(self, floor_id: str) -> str:
        """Get human-readable floor name"""
        if not self.floors or 'features' not in self.floors:
            return floor_id
        
        for floor_feature in self.floors['features']:
            properties = floor_feature.get('properties', {})
            if properties.get('id') == floor_id:
                details = properties.get('details', {})
                return details.get('name', floor_id)
        
        return floor_id
    
    def _convert_geojson_geometry(self, geojson_geom: Dict[str, Any]) -> Optional[QgsGeometry]:
        """Convert GeoJSON geometry to QgsGeometry"""
        if not geojson_geom or 'type' not in geojson_geom:
            return None
        
        try:
            geom_type = geojson_geom['type']
            coordinates = geojson_geom.get('coordinates', [])
            
            if geom_type == 'Point':
                if len(coordinates) >= 2:
                    return QgsGeometry.fromPointXY(QgsPointXY(coordinates[0], coordinates[1]))
            
            elif geom_type == 'LineString':
                points = [QgsPointXY(coord[0], coord[1]) for coord in coordinates if len(coord) >= 2]
                if points:
                    return QgsGeometry.fromPolylineXY(points)
            
            elif geom_type == 'Polygon':
                if coordinates and len(coordinates[0]) > 0:
                    # Outer ring
                    points = [QgsPointXY(coord[0], coord[1]) for coord in coordinates[0] if len(coord) >= 2]
                    if points:
                        return QgsGeometry.fromPolygonXY([points])
            
            elif geom_type == 'MultiPoint':
                points = []
                for coord in coordinates:
                    if len(coord) >= 2:
                        points.append(QgsPointXY(coord[0], coord[1]))
                if points:
                    return QgsGeometry.fromMultiPointXY(points)
            
            elif geom_type == 'MultiLineString':
                lines = []
                for line_coords in coordinates:
                    points = [QgsPointXY(coord[0], coord[1]) for coord in line_coords if len(coord) >= 2]
                    if points:
                        lines.append(points)
                if lines:
                    return QgsGeometry.fromMultiPolylineXY(lines)
            
            elif geom_type == 'MultiPolygon':
                polygons = []
                for polygon_coords in coordinates:
                    if polygon_coords and len(polygon_coords[0]) > 0:
                        points = [QgsPointXY(coord[0], coord[1]) for coord in polygon_coords[0] if len(coord) >= 2]
                        if points:
                            polygons.append([points])
                if polygons:
                    return QgsGeometry.fromMultiPolygonXY(polygons)
            
        except Exception as e:
            pass
        
        return None
    
    def _get_floor_fields(self) -> QgsFields:
        """Define fields for floor boundary layers"""
        fields = QgsFields()
        fields.append(QgsField('floor_id', QMetaType.QString))
        fields.append(QgsField('name', QMetaType.QString))
        fields.append(QgsField('elevation', QMetaType.Double))
        fields.append(QgsField('description', QMetaType.QString))
        fields.append(QgsField('external_id', QMetaType.QString))
        return fields
    
    def _get_geometry_fields(self) -> QgsFields:
        """Define fields for geometry layers"""
        fields = QgsFields()
        fields.append(QgsField('geometry_id', QMetaType.QString))
        fields.append(QgsField('floor_id', QMetaType.QString))
        fields.append(QgsField('name', QMetaType.QString))
        fields.append(QgsField('description', QMetaType.QString))
        fields.append(QgsField('external_id', QMetaType.QString))
        fields.append(QgsField('icon', QMetaType.QString))
        fields.append(QgsField('kind', QMetaType.QString))  # Add kind field
        return fields
    
    def _get_location_fields(self) -> QgsFields:
        """Define fields for location layers"""
        fields = QgsFields()
        fields.append(QgsField('location_id', QMetaType.QString))
        fields.append(QgsField('name', QMetaType.QString))
        fields.append(QgsField('description', QMetaType.QString))
        fields.append(QgsField('external_id', QMetaType.QString))
        fields.append(QgsField('icon', QMetaType.QString))
        fields.append(QgsField('categories', QMetaType.QString))
        fields.append(QgsField('floor_id', QMetaType.QString))
        fields.append(QgsField('geometry_id', QMetaType.QString))
        fields.append(QgsField('anchor_count', QMetaType.QString))  # Changed to String to avoid type issues
        return fields
    
    def _configure_location_layer_styling(self, layer: QgsVectorLayer):
        """Configure visual styling for location points"""
        # Create a bright, visible symbol for locations
        symbol = QgsMarkerSymbol.createSimple({
            'name': 'circle',
            'color': '#FF4444',  # Bright red
            'outline_color': '#FFFFFF',  # White outline
            'outline_width': '0.5',
            'size': '4'  # Larger size for visibility
        })
        
        # Apply single symbol renderer
        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        
        # Refresh the layer
        layer.triggerRepaint()
    
    def _configure_location_labels(self, layer: QgsVectorLayer):
        """Configure text labels for location points"""
        # Create label settings
        label_settings = QgsPalLayerSettings()
        
        # Set the field to use for labels (location name)
        label_settings.fieldName = 'name'
        
        # Configure label appearance
        label_settings.enabled = True
        
        # Text formatting
        text_format = label_settings.format()
        text_format.setColor(QColor(0, 0, 0))  # Black text
        text_format.setSize(10)  # Font size
        # Create proper QFont object
        font = QFont()
        font.setFamily('Arial')
        font.setPointSize(10)
        text_format.setFont(font)
        
        # Add white buffer around text for readability
        buffer_settings = text_format.buffer()
        buffer_settings.setEnabled(True)
        buffer_settings.setSize(1)
        buffer_settings.setColor(QColor(255, 255, 255))  # White buffer
        
        text_format.setBuffer(buffer_settings)
        label_settings.setFormat(text_format)
        
        # Label placement - around point
        label_settings.placement = QgsPalLayerSettings.AroundPoint
        
        # Avoid overlaps
        label_settings.displayAll = True
        
        # Apply labeling to layer
        labeling = QgsVectorLayerSimpleLabeling(label_settings)
        layer.setLabelsEnabled(True)
        layer.setLabeling(labeling)
        
        # Refresh the layer
        layer.triggerRepaint()
    
    def _get_extension_fields(self) -> QgsFields:
        """Define fields for generic extension layers"""
        fields = QgsFields()
        fields.append(QgsField('id', QMetaType.QString))
        fields.append(QgsField('data', QMetaType.QString))
        return fields
    
    def create_qgis_layer(self, layer_info: Dict[str, Any]) -> Optional[QgsVectorLayer]:
        """Create a QGIS vector layer from layer info"""
        try:
            # Determine geometry type from first feature if type is 'mixed'
            geom_type = layer_info['type']
            if geom_type == 'mixed' and layer_info['features']:
                first_geom = layer_info['features'][0]['geometry']
                if first_geom.type() == QgsWkbTypes.PointGeometry:
                    geom_type = 'point'
                elif first_geom.type() == QgsWkbTypes.LineGeometry:
                    geom_type = 'linestring'
                elif first_geom.type() == QgsWkbTypes.PolygonGeometry:
                    geom_type = 'polygon'
            
            # Map to QGIS geometry types
            geom_type_map = {
                'point': 'Point',
                'linestring': 'LineString', 
                'polygon': 'Polygon'
            }
            
            qgis_geom_type = geom_type_map.get(geom_type, 'Point')
            
            # Create the layer
            layer = QgsVectorLayer(
                f"{qgis_geom_type}?crs=EPSG:4326",  # MVF uses WGS84
                layer_info['name'],
                'memory'
            )
            
            # Add fields with debug info
            provider = layer.dataProvider()
            provider.addAttributes(layer_info['fields'])
            layer.updateFields()
            
            # Add features 
            features = []
            
            for i, feature_data in enumerate(layer_info['features']):
                feature = QgsFeature(layer.fields())
                feature.setGeometry(feature_data['geometry'])
                
                # Set attributes using ordered values (more reliable than setAttribute by name)
                field_names = [field.name() for field in layer.fields()]
                attribute_values = []
                for field_name in field_names:
                    value = feature_data['attributes'].get(field_name, '')
                    attribute_values.append(value)
                
                feature.setAttributes(attribute_values)
                features.append(feature)
            
            add_result = provider.addFeatures(features)
            

            
            # Force layer refresh and update
            layer.updateExtents()
            layer.reload()
            layer.triggerRepaint()
            
            # Configure styling based on layer type
            layer_name = layer_info.get('name', '')
            style_type = layer_info.get('style_type', '')
            
            if 'Locations' in layer_name:
                self._configure_location_layer_styling(layer)
                self._configure_location_labels(layer)
                layer.triggerRepaint()
            elif style_type == 'door':
                self._configure_door_layer_styling(layer)
                layer.triggerRepaint()
            elif style_type == 'window':
                self._configure_window_layer_styling(layer)
                layer.triggerRepaint()
            elif style_type == 'wall':
                self._configure_wall_layer_styling(layer)
                layer.triggerRepaint()
            elif style_type == 'line_doors':
                self._configure_line_doors_layer_styling(layer)
                layer.triggerRepaint()
            elif 'Connections' in layer_name:
                self._configure_connections_layer_styling(layer)
                layer.triggerRepaint()
            elif 'Lines' in layer_name:
                self._configure_line_layer_styling(layer)
                layer.triggerRepaint()
            elif 'Spaces' in layer_name:
                self._configure_space_layer_styling(layer)
                layer.triggerRepaint()
            
            # Layer will be added to project by the calling method
            # (to handle proper grouping and ordering)
            
            return layer
            
        except Exception as e:
            return None


# Alias for backward compatibility
MVFParser = MVFv3Parser
