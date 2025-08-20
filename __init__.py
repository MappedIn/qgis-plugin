"""
/***************************************************************************
 Mappedin MVF Importer
                                 A QGIS plugin
 A QGIS plugin for importing Mappedin MVF (Map Venue Format) packages
                             -------------------
        begin                : 2024-01-01
        copyright            : (C) 2024 by Mappedin
        email                : support@mappedin.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load MappedInMVFImporter class from file mappedin_mvf_importer.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from mappedin_mvf_importer.mappedin_mvf_importer import MappedInMVFImporter
    return MappedInMVFImporter(iface)
