SUMMARY = "Data Collector Service for IoT Edge Node"
DESCRIPTION = "Installs and enables the Python script for MQTT data collection and SQLite storage."
LICENSE = "CLOSED"
#PV = "1.0" 

# Definira izvorne datoteke (uzima ih iz poddirektorija 'files/')
SRC_URI = " \
    file://data_collector.py \
    file://data-collector.service \
    file://command_sender.py \
"

# Yocto varijabla koja govori systemd-u da automatski omogući servis pri bootanju
SYSTEMD_SERVICE:${PN} = "data-collector.service"

# Ovisnosti: osigurava da su ključni paketi prisutni prije instalacije ovog servisa
RDEPENDS:${PN} += "python3-paho-mqtt python3-sqlite3 mosquitto"

# File: data-collector_1.0.bb

# Inherit systemd rješava pakiranje servisne datoteke
inherit systemd

# Explicitno definirajte SVE datoteke koje nisu u standardnim putanjama (poput /usr/local/)
FILES:${PN} = " \
    /usr/local/bin/data_collector.py \
    /usr/local/bin/command_sender.py \
    /usr/local/bin/ \
    /usr/local/ \
    ${systemd_system_unitdir}/data-collector.service \
"

do_install() {
    # 1. Instaliraj Python skripte:
    install -d ${D}/usr/local/bin/
    install -m 0755 ${WORKDIR}/data_collector.py ${D}/usr/local/bin/data_collector.py
    install -m 0755 ${WORKDIR}/command_sender.py ${D}/usr/local/bin/command_sender.py
    
    # 2. Instaliraj systemd servisnu datoteku:
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/data-collector.service ${D}${systemd_system_unitdir}
}