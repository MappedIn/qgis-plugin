"""
/***************************************************************************
 Mappedin MVF Importer
                                 A QGIS plugin
 A QGIS plugin for importing Mappedin MVF (Map Venue Format) packages
                              -------------------
        begin                : 2024-01-01
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Mappedin
        email                : support@mappedin.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QUrl
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox
from qgis.core import QgsProject, QgsLayerTreeGroup, QgsLayerTreeLayer, QgsRasterLayer, QgsDataSourceUri

# Initialize Qt resources from file resources.py
from mappedin_mvf_importer.resources import *
# Import the code for the dialog
from mappedin_mvf_importer.mappedin_mvf_importer_dialog import MappedInMVFImporterDialog
from mappedin_mvf_importer.mvf_parser_v3 import MVFv3Parser
import os.path


class MappedInMVFImporter:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'MappedInMVFImporter_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Mappedin MVF Importer')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('MappedInMVFImporter', message)


    def _get_plugin_icon(self) -> QIcon:
        """Return the plugin icon, trying Qt resource first, then filesystem fallback."""
        resource_path = ':/plugins/mappedin_mvf_importer/logowhite.png'
        icon = QIcon()
        # Load pixmap from resource
        pix = QPixmap(resource_path)
        if not pix.isNull():
            icon.addPixmap(pix, QIcon.Normal, QIcon.Off)
            icon.addPixmap(pix, QIcon.Active, QIcon.Off)
            icon.addPixmap(pix, QIcon.Disabled, QIcon.Off)
            return icon
        # Fallback to filesystem
        fs_icon_path = os.path.join(self.plugin_dir, 'logowhite.png')
        pix = QPixmap(fs_icon_path)
        if not pix.isNull():
            icon.addPixmap(pix, QIcon.Normal, QIcon.Off)
            icon.addPixmap(pix, QIcon.Active, QIcon.Off)
            icon.addPixmap(pix, QIcon.Disabled, QIcon.Off)
        return icon

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        # Load icon robustly using resource with filesystem fallback
        icon = self._get_plugin_icon()
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar and ensures icon shows on the button
            self.iface.addToolBarIcon(action)
            try:
                toolbar = self.iface.mainWindow().findChild(type(self.iface.addToolBarIcon(action).__class__), None)
            except Exception:
                toolbar = None

        if add_to_menu:
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/mappedin_mvf_importer/logowhite.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Import Mappedin MVF Package'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.tr(u'&Mappedin MVF Importer'),
                action)
            self.iface.removeToolBarIcon(action)
        


    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = MappedInMVFImporterDialog()

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            self.import_mvf_package()

    def import_mvf_package(self):
        """Import the selected MVF package"""
        # Get the selected file path and options from the dialog
        file_path = self.dlg.get_selected_file()
        enable_osm_baselayer = self.dlg.get_osm_baselayer_enabled()
        
        if not file_path:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Warning",
                "Please select an MVF package file."
            )
            return
        
        try:
            # Parse the MVF package
            parser = MVFv3Parser()
            layers_data = parser.parse_mvf_package(file_path)
            
            # Organize layers for proper grouping first
            self._organize_and_add_layers(parser, layers_data)
            
            # Add OSM base layer LAST and force to absolute bottom
            if enable_osm_baselayer:
                self._add_osm_baselayer()
                # Extra safety: ensure any OSM layers are positioned at absolute bottom
                self._ensure_osm_at_bottom()
                    
            QMessageBox.information(
                self.iface.mainWindow(),
                "Success",
                f"Successfully imported MVF package with {len(layers_data)} layer(s)."
            )
            
        except Exception as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error",
                f"Failed to import MVF package: {str(e)}"
            )
    
    def _organize_and_add_layers(self, parser, layers_data):
        """Organize layers into floor groups with proper ordering"""
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        
        # Separate layers by type and floor
        floor_layers = {}
        boundary_layers = []
        
        for layer_info in layers_data:
            layer_name = layer_info.get('name', '')
            
            if 'Floor Boundaries' in layer_name or 'Boundary' in layer_name:
                boundary_layers.append(layer_info)
            else:
                # Extract floor/level info from layer name
                if 'Level 1' in layer_name:
                    floor_key = 'Level 1'
                elif 'Level 2' in layer_name:
                    floor_key = 'Level 2'
                else:
                    # Handle other floors dynamically
                    parts = layer_name.split(' - ')
                    if len(parts) >= 2:
                        floor_key = parts[0]
                    else:
                        floor_key = 'Other'
                
                if floor_key not in floor_layers:
                    floor_layers[floor_key] = {
                        'locations': [],
                        'points': [],
                        'lines': [],
                        'spaces': []
                    }
                
                # Categorize layer by type
                if 'Locations' in layer_name:
                    floor_layers[floor_key]['locations'].append(layer_info)
                elif 'Connections' in layer_name:
                    floor_layers[floor_key]['points'].append(layer_info)
                elif 'Lines' in layer_name:
                    floor_layers[floor_key]['lines'].append(layer_info)
                elif 'Spaces' in layer_name:
                    floor_layers[floor_key]['spaces'].append(layer_info)
        
        # Add boundary layers FIRST so they appear at the bottom of the tree and render behind everything
        for layer_info in boundary_layers:
            layer = parser.create_qgis_layer(layer_info)
            if layer and layer.isValid():
                # Add normally to project - this will put it at the bottom since it's first
                project.addMapLayer(layer)
                # Hide floor boundary by default
                layer_node = root.findLayer(layer.id())
                if layer_node:
                    layer_node.setItemVisibilityChecked(False)
        
        # Create floor groups in descending order (Level 2, Level 1, etc.) AFTER boundaries
        floor_keys = sorted(floor_layers.keys(), reverse=True)
        
        for floor_key in floor_keys:
            floor_data = floor_layers[floor_key]
            
            # Create floor group
            group = root.addGroup(f"{floor_key} Group")
            
            # Add layers in specific order: Locations, Connections, Lines, Spaces
            layer_order = [
                ('locations', floor_data['locations']),
                ('connections', floor_data['points']),
                ('lines', floor_data['lines']),
                ('spaces', floor_data['spaces'])
            ]
            
            for layer_type, layer_infos in layer_order:
                for layer_info in layer_infos:
                    layer = parser.create_qgis_layer(layer_info)
                    if layer and layer.isValid():
                        # Add layer to project first (required for grouping)
                        project.addMapLayer(layer, addToLegend=False)
                        # Then add to group
                        group.addLayer(layer)
        
        # Set canvas extent and refresh
        if layers_data:
            self.iface.mapCanvas().zoomToFullExtent()
            self.iface.mapCanvas().refresh()
    
    def _add_osm_baselayer(self):
        """Add OpenStreetMap XYZ tile layer as base layer"""
        try:
            # OpenStreetMap XYZ tile service URL - correct format for QGIS
            osm_url = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0&crs=EPSG3857"
            
            # Create the raster layer with correct provider
            osm_layer = QgsRasterLayer(osm_url, "OpenStreetMap", "wms")
            
            # Silent: no console logging in production
            
            if osm_layer.isValid():
                # Add to project but place at absolute bottom of the layer tree
                project = QgsProject.instance()
                # Set visible attribution for OSM tile usage policy
                try:
                    osm_layer.serverProperties().setAttribution("© OpenStreetMap contributors")
                    osm_layer.setAttributionUrl(QUrl("https://www.openstreetmap.org/copyright"))
                except Exception:
                    pass
                # Avoid auto-adding to legend so we can control position
                project.addMapLayer(osm_layer, addToLegend=False)
                root = project.layerTreeRoot()
                # Place at end (visual bottom in the Layers panel)
                root.insertLayer(len(root.children()), osm_layer)
                # added successfully
                
            else:
                # failed to create primary OSM layer
                
                # Try alternative method using QgsDataSourceUri
                uri = QgsDataSourceUri()
                uri.setParam('type', 'xyz')
                uri.setParam('url', 'https://tile.openstreetmap.org/{z}/{x}/{y}.png')
                uri.setParam('zmax', '19')
                uri.setParam('zmin', '0')
                
                osm_layer_alt = QgsRasterLayer(uri.encodedUri().data().decode(), "OpenStreetMap", "wms")
                # Silent
                
                if osm_layer_alt.isValid():
                    project = QgsProject.instance()
                    try:
                        osm_layer_alt.serverProperties().setAttribution("© OpenStreetMap contributors")
                        osm_layer_alt.setAttributionUrl(QUrl("https://www.openstreetmap.org/copyright"))
                    except Exception:
                        pass
                    project.addMapLayer(osm_layer_alt, addToLegend=False)
                    root = project.layerTreeRoot()
                    root.insertLayer(len(root.children()), osm_layer_alt)
                    # added via alternative path
                    
                else:
                    pass
                    
        except Exception as e:
            pass

    

    def _ensure_osm_at_bottom(self):
        """Move any OpenStreetMap XYZ layers to the absolute bottom of the layer tree."""
        try:
            project = QgsProject.instance()
            root = project.layerTreeRoot()
            moved = 0
            for layer in project.mapLayers().values():
                if not layer:
                    continue
                name_matches = layer.name() == "OpenStreetMap"
                source = getattr(layer, 'source', None)
                source_matches = False
                if callable(source):
                    try:
                        source_matches = 'tile.openstreetmap.org' in layer.source()
                    except Exception:
                        source_matches = False
                if not (name_matches or source_matches):
                    continue
                node = root.findLayer(layer.id())
                if node is None:
                    # Not in tree yet; add at bottom
                    root.insertLayer(len(root.children()), layer)
                    moved += 1
                    continue
                # Node exists; if not already last or not at root, move via clone to avoid deletion issues
                is_at_root = node.parent() == root
                is_last = root.children() and (root.children()[-1] is node)
                if (not is_at_root) or (not is_last):
                    node_clone = node.clone()
                    root.insertChildNode(len(root.children()), node_clone)
                    node.parent().removeChildNode(node)
                    moved += 1
            # no-op logging
        except Exception as e:
            pass
