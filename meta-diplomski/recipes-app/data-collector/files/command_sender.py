#!/usr/bin/env python3
"""
IoT Command Sender - Runs ON the IoT edge device
Sends commands to external sensors via MQTT broker
"""

import paho.mqtt.client as mqtt
import json
import time
import sys
import argparse

class CommandSender:
    def __init__(self, broker_host='localhost', broker_port=1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.connected = False
        
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print(f"[✓] Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            sys.stdout.flush()
            self.connected = True
        else:
            print(f"[✗] Failed to connect, return code {reason_code}")
            sys.stdout.flush()
            
    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)
                
            if not self.connected:
                raise TimeoutError(f"Could not connect within {timeout}s")
                
        except Exception as e:
            print(f"[✗] Connection error: {e}")
            sys.stdout.flush()
            raise
            
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        
    def send_command(self, sensor_id, command_data):
        """Send command to sensor(s)"""
        if not self.connected:
            print("[✗] Not connected to broker")
            sys.stdout.flush()
            return False
            
        topic = f"commands/{sensor_id}"
        payload = json.dumps(command_data)
        
        result = self.client.publish(topic, payload)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[→] Command sent to {topic}")
            print(f"    {command_data}")
            sys.stdout.flush()
            return True
        else:
            print(f"[✗] Failed to send command: {result.rc}")
            sys.stdout.flush()
            return False


def main():
    parser = argparse.ArgumentParser(description="Send commands to sensors from IoT device")
    
    parser.add_argument('--broker', default='localhost', help='MQTT broker (default: localhost)')
    parser.add_argument('--port', type=int, default=1883, help='MQTT port (default: 1883)')
    parser.add_argument('--sensor-id', required=True, help='Target sensor ID or "all"')
    parser.add_argument('--command', required=True, choices=['measure', 'stop'], help='Command to send')
    parser.add_argument('--count', type=int, default=10, help='Number of measurements (default: 10)')
    parser.add_argument('--interval', type=float, default=1.0, help='Interval between measurements (default: 1.0)')
    parser.add_argument('--base', type=float, default=25.0, help='Base value (default: 25)')
    parser.add_argument('--variance', type=float, default=5.0, help='Variance (default: 5)')
    
    args = parser.parse_args()
    
    sender = CommandSender(args.broker, args.port)
    
    try:
        print("\n" + "="*60)
        print("IoT Command Sender (Edge Device)")
        print("="*60)
        print(f"Broker: {args.broker}:{args.port}")
        print(f"Target: {args.sensor_id}")
        print(f"Command: {args.command}")
        print("="*60 + "\n")
        sys.stdout.flush()
        
        sender.connect()
        
        # Prepare command
        command_data = {'command': args.command}
        
        if args.command == 'measure':
            command_data.update({
                'count': args.count,
                'interval': args.interval,
                'base': args.base,
                'variance': args.variance
            })
        
        # Send command
        sender.send_command(args.sensor_id, command_data)
        time.sleep(1)
        
        print("\n[✓] Command sent successfully\n")
        sys.stdout.flush()
        
    except Exception as e:
        print(f"[✗] Error: {e}")
        sys.stdout.flush()
        sys.exit(1)
    finally:
        sender.disconnect()


if __name__ == '__main__':
    main()
