#!/bin/bash
# Pokreće QEMU sa IoT dashboardom i potrebnim portovima

echo "╔════════════════════════════════════════════╗"
echo "║    IoT Dashboard - QEMU Launcher          ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "🌐 Port forwarding:"
echo "   • http://localhost:8080  → IoT Dashboard"
echo "   • localhost:18830        → MQTT Broker"
echo "   • localhost:2222         → SSH"
echo ""

cd "$(dirname "$0")"
source oe-init-build-env

runqemu qemux86-64 nographic kvm slirp \
  qemuparams="-net nic,model=e1000 -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::18830-:1883,hostfwd=tcp::8080-:8080"
