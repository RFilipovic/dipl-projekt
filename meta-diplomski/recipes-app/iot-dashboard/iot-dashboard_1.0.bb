SUMMARY = "IoT Dashboard Web UI"
DESCRIPTION = "Lightweight web dashboard for IoT device monitoring and control"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://iot-dashboard.py \
           file://iot-dashboard.service"

S = "${WORKDIR}"

RDEPENDS:${PN} = "python3 python3-flask python3-paho-mqtt python3-sqlite3"

inherit systemd

SYSTEMD_SERVICE:${PN} = "iot-dashboard.service"
SYSTEMD_AUTO_ENABLE = "enable"

do_install() {
    # Install Python script
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/iot-dashboard.py ${D}${bindir}/iot-dashboard.py

    # Install systemd service
    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/iot-dashboard.service ${D}${systemd_unitdir}/system/
}

FILES:${PN} += "${bindir}/iot-dashboard.py \
                ${systemd_unitdir}/system/iot-dashboard.service"
