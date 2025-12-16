import paho.mqtt.client as mqtt
import sqlite3
import json
import time
import os
import sys

# --- Konfiguracija logiranja ---
# Osigurava da se poruke odmah ispisu (za systemd journalctl)
sys.stdout.flush()
sys.stderr.flush()

# --- Konfiguracija Edge Nodea ---
# Mosquitto Broker radi na istoj QEMU mašini (localhost)
BROKER_ADDRESS = "localhost"
BROKER_PORT = 1883
TOPIC_SUBSCRIPTION = "sensors/#" # Pretplata na sve teme koje počinju s 'sensors/'

# --- Konfiguracija Baze Podataka ---
# Ime baze podataka. S obzirom da systemd servis koristi WorkingDirectory=/usr/local/bin/,
# baza će biti kreirana tamo.
DB_NAME = 'iot_data.db'
TABLE_NAME = 'sensor_readings'


def init_db():
    """Inicijalizira SQLite bazu podataka i stvara tablicu ako ne postoji."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Stvara tablicu za pohranu podataka senzora
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id INTEGER PRIMARY KEY,
                topic TEXT NOT NULL,
                system_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                measurement_time REAL,
                value REAL
            );
        """)
        conn.commit()
        conn.close()
        print(f"[INIT] Database '{DB_NAME}' initialized successfully.")
        sys.stdout.flush()
    except Exception as e:
        print(f"[INIT ERROR] Could not initialize database: {e}")
        sys.stdout.flush()

def insert_data(topic, payload_json):
    """Parsira JSON payload i pohranjuje podatke u bazu."""
    try:
        # Dekodiranje JSON stringa u Python rječnik
        data = json.loads(payload_json)
        
        # Očekujemo 'timestamp' (vrijeme mjerenja sa senzora) i 'value'
        # Napomena: Ako pošaljete drugu strukturu, ovo morate prilagoditi!
        measurement_time = data.get('timestamp', time.time()) # Koristi vrijeme senzora, ili sistemsko vrijeme ako fali
        value = data.get('value')
        
        if value is not None:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            cursor.execute(f"""
                INSERT INTO {TABLE_NAME} (topic, measurement_time, value)
                VALUES (?, ?, ?)
            """, (topic, measurement_time, value))
            
            conn.commit()
            conn.close()
            print(f"[{topic}] Data saved: {value}")
            sys.stdout.flush()
        else:
            print(f"[WARNING] Payload from topic {topic} is missing 'value'. Ignoring.")
            sys.stdout.flush()

    except json.JSONDecodeError:
        print(f"[ERROR] Could not decode JSON from topic {topic}. Payload: {payload_json}")
        sys.stdout.flush()
    except Exception as e:
        print(f"[DB ERROR] Failed to insert data: {e}")
        sys.stdout.flush()


# --- MQTT Callbacks ---

def on_connect(client, userdata, flags, reason_code, properties):
    # Ovdje je 5 argumenata, u skladu s VERSION2 API-jem
    if reason_code == 0:
        print(f"[MQTT] Connected to Broker at {BROKER_ADDRESS}:{BROKER_PORT} successfully.")
        sys.stdout.flush()
        client.subscribe(TOPIC_SUBSCRIPTION)
        print(f"[MQTT] Subscribed to topic: {TOPIC_SUBSCRIPTION}")
        sys.stdout.flush()
    else:
        # Paho 2.0+ koristi 'reason_code' za povratni status
        print(f"[MQTT ERROR] Failed to connect, return code {reason_code}")
        sys.stdout.flush()

def on_message(client, userdata, msg):
    """Callback funkcija kada se primi poruka."""
    topic = msg.topic
    payload = msg.payload.decode()
    
    print(f"[RECEIVE] Topic: {topic} | Payload: {payload}")
    sys.stdout.flush()
    
    # Poziv funkcije za obradu i pohranu podataka
    insert_data(topic, payload)

# --- Glavna izvršna petlja ---

if __name__ == '__main__':
    print("--- IoT Edge Data Collector Starting ---")
    sys.stdout.flush()
    
    # 1. Inicijalizacija baze podataka
    init_db()

    # 2. Konfiguracija MQTT klijenta
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    
    # 3. Spajanje na Broker
    try:
        # Pokušaj ponovnog spajanja (zbog systemd.service After=mosquitto.service)
        client.reconnect_delay_set(min_delay=1, max_delay=10) 
        client.connect(BROKER_ADDRESS, BROKER_PORT, 60)
        
        # Započinje petlju koja obrađuje mrežni promet i poziva on_message funkciju
        client.loop_forever() 
        
    except ConnectionRefusedError:
        print(f"[CRITICAL ERROR] Connection refused. Is Mosquitto running on {BROKER_ADDRESS}:{BROKER_PORT}?")
        sys.stdout.flush()
    except KeyboardInterrupt:
        print("Collector service stopped by user (Ctrl+C).")
        sys.stdout.flush()
    except Exception as e:
        print(f"[FATAL ERROR] An unexpected error occurred: {e}")
        sys.stdout.flush()
    finally:
        client.disconnect()
        print("--- MQTT client disconnected. Service stopped. ---")
        sys.stdout.flush()