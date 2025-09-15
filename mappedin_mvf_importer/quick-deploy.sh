#!/bin/bash

# Quick deployment script for Mappedin MVF Importer plugin development
# This script deploys your changes to QGIS and reminds you to restart

echo "🚀 Quick Deploy: Mappedin MVF Importer"
echo "======================================"

# Change to the plugin directory (in case script is run from elsewhere)
cd "$(dirname "$0")"

# Run the development deployment
make dev-deploy

echo ""
echo "✅ Plugin deployed successfully!"
echo ""
echo "📋 Next steps:"
echo "   1. Close QGIS if it's running"
echo "   2. Restart QGIS"
echo "   3. Go to Vector → Mappedin MVF Importer to test your changes"
echo ""
echo "💡 Tip: Run this script anytime you make changes to test them quickly!"
