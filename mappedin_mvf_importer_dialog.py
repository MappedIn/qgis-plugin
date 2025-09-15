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
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox, QProgressDialog
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QSettings

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "mappedin_mvf_importer_dialog_base.ui")
)


class APIDownloadThread(QThread):
    """Thread for downloading MVF from API without blocking UI"""

    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str, str)  # success, message, file_path

    def __init__(self, api_key, api_secret, venue_id, api_client=None):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.venue_id = venue_id
        self.api_client = api_client

    def run(self):
        try:
            # Use the shared API client passed from the main dialog
            if self.api_client:
                # DEBUG: print(f"Using shared API client - {self.api_client.get_token_cache_status()}")
                client = self.api_client
            else:
                # Fallback: create new client if none provided
                from mappedin_mvf_importer.mappedin_api import MappedInAPIClient

                client = MappedInAPIClient()
                # DEBUG: print("Created fallback API client (no shared client provided)")

            def progress_callback(progress):
                self.progress.emit(int(progress))

            success, result, temp_file_path, metadata = client.fetch_mvf_package(
                self.api_key, self.api_secret, self.venue_id, progress_callback
            )

            if success:
                self.finished.emit(True, result, temp_file_path or "")
            else:
                self.finished.emit(False, result, temp_file_path or "")

        except Exception as e:
            self.finished.emit(False, f"Unexpected error: {str(e)}", "")


class FetchVenuesThread(QThread):
    """Thread for fetching venues list from API without blocking UI"""

    finished = pyqtSignal(bool, str, list)  # success, message, venues_list

    def __init__(self, api_key, api_secret, api_client=None):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_client = api_client

    def run(self):
        try:
            # Use the shared API client passed from the main dialog
            if self.api_client:
                # DEBUG: print(f"Using shared API client - {self.api_client.get_token_cache_status()}")
                client = self.api_client
            else:
                # Fallback: create new client if none provided
                from mappedin_mvf_importer.mappedin_api import MappedInAPIClient

                client = MappedInAPIClient()
                # DEBUG: print("Created fallback API client (no shared client provided)")

            # First authenticate
            auth_success, auth_error = client.authenticate(
                self.api_key, self.api_secret
            )
            if not auth_success:
                self.finished.emit(False, f"Authentication failed: {auth_error}", [])
                return

            # Then fetch venues
            venues_success, venues_result, venues_list = client.get_venues_list()

            if venues_success:
                self.finished.emit(
                    True, "Venues fetched successfully", venues_list or []
                )
            else:
                self.finished.emit(False, venues_result, [])

        except Exception as e:
            self.finished.emit(False, f"Unexpected error: {str(e)}", [])


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
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint
        )
        self.setModal(
            True
        )  # Make dialog modal to prevent getting lost behind main window

        # Connect UI elements
        self.browse_button.clicked.connect(self.browse_file)
        self.file_import_radio.toggled.connect(self.on_import_method_changed)
        self.api_import_radio.toggled.connect(self.on_import_method_changed)
        self.fetch_venues_button.clicked.connect(self.fetch_venues)

        # Connect API credential fields to enable fetch button
        self.api_key_edit.textChanged.connect(self.on_credentials_changed)
        self.api_secret_edit.textChanged.connect(self.on_credentials_changed)

        # Store the selected file path and API data
        self.selected_file = None
        self.temp_api_file = None
        self.download_thread = None
        self.fetch_venues_thread = None

        # Shared API client for token caching across calls
        self._api_client = None

        # Settings for persistent storage
        self.settings = QSettings("Mappedin", "MVF_Importer")

        # Load saved credentials
        self.load_saved_credentials()

        # Clear and setup venue dropdown with helpful placeholder
        self.venue_combo.clear()
        self.venue_combo.addItem("Click 'Fetch Venues' to load available venues", "")
        self.venue_combo.setCurrentIndex(0)

        # Initial UI state
        self.on_import_method_changed()

    def browse_file(self):
        """Open file dialog to select MVF package"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Mappedin MVF Package",
            "",
            "All Files (*);;MVF Files (*.mvf);;ZIP Files (*.zip)",
        )

        if file_path:
            self.selected_file = file_path
            self.file_path_edit.setText(file_path)

    def on_import_method_changed(self):
        """Handle import method radio button changes"""
        is_file_mode = self.file_import_radio.isChecked()

        # Enable/disable appropriate sections
        self.file_selection_group.setEnabled(is_file_mode)
        self.api_selection_group.setEnabled(not is_file_mode)

    def get_import_mode(self):
        """Return the selected import mode"""
        if self.file_import_radio.isChecked():
            return "file"
        else:
            return "api"

    def get_selected_file(self):
        """Return the selected file path"""
        if self.get_import_mode() == "file":
            return self.selected_file
        else:
            return self.temp_api_file

    def get_api_credentials(self):
        """Return API credentials"""
        # Get venue ID from combo box (either selected data or current text)
        venue_id = ""
        if self.venue_combo.currentData():
            venue_id = self.venue_combo.currentData()
        else:
            venue_id = self.venue_combo.currentData() or ""

        return {
            "api_key": self.api_key_edit.text().strip(),
            "api_secret": self.api_secret_edit.text().strip(),
            "venue_id": venue_id,
        }

    def get_osm_baselayer_enabled(self):
        """Return whether OSM base layer should be enabled"""
        return self.enable_osm_baselayer_check.isChecked()

    def validate_inputs(self):
        """Validate user inputs based on selected mode"""
        if self.get_import_mode() == "file":
            if not self.selected_file:
                QMessageBox.warning(
                    self, "Invalid Input", "Please select an MVF package file."
                )
                return False
        else:
            creds = self.get_api_credentials()
            if not creds["api_key"]:
                QMessageBox.warning(self, "Invalid Input", "Please enter your API key.")
                return False
            if not creds["api_secret"]:
                QMessageBox.warning(
                    self, "Invalid Input", "Please enter your API secret."
                )
                return False
            if not creds["venue_id"]:
                QMessageBox.warning(
                    self,
                    "No Venue Selected",
                    "Please first click 'Fetch Venues' to load available venues, then select one from the dropdown.",
                )
                return False
        return True

    def on_credentials_changed(self):
        """Called when API credentials are changed"""
        api_key = self.api_key_edit.text().strip()
        api_secret = self.api_secret_edit.text().strip()

        # Enable fetch button only if both credentials are entered
        has_credentials = bool(api_key and api_secret)
        self.fetch_venues_button.setEnabled(has_credentials)

    def fetch_venues(self):
        """Fetch available venues from the API"""
        api_key = self.api_key_edit.text().strip()
        api_secret = self.api_secret_edit.text().strip()

        if not api_key or not api_secret:
            QMessageBox.warning(
                self,
                "Missing Credentials",
                "Please enter both API key and secret before fetching venues.",
            )
            return

        # Disable fetch button during operation
        self.fetch_venues_button.setEnabled(False)
        self.fetch_venues_button.setText("Fetching venues...")

        # Start fetch venues thread
        # Ensure we have a shared API client
        if not self._api_client:
            from mappedin_mvf_importer.mappedin_api import MappedInAPIClient

            self._api_client = MappedInAPIClient()
            # DEBUG: print("Created shared API client for venues thread")

        self.fetch_venues_thread = FetchVenuesThread(
            api_key, api_secret, self._api_client
        )
        self.fetch_venues_thread.finished.connect(self.on_venues_fetched)
        self.fetch_venues_thread.start()

    def on_venues_fetched(self, success, message, venues_list):
        """Handle venues fetch completion"""
        # Re-enable and reset fetch button
        self.fetch_venues_button.setEnabled(True)
        self.fetch_venues_button.setText("Fetch Available Venues")

        if success:
            self.populate_venues_combo(venues_list)
            if venues_list:
                QMessageBox.information(
                    self,
                    "Venues Loaded",
                    f"Successfully loaded {len(venues_list)} venue(s).",
                )
            else:
                QMessageBox.information(
                    self,
                    "No Venues",
                    "No venues found for your account. You can still enter a venue ID manually.",
                )
        else:
            QMessageBox.warning(
                self, "Fetch Failed", f"Failed to fetch venues:\n\n{message}"
            )

    def populate_venues_combo(self, venues_list):
        """Populate the venues combo box with fetched venues"""
        # Save current text if any
        current_text = self.venue_combo.currentText()
        current_venue_id = self.venue_combo.currentData()

        # Clear existing items (including placeholder)
        self.venue_combo.clear()

        if not venues_list:
            # Add a helpful message if no venues are returned
            self.venue_combo.addItem("No venues available for this account", "")
            return

        # Add venues to combo box
        for venue in venues_list:
            # Try different possible keys for venue name and ID
            venue_name = venue.get(
                "name", venue.get("title", venue.get("displayName", "Unknown Venue"))
            )
            venue_id = venue.get("id", venue.get("venueId", venue.get("mapId", "")))

            if venue_id:
                display_text = f"{venue_name} ({venue_id})"
                self.venue_combo.addItem(display_text, venue_id)

        # Restore previous selection if it was there
        if current_venue_id:
            # Find by venue ID (stored as data)
            for i in range(self.venue_combo.count()):
                if self.venue_combo.itemData(i) == current_venue_id:
                    self.venue_combo.setCurrentIndex(i)
                    break
        elif current_text:
            # Fallback: find by text
            index = self.venue_combo.findText(current_text)
            if index >= 0:
                self.venue_combo.setCurrentIndex(index)

    def fetch_from_api(self):
        """Fetch MVF package from API"""
        creds = self.get_api_credentials()

        # Show progress dialog
        self.progress_dialog = QProgressDialog(
            "Downloading MVF package...", "Cancel", 0, 100, self
        )
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.show()

        # Ensure we have a shared API client
        if not self._api_client:
            from mappedin_mvf_importer.mappedin_api import MappedInAPIClient

            self._api_client = MappedInAPIClient()
            # DEBUG: print("Created shared API client for download thread")

        # Start download thread
        self.download_thread = APIDownloadThread(
            creds["api_key"], creds["api_secret"], creds["venue_id"], self._api_client
        )

        # Connect signals
        self.download_thread.progress.connect(self.progress_dialog.setValue)
        self.download_thread.finished.connect(self.on_api_download_finished)
        self.progress_dialog.canceled.connect(self.cancel_download)

        # Start download
        self.download_thread.start()

    def cancel_download(self):
        """Cancel the API download"""
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.terminate()
            self.download_thread.wait()
        self.progress_dialog.close()

    def on_api_download_finished(self, success, message, file_path):
        """Handle API download completion"""
        self.progress_dialog.close()

        if success:
            self.temp_api_file = file_path
            # Save credentials after successful authentication
            self.save_credentials()
            super().accept()  # Close dialog and proceed with import (bypass override)
        else:
            QMessageBox.critical(
                self,
                "API Download Failed",
                f"Failed to download MVF package:\n\n{message}",
            )

    def accept(self):
        """Override accept to validate inputs first"""
        if self.get_import_mode() == "api":
            if self.validate_inputs():
                self.fetch_from_api()
        else:
            if self.validate_inputs():
                super().accept()

    def load_saved_credentials(self):
        """Load saved API credentials from settings"""
        try:
            # Load saved API key and secret
            saved_api_key = self.settings.value("api_key", "", type=str)
            saved_api_secret = self.settings.value("api_secret", "", type=str)
            saved_venue_id = self.settings.value("last_venue_id", "", type=str)

            # Populate the fields if we have saved values
            if saved_api_key:
                self.api_key_edit.setText(saved_api_key)
            if saved_api_secret:
                self.api_secret_edit.setText(saved_api_secret)
            if saved_venue_id:
                self.venue_combo.setCurrentText(saved_venue_id)

        except Exception:
            # If there's any issue loading settings, just continue with empty fields
            pass

    def save_credentials(self):
        """Save API credentials to settings"""
        try:
            # Get current values
            api_key = self.api_key_edit.text().strip()
            api_secret = self.api_secret_edit.text().strip()
            venue_id = self.venue_combo.currentData() or ""

            # Only save non-empty values
            if api_key:
                self.settings.setValue("api_key", api_key)
            if api_secret:
                self.settings.setValue("api_secret", api_secret)
            if venue_id:
                self.settings.setValue("last_venue_id", venue_id)

            # Ensure settings are written to storage
            self.settings.sync()

        except Exception:
            # If there's any issue saving settings, just continue
            pass

    def clear_selection(self):
        """Clear the selected file path and reset the UI (but keep API credentials)"""
        self.selected_file = None
        self.temp_api_file = None
        self.file_path_edit.clear()
        # Note: We don't clear API credentials anymore - they persist between uses

    def clear_saved_credentials(self):
        """Clear saved API credentials from settings and UI"""
        try:
            self.settings.remove("api_key")
            self.settings.remove("api_secret")
            self.settings.remove("last_venue_id")
            self.settings.sync()

            # Also clear the UI fields
            self.api_key_edit.clear()
            self.api_secret_edit.clear()
            self.venue_combo.clear()
        except Exception:
            pass

    def cleanup_temp_files(self):
        """Clean up temporary files"""
        if self.temp_api_file:
            try:
                import os

                if os.path.exists(self.temp_api_file):
                    os.unlink(self.temp_api_file)
            except Exception:
                pass
            self.temp_api_file = None

    def closeEvent(self, event):
        """Handle dialog close event"""
        # Save any changes to credentials before closing
        if self.get_import_mode() == "api":
            self.save_credentials()
        self.cleanup_temp_files()
        super().closeEvent(event)
