"""
/***************************************************************************
 Mappedin MVF Importer Dialog
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

import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtWidgets import QFileDialog
from qgis.PyQt.QtCore import Qt

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'mappedin_mvf_importer_dialog_base.ui'))


class MappedInMVFImporterDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(MappedInMVFImporterDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html#widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        
        # Set window flags for better dialog behavior
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)
        self.setModal(True)  # Make dialog modal to prevent getting lost behind main window
        
        # Connect the browse button to file selection
        self.browse_button.clicked.connect(self.browse_file)
        
        # Store the selected file path
        self.selected_file = None

    def browse_file(self):
        """Open file dialog to select MVF package"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Mappedin MVF Package",
            "",
            "All Files (*);;MVF Files (*.mvf);;ZIP Files (*.zip)"
        )
        
        if file_path:
            self.selected_file = file_path
            self.file_path_edit.setText(file_path)

    def get_selected_file(self):
        """Return the selected file path"""
        return self.selected_file
    
    def get_osm_baselayer_enabled(self):
        """Return whether OSM base layer should be enabled"""
        return self.enable_osm_baselayer_check.isChecked()
    
    def clear_selection(self):
        """Clear the selected file path and reset the UI"""
        self.selected_file = None
        self.file_path_edit.clear()  # Clear the text field
