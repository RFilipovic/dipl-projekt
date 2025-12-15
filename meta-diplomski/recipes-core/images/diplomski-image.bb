SUMMARY = "IoT Edge Image za Diplomski"
LICENSE = "MIT"

inherit core-image

IMAGE_INSTALL:append = " \
    packagegroup-core-boot \
    openssh \
    htop \
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
    data-collector \
    "

IMAGE_ROOTFS_SIZE ?= "2097152"
