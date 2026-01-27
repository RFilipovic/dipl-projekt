# 🌐 IoT Dashboard - Web GUI

Minimalistički web GUI za monitoring i kontrolu IoT senzora. Pokreće se na IoT uređaju (QEMU) i dostupan je preko browsera.

## 🎯 Značajke

- ✅ Real-time prikaz senzora sa vrijednostima
- ✅ Kontrolni panel sa gumbima (Start/Stop/Measure)
- ✅ Tablični prikaz zadnjih očitanja
- ✅ Minimalistički dizajn (bez frameworka, samo CSS)
- ✅ Auto-refresh svake 2 sekunde
- ✅ Port forwarding na localhost:8080

## 🚀 Brzi Start

### 1. Build Image (prvi put ili nakon promjena)

```bash
./build_iot_dashboard.sh
```

**Trajanje:** 5-15 minuta (ili duže prvi put)

### 2. Pokreni QEMU

```bash
./run_dashboard.sh
```

**Portovi:**
- `8080` → Web Dashboard
- `18830` → MQTT Broker  
- `2222` → SSH

### 3. Pričekaj boot

Pričekaj 30-60 sekundi da se sistem bootuje i servisi pokrenu.

### 4. Otvori Dashboard

```bash
firefox http://localhost:8080
```

ili

```bash
google-chrome http://localhost:8080
```

## 📊 Korištenje Dashboarda

### Kontrolni Panel

**Odabir senzora:**
- `All Sensors` - šalje komandu svim senzorima
- Ili odaberi specifičan sensor ID

**Parametri:**
- **Count** - broj očitanja (default: 10)
- **Interval** - razmak između očitanja u sekundama (default: 1)

**Gumbi:**
- **📊 Measure** - zatraži točno `count` očitanja sa `interval` razmakom
- **▶ Start** - pokreni kontinuirano slanje podataka
- **⏹ Stop** - zaustavi slanje podataka

### Primjer: Zatražiti 20 očitanja svake 0.5 sekundi

1. Odaberi sensor (npr. `temp1`)
2. Postavi `Count: 20`
3. Postavi `Interval: 0.5`
4. Klikni **📊 Measure**

## 🔧 Testiranje sa Senzorima

### Terminal 1: Pokreni QEMU
```bash
./run_dashboard.sh
```

### Terminal 2: Pokreni senzor simulator

```bash
cd /home/rene/Documents/projekt-dipl/dipl-projekt
source .venv/bin/activate  # ako imaš venv

# Pokreni senzor u listen modu
python3 sensor_simulator.py \
  --ssh-tunnel \
  --sensor temperature \
  --sensor-id temp1 \
  --listen
```

### Terminal 3 (optional): Drugi senzor

```bash
python3 sensor_simulator.py \
  --ssh-tunnel \
  --sensor humidity \
  --sensor-id humid1 \
  --listen
```

### Browser: Kontrola preko GUI

Otvori http://localhost:8080 i kontroliraj senzore preko gumbi!

## 🏗️ Arhitektura

```
┌─────────────────────────────────────────┐
│         Browser (localhost:8080)        │
│  [Sensor Cards] [Control Panel] [Table] │
└──────────────┬──────────────────────────┘
               │ HTTP (port forwarding)
               ▼
┌─────────────────────────────────────────┐
│         QEMU IoT Device                 │
│  ┌──────────────────────────────────┐   │
│  │  iot-dashboard.py (Flask :8080)  │   │
│  │  - /api/sensors (GET)            │   │
│  │  - /api/readings (GET)           │   │
│  │  - /api/command/<id> (POST)      │   │
│  └────────┬─────────────────────────┘   │
│           │ MQTT                         │
│  ┌────────▼─────────┐  ┌──────────────┐ │
│  │ Mosquitto :1883  │  │  SQLite DB   │ │
│  └──────────────────┘  └──────────────┘ │
│           ▲                              │
│  ┌────────┴─────────┐                   │
│  │  data-collector  │                   │
│  └──────────────────┘                   │
└──────────────┬──────────────────────────┘
               │ MQTT (port 18830 forwarding)
               ▼
┌─────────────────────────────────────────┐
│    Host: sensor_simulator.py (listen)   │
│    - Receives commands via MQTT         │
│    - Sends sensor data back             │
└─────────────────────────────────────────┘
```

## 🐛 Troubleshooting

### Dashboard ne učitava u browseru

```bash
# Provjeri unutar QEMU-a (SSH)
ssh -p 2222 root@localhost

# Provjeri servis
systemctl status iot-dashboard

# Ako nije aktivan
systemctl start iot-dashboard

# Provjeri logove
journalctl -u iot-dashboard -f
```

### Port 8080 zauzet

```bash
# Provjeri što koristi port
sudo lsof -i :8080

# Zaustavi proces ili promijeni port u run_dashboard.sh
```

### Nema senzora u dashboardu

Dashboard prikazuje senzore iz baze podataka. Trebaju postojati senzori koji su slali podatke.

**Brzi test:**
```bash
# Pokreni senzor (drugi terminal)
python3 sensor_simulator.py --ssh-tunnel --sensor temperature --value 25.5
```

Nakon 2-3 sekunde, senzor bi se trebao pojaviti u dashboardu.

## 📝 Tehnički Detalji

**Backend:** Python 3 + Flask  
**Frontend:** Pure HTML/CSS/JavaScript (bez frameworka)  
**Database:** SQLite3  
**MQTT:** Mosquitto + paho-mqtt  
**Systemd:** Auto-start na boot

**Fajlovi u image-u:**
- `/usr/bin/iot-dashboard.py` - Flask web server
- `/usr/local/bin/iot_data.db` - SQLite baza
- `/etc/systemd/system/iot-dashboard.service` - systemd servis

## 🎨 Dizajn

Minimalistički gradient dizajn (ljubičasto-plavi) sa:
- Card-based layout
- Responsive grid za senzore
- Real-time auto-refresh
- Console-style log output
- Gumbi sa hover efektima

Nema vanjskih dependencija - sve inline CSS i vanilla JS!
