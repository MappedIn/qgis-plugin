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
from qgis.PyQt.QtCore import QVariant
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
            
            # 3. Parse geometry files (one per floor)
            geometry_files = [f for f in file_names if f.startswith('geometry/') and f.endswith('.geojson')]
            for geom_file in geometry_files:
                floor_id = self._extract_floor_id_from_filename(geom_file)
                with zip_file.open(geom_file) as f:
                    geometry_data = json.load(f)
                    self.geometry[floor_id] = geometry_data
                    layers_data.extend(self._process_geometry(floor_id, geometry_data))
            
            # 4. Parse locations (optional extension) - can be .json or .geojson
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
            
            # 5. Look for other extensions
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
        return basename.replace('.geojson', '')
    
    def _process_floors(self) -> List[Dict[str, Any]]:
        """Process floors.geojson - creates floor boundary polygons"""
        if not self.floors or 'features' not in self.floors:
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
        
        return []
    
    def _process_geometry(self, floor_id: str, geometry_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process geometry for a specific floor"""
        if not geometry_data or 'features' not in geometry_data:
            return []
        
        # Group geometry by type
        polygons = []
        lines = []
        points = []
        
        for geom_feature in geometry_data['features']:
            geometry = self._convert_geojson_geometry(geom_feature.get('geometry'))
            if not geometry:
                continue
                
            properties = geom_feature.get('properties', {})
            details = properties.get('details', {})
            
            feature_data = {
                'geometry': geometry,
                'attributes': {
                    'geometry_id': properties.get('id', ''),
                    'floor_id': floor_id,
                    'name': details.get('name', ''),
                    'description': details.get('description', ''),
                    'external_id': details.get('externalId', ''),
                    'icon': details.get('icon', '')
                }
            }
            
            geom_type = geometry.type()
            geom_type_name = geometry.wkbType()
            
            # Debug geometry types
            geom_id = properties.get('id', 'unknown')
            
            if geom_type == QgsWkbTypes.PolygonGeometry:
                polygons.append(feature_data)
            elif geom_type == QgsWkbTypes.LineGeometry:
                lines.append(feature_data)
            elif geom_type == QgsWkbTypes.PointGeometry:
                points.append(feature_data)
            else:
                pass
        
        layers = []
        floor_name = self._get_floor_name(floor_id)
        
        if polygons:
            layers.append({
                'name': f'{floor_name} - Spaces',
                'type': 'polygon',
                'features': polygons,
                'fields': self._get_geometry_fields()
            })
        
        if lines:
            layers.append({
                'name': f'{floor_name} - Lines',
                'type': 'linestring',
                'features': lines,
                'fields': self._get_geometry_fields()
            })
        
        if points:
            layers.append({
                'name': f'{floor_name} - Connections',
                'type': 'point',
                'features': points,
                'fields': self._get_geometry_fields()
            })
        
        return layers
    
    def _process_locations(self) -> List[Dict[str, Any]]:
        """Process locations.json/geojson - POIs and places of interest"""
        if not self.locations:
            return []
        
        # Handle both list and FeatureCollection formats
        location_list = []
        if 'features' in self.locations:
            location_list = [f.get('properties', {}) for f in self.locations['features']]
        elif isinstance(self.locations, list):
            location_list = self.locations
        else:
            location_list = [self.locations]
        
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
        fields.append(QgsField('floor_id', QVariant.String))
        fields.append(QgsField('name', QVariant.String))
        fields.append(QgsField('elevation', QVariant.Double))
        fields.append(QgsField('description', QVariant.String))
        fields.append(QgsField('external_id', QVariant.String))
        return fields
    
    def _get_geometry_fields(self) -> QgsFields:
        """Define fields for geometry layers"""
        fields = QgsFields()
        fields.append(QgsField('geometry_id', QVariant.String))
        fields.append(QgsField('floor_id', QVariant.String))
        fields.append(QgsField('name', QVariant.String))
        fields.append(QgsField('description', QVariant.String))
        fields.append(QgsField('external_id', QVariant.String))
        fields.append(QgsField('icon', QVariant.String))
        return fields
    
    def _get_location_fields(self) -> QgsFields:
        """Define fields for location layers"""
        fields = QgsFields()
        fields.append(QgsField('location_id', QVariant.String))
        fields.append(QgsField('name', QVariant.String))
        fields.append(QgsField('description', QVariant.String))
        fields.append(QgsField('external_id', QVariant.String))
        fields.append(QgsField('icon', QVariant.String))
        fields.append(QgsField('categories', QVariant.String))
        fields.append(QgsField('floor_id', QVariant.String))
        fields.append(QgsField('geometry_id', QVariant.String))
        fields.append(QgsField('anchor_count', QVariant.String))  # Changed to String to avoid type issues
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
        fields.append(QgsField('id', QVariant.String))
        fields.append(QgsField('data', QVariant.String))
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
            
            # Configure styling and labeling for location layers
            if 'Locations' in layer_info.get('name', ''):
                self._configure_location_layer_styling(layer)
                self._configure_location_labels(layer)
                # Additional refresh for locations after styling
                layer.triggerRepaint()
            elif 'Lines' in layer_info.get('name', ''):
                self._configure_line_layer_styling(layer)
                layer.triggerRepaint()
            elif 'Spaces' in layer_info.get('name', ''):
                self._configure_space_layer_styling(layer)
                layer.triggerRepaint()
            
            # Layer will be added to project by the calling method
            # (to handle proper grouping and ordering)
            
            return layer
            
        except Exception as e:
            return None


# Alias for backward compatibility
MVFParser = MVFv3Parser
