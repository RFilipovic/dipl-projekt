#!/usr/bin/env python3
"""
IoT Dashboard - Minimal Web UI
Lightweight dashboard for IoT device monitoring and control
"""

from flask import Flask, render_template_string, jsonify, request
import paho.mqtt.client as mqtt
import sqlite3
import json
from datetime import datetime
from threading import Lock

app = Flask(__name__)
mqtt_client = None
db_lock = Lock()
DB_PATH = "/usr/local/bin/iot_data.db"

# HTML Template - Pure CSS, no frameworks
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IoT Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        h1 { color: #2d3748; margin-bottom: 8px; font-size: 28px; }
        .subtitle { color: #718096; margin-bottom: 24px; }
        .status { 
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        .status.online { background: #c6f6d5; color: #22543d; }
        .status.offline { background: #fed7d7; color: #742a2a; }
        
        .sensor-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); 
            gap: 16px;
            margin-bottom: 24px;
        }
        .sensor-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 12px;
            position: relative;
        }
        .sensor-type { font-size: 14px; opacity: 0.9; margin-bottom: 4px; }
        .sensor-value { font-size: 36px; font-weight: bold; margin: 8px 0; }
        .sensor-id { font-size: 12px; opacity: 0.8; }
        .sensor-time { font-size: 11px; opacity: 0.7; margin-top: 8px; }
        
        .control-panel { margin-top: 24px; }
        .control-row {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: center;
            margin-bottom: 16px;
        }
        input, select {
            padding: 10px 14px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            font-size: 14px;
            outline: none;
            transition: border 0.2s;
        }
        input:focus, select:focus { border-color: #667eea; }
        
        button {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            color: white;
        }
        .btn-primary { background: #667eea; }
        .btn-primary:hover { background: #5568d3; }
        .btn-success { background: #48bb78; }
        .btn-success:hover { background: #38a169; }
        .btn-danger { background: #f56565; }
        .btn-danger:hover { background: #e53e3e; }
        
        .readings-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 16px;
        }
        .readings-table th {
            background: #f7fafc;
            padding: 12px;
            text-align: left;
            font-size: 12px;
            font-weight: 600;
            color: #4a5568;
            border-bottom: 2px solid #e2e8f0;
        }
        .readings-table td {
            padding: 12px;
            border-bottom: 1px solid #e2e8f0;
            font-size: 14px;
        }
        .readings-table tr:hover { background: #f7fafc; }
        
        .log { 
            background: #1a202c;
            color: #e2e8f0;
            padding: 16px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 12px;
            max-height: 200px;
            overflow-y: auto;
        }
        .log-entry { margin-bottom: 4px; }
        .log-time { color: #a0aec0; }
        .log-success { color: #48bb78; }
        .log-error { color: #f56565; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🌡️ IoT Device Dashboard</h1>
            <p class="subtitle">Monitor and control your IoT sensors</p>
            <span class="status online" id="mqtt-status">● MQTT Connected</span>
        </div>
        
        <div id="sensors-container"></div>
        
        <div class="card">
            <h2 style="margin-bottom: 16px; color: #2d3748;">📡 Sensor Control</h2>
            <div class="control-panel">
                <div class="control-row">
                    <select id="sensor-select" style="flex: 1; min-width: 200px;">
                        <option value="all">All Sensors</option>
                    </select>
                    <input type="number" id="count" placeholder="Count" value="10" style="width: 100px;">
                    <input type="number" id="interval" placeholder="Interval (s)" value="1" step="0.1" style="width: 120px;">
                    <button class="btn-primary" onclick="sendCommand('measure')">📊 Measure</button>
                    <button class="btn-success" onclick="sendCommand('start')">▶ Start</button>
                    <button class="btn-danger" onclick="sendCommand('stop')">⏹ Stop</button>
                </div>
            </div>
            
            <div class="log" id="command-log">
                <div class="log-entry"><span class="log-time">[Ready]</span> Waiting for commands...</div>
            </div>
        </div>
        
        <div class="card">
            <h2 style="margin-bottom: 16px; color: #2d3748;">📋 Recent Readings</h2>
            <table class="readings-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Sensor ID</th>
                        <th>Type</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody id="readings-tbody"></tbody>
            </table>
        </div>
    </div>
    
    <script>
        let sensors = {};
        
        function updateSensors() {
            fetch('/api/sensors')
                .then(r => r.json())
                .then(data => {
                    sensors = data.sensors;
                    renderSensors();
                    updateSensorSelect();
                });
        }
        
        function renderSensors() {
            const container = document.getElementById('sensors-container');
            if (Object.keys(sensors).length === 0) {
                container.innerHTML = '<div class="card"><p style="color: #718096;">No active sensors. Start a sensor to see data.</p></div>';
                return;
            }
            
            let html = '<div class="sensor-grid">';
            for (const [id, sensor] of Object.entries(sensors)) {
                const icon = sensor.type === 'temperature' ? '🌡️' : sensor.type === 'humidity' ? '💧' : '💡';
                const unit = sensor.type === 'temperature' ? '°C' : sensor.type === 'humidity' ? '%' : 'lux';
                html += `
                    <div class="sensor-card">
                        <div class="sensor-type">${icon} ${sensor.type.toUpperCase()}</div>
                        <div class="sensor-value">${sensor.value.toFixed(1)} ${unit}</div>
                        <div class="sensor-id">ID: ${id}</div>
                        <div class="sensor-time">${new Date(sensor.timestamp * 1000).toLocaleTimeString()}</div>
                    </div>
                `;
            }
            html += '</div>';
            container.innerHTML = html;
        }
        
        function updateSensorSelect() {
            const select = document.getElementById('sensor-select');
            const current = select.value;
            select.innerHTML = '<option value="all">All Sensors</option>';
            for (const id of Object.keys(sensors)) {
                select.innerHTML += `<option value="${id}">${id}</option>`;
            }
            select.value = current;
        }
        
        function updateReadings() {
            fetch('/api/readings')
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('readings-tbody');
                    tbody.innerHTML = data.readings.map(r => `
                        <tr>
                            <td>${new Date(r.timestamp * 1000).toLocaleString()}</td>
                            <td>${r.sensor_id}</td>
                            <td>${r.sensor_type}</td>
                            <td><strong>${r.value.toFixed(2)}</strong></td>
                        </tr>
                    `).join('');
                });
        }
        
        function sendCommand(cmd) {
            const sensorId = document.getElementById('sensor-select').value;
            const count = document.getElementById('count').value;
            const interval = document.getElementById('interval').value;
            
            const payload = { command: cmd };
            if (cmd === 'measure') {
                payload.count = parseInt(count);
                payload.interval = parseFloat(interval);
            }
            
            fetch(`/api/command/${sensorId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(r => r.json())
            .then(data => {
                logCommand(`Sent "${cmd}" to ${sensorId}`, true);
            })
            .catch(err => {
                logCommand(`Failed to send "${cmd}": ${err}`, false);
            });
        }
        
        function logCommand(msg, success) {
            const log = document.getElementById('command-log');
            const time = new Date().toLocaleTimeString();
            const cls = success ? 'log-success' : 'log-error';
            log.innerHTML = `<div class="log-entry"><span class="log-time">[${time}]</span> <span class="${cls}">${msg}</span></div>` + log.innerHTML;
        }
        
        // Auto-refresh
        setInterval(updateSensors, 2000);
        setInterval(updateReadings, 3000);
        updateSensors();
        updateReadings();
    </script>
</body>
</html>
"""

# MQTT Setup
def setup_mqtt():
    global mqtt_client
    try:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    except:
        mqtt_client = mqtt.Client()
    mqtt_client.connect("localhost", 1883, 60)
    mqtt_client.loop_start()

# API Routes
@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/sensors')
def get_sensors():
    """Get all active sensors from MQTT subscriptions"""
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Get latest reading for each topic
        cursor.execute("""
            SELECT topic, value, measurement_time
            FROM sensor_readings
            WHERE id IN (
                SELECT MAX(id) FROM sensor_readings GROUP BY topic
            )
            ORDER BY measurement_time DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        sensors = {}
        for row in rows:
            topic = row[0]  # e.g., "sensors/temperature"
            # Extract sensor type from topic
            parts = topic.split('/')
            sensor_type = parts[-1] if len(parts) > 1 else 'unknown'
            sensor_id = f"{sensor_type}-sensor"
            
            sensors[sensor_id] = {
                'id': sensor_id,
                'type': sensor_type,
                'value': row[1],
                'timestamp': row[2]
            }
        
        return jsonify({'sensors': sensors})

@app.route('/api/readings')
def get_readings():
    """Get recent readings"""
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT topic, value, measurement_time
            FROM sensor_readings
            ORDER BY measurement_time DESC
            LIMIT 20
        """)
        rows = cursor.fetchall()
        conn.close()
        
        readings = []
        for row in rows:
            topic = row[0]
            parts = topic.split('/')
            sensor_type = parts[-1] if len(parts) > 1 else 'unknown'
            sensor_id = f"{sensor_type}-sensor"
            
            readings.append({
                'sensor_id': sensor_id,
                'sensor_type': sensor_type,
                'value': row[1],
                'timestamp': row[2]
            })
        
        return jsonify({'readings': readings})

@app.route('/api/command/<sensor_id>', methods=['POST'])
def send_command(sensor_id):
    """Send command to sensor(s)"""
    data = request.json
    command = data.get('command')
    
    payload = {'command': command}
    if 'count' in data:
        payload['count'] = data['count']
    if 'interval' in data:
        payload['interval'] = data['interval']
    
    topic = f"commands/{sensor_id}"
    mqtt_client.publish(topic, json.dumps(payload))
    
    return jsonify({'status': 'sent', 'topic': topic, 'payload': payload})

if __name__ == '__main__':
    setup_mqtt()
    print("╔════════════════════════════════════════════╗")
    print("║       IoT Dashboard Web Server            ║")
    print("╚════════════════════════════════════════════╝")
    print("Starting on http://0.0.0.0:8080")
    app.run(host='0.0.0.0', port=8080, debug=False)
