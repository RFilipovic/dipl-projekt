SUMMARY = "IoT Edge Image za Diplomski"
LICENSE = "MIT"

inherit core-image

# Enable systemd
DISTRO_FEATURES:append = " systemd"
VIRTUAL-RUNTIME_init_manager = "systemd"
VIRTUAL-RUNTIME_initscripts = "systemd-compat-units"

IMAGE_INSTALL:append = " \
    packagegroup-core-boot \
    openssh \
    vim \
    curl \
    mosquitto \
    mosquitto-clients \
    python3 \
    python3-paho-mqtt \
    python3-pip \
    python3-sqlite3 \
    sqlite3 \
    tzdata \
    systemd \
    systemd-analyze \
    data-collector \
    "

IMAGE_ROOTFS_SIZE ?= "2097152"
