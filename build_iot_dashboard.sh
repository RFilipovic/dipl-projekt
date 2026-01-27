#!/bin/bash
# Build IoT image sa dashboardom

echo "╔════════════════════════════════════════════╗"
echo "║    Building IoT Dashboard Image           ║"
echo "╚════════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"
source oe-init-build-env

echo "🧹 Cleaning previous iot-dashboard build..."
bitbake -c cleansstate iot-dashboard

echo ""
echo "🏗️  Building diplomski-image with IoT Dashboard..."
echo ""

bitbake diplomski-image

if [ $? -eq 0 ]; then
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo "║          ✅ BUILD SUCCESSFUL               ║"
    echo "╚════════════════════════════════════════════╝"
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Run: ./run_dashboard.sh"
    echo "   2. Wait for boot (30-60s)"
    echo "   3. Open: http://localhost:8080"
    echo ""
else
    echo ""
    echo "❌ Build failed. Check logs above."
    exit 1
fi
