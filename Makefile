#/***************************************************************************
# MappedInMVFImporter
# 
# A QGIS plugin for importing Mappedin MVF (Map Venue Format) packages
#                             -------------------
#        begin                : 2024-01-01
#        copyright            : (C) 2024 by Mappedin
#        email                : support@mappedin.com
# ***************************************************************************/
# 
#/***************************************************************************
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU General Public License as published by  *
# *   the Free Software Foundation; either version 2 of the License, or     *
# *   (at your option) any later version.                                   *
# *                                                                         *
# ***************************************************************************/

#################################################
# Edit the following to match your sources lists
#################################################

# Translation
SOURCES = \
	__init__.py \
	mappedin_mvf_importer.py \
	mappedin_mvf_importer_dialog.py \
	mappedin_api.py \
	mvf_parser_v3.py

PLUGINNAME = mappedin_mvf_importer

PY_FILES = \
	__init__.py \
	mappedin_mvf_importer.py \
	mappedin_mvf_importer_dialog.py \
	mappedin_api.py \
	mvf_parser_v3.py

UI_FILES = mappedin_mvf_importer_dialog_base.ui

EXTRAS = metadata.txt logowhite.png LICENSE README.md

COMPILED_RESOURCE_FILES = resources.py

PEP8EXCLUDE=pydev,resources.py,conf.py,third_party,ui

#################################################
# Normally you would not need to edit below here
#################################################

# QGIS 3 plugin directory (adjust if your QGIS profile location is different)
QGISDIR=Library/Application\ Support/QGIS/QGIS3/profiles/default

HELP = help/build/html

PLUGIN_UPLOAD = $(c)/plugin_upload.py

RESOURCE_SRC=$(shell grep '^ *<file' resources.qrc | sed 's@</file>@@g;s/.*>//g' | tr '\n' ' ')

.PHONY: default
default: compile

compile: $(COMPILED_RESOURCE_FILES)

%.py : %.qrc $(RESOURCES_SRC)
	pyrcc5 -o $*.py  $<

%.qm : %.ts
	lrelease $<

test: compile transcompile
	@echo
	@echo "----------------------"
	@echo "Regression Test Suite"
	@echo "----------------------"

	@# Preceding dash means that make will continue in case of errors
	@-export PYTHONPATH=`pwd`:$(PYTHONPATH); \
		export QGIS_DEBUG=0; \
		export QGIS_LOG_FILE=/tmp/qgis.log; \
		nosetests -v --with-id --with-coverage --cover-package=. \
		3>&1 1>&2 2>&3 3>&- || true

pep8:
	@echo
	@echo "-----------"
	@echo "PEP8 issues"
	@echo "-----------"
	@pep8 --repeat --ignore=E203,E121,E122,E123,E124,E125,E126,E127,E128 --exclude $(PEP8EXCLUDE) . || true
	@echo "-----------"
	@echo "Ignored in PEP8 check:"
	@echo $(PEP8EXCLUDE)

autopep8:
	@echo
	@echo "-------------------"
	@echo "Applying autopep8"
	@echo "-------------------"
	@autopep8 --in-place --aggressive --aggressive --line-length=79 --exclude=$(PEP8EXCLUDE) .

pylint:
	@echo
	@echo "-----------------"
	@echo "Pylint violations"
	@echo "-----------------"
	@pylint --reports=n --rcfile=pylintrc . || true
	@echo
	@echo "----------------------"
	@echo "If you get a 'no module named qgis.core' error, try setting up the"
	@echo "PYTHONPATH to include the /usr/share/qgis/python directory."
	@echo "----------------------"

clean:
	@echo
	@echo "------------------------------------"
	@echo "Removing uic and rcc generated files"
	@echo "------------------------------------"
	$(RM) $(COMPILED_RESOURCE_FILES) $(COMPILED_UI_FILES) $(COMPILED_FORM_FILES)

deploy: compile
	@echo
	@echo "------------------------------------------"
	@echo "Deploying plugin to your QGIS 3 directory."
	@echo "------------------------------------------"
	@echo "Target: $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)"
	# The deploy target works on unix like operating systems where
	# the Python plugin directory is located at:
	# $HOME/$(QGISDIR)/python/plugins
	mkdir -p $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)
	cp -vf $(PY_FILES) $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)/
	cp -vf $(UI_FILES) $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)/
	cp -vf $(COMPILED_RESOURCE_FILES) $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)/
	cp -vf $(EXTRAS) $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)/
	@if [ -d "i18n" ]; then cp -vfr i18n $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)/; fi
	@if [ -d "$(HELP)" ]; then cp -vfr $(HELP) $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)/help; fi
	@echo "Plugin deployed successfully!"
	@echo "Restart QGIS to see your changes."

dev-deploy: compile
	@echo
	@echo "---------------------------------------"
	@echo "Quick development deployment to QGIS 3"
	@echo "---------------------------------------"
	mkdir -p $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)
	cp -f $(PY_FILES) $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)/
	cp -f $(UI_FILES) $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)/
	cp -f $(COMPILED_RESOURCE_FILES) $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)/
	cp -f $(EXTRAS) $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)/
	@echo "Development files deployed. Restart QGIS to test."

# The dclean target removes compiled python files from plugin directory
# also deletes any .git entry
dclean:
	@echo
	@echo "-----------------------------------"
	@echo "Removing any compiled python files."
	@echo "-----------------------------------"
	find $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME) -iname "*.pyc" -delete
	find $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME) -iname ".git" -prune -exec rm -Rf {} \;

derase:
	@echo
	@echo "-------------------------"
	@echo "Removing deployed plugin."
	@echo "-------------------------"
	rm -Rf $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)

zip: deploy dclean
	@echo
	@echo "---------------------------"
	@echo "Creating plugin zip bundle."
	@echo "---------------------------"
	# The zip target deploys the plugin and creates a zip file with the deployed
	# content. You can then upload the zip file on http://plugins.qgis.org
	rm -f $(PLUGINNAME).zip
	cd $(HOME)/$(QGISDIR)/python/plugins; zip -9r $(CURDIR)/$(PLUGINNAME).zip $(PLUGINNAME)

package: compile
	# Create a zip package of the plugin for distribution.
	# This packages the plugin with all the required files.
	@echo
	@echo "------------------------------------"
	@echo "Exporting plugin to zip package."
	@echo "------------------------------------"
	rm -f $(PLUGINNAME).zip
	git archive --prefix=$(PLUGINNAME)/ -o $(PLUGINNAME).zip HEAD
	echo "Created package: $(PLUGINNAME).zip"

upload: zip
	@echo
	@echo "-------------------------------------"
	@echo "Uploading plugin to QGIS Plugin repo."
	@echo "-------------------------------------"
	$(PLUGIN_UPLOAD) $(PLUGINNAME).zip

transup:
	@echo
	@echo "------------------------------------------------"
	@echo "Updating translation files with any new strings."
	@echo "------------------------------------------------"
	@chmod +x scripts/update-strings.sh
	@scripts/update-strings.sh $(LOCALES)

transcompile:
	@echo
	@echo "----------------------------------------"
	@echo "Compiled translation files to .qm files."
	@echo "----------------------------------------"
	@chmod +x scripts/compile-strings.sh
	@scripts/compile-strings.sh

transclean:
	@echo
	@echo "------------------------------------"
	@echo "Removing compiled translation files."
	@echo "------------------------------------"
	rm -f i18n/*.qm

doc:
	@echo
	@echo "------------------------------------"
	@echo "Building documentation using sphinx."
	@echo "------------------------------------"
	cd help; make html
