#!/usr/bin/env python3
"""
IoT Sensor Simulator
Sends simulated sensor data to the MQTT broker running on QEMU edge node.
Supports both direct connections and SSH tunneling.
"""

import paho.mqtt.client as mqtt
import json
import time
import random
import argparse
import subprocess
import sys
import os
from datetime import datetime

class SensorSimulator:
    def __init__(self, broker_host, broker_port, sensor_type, topic_prefix="sensors", ssh_tunnel=False, ssh_host="localhost", ssh_port=2222, ssh_user="root"):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.sensor_type = sensor_type
        self.topic_prefix = topic_prefix
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.connected = False
        
        # SSH Tunnel settings
        self.ssh_tunnel = ssh_tunnel
        self.ssh_host = ssh_host
        self.ssh_port = ssh_port
        self.ssh_user = ssh_user
        self.tunnel_process = None
        self.local_forward_port = 11883  # Local port for tunnel
        
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print(f"[✓] Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            self.connected = True
        else:
            print(f"[✗] Failed to connect, return code {reason_code}")
            
    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        print(f"[✗] Disconnected from broker")
        self.connected = False
        
    def connect(self):
        """Connect to MQTT broker"""
        try:
            # Setup SSH tunnel if requested
            if self.ssh_tunnel:
                self._setup_ssh_tunnel()
                connect_host = "localhost"
                connect_port = self.local_forward_port
                print(f"[SSH] Using tunnel: {connect_host}:{connect_port} -> {self.ssh_user}@{self.ssh_host}:{self.ssh_port} -> {self.broker_host}:{self.broker_port}")
            else:
                connect_host = self.broker_host
                connect_port = self.broker_port
            
            self.client.connect(connect_host, connect_port, 60)
            self.client.loop_start()
            
            # Wait for connection to establish (max 10 seconds)
            timeout = 10
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)
                
            if not self.connected:
                print(f"[✗] Connection timeout after {timeout}s")
                raise TimeoutError(f"Could not connect to {connect_host}:{connect_port} within {timeout}s")
                
        except Exception as e:
            print(f"[✗] Connection error: {e}")
            raise
    
    def _setup_ssh_tunnel(self):
        """Setup SSH port forwarding tunnel"""
        try:
            print(f"[SSH] Setting up tunnel...")
            # ssh -L local_port:remote_host:remote_port user@host
            cmd = [
                'ssh',
                '-N',  # Don't execute remote command
                '-L', f'{self.local_forward_port}:{self.broker_host}:{self.broker_port}',
                f'{self.ssh_user}@{self.ssh_host}',
                '-p', str(self.ssh_port),
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null'
            ]
            
            self.tunnel_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            # Give tunnel time to establish
            time.sleep(2)
            
            # Check if tunnel is running
            if self.tunnel_process.poll() is not None:
                stderr = self.tunnel_process.stderr.read().decode()
                raise Exception(f"SSH tunnel failed: {stderr}")
            
            print(f"[SSH] Tunnel established")
            
        except Exception as e:
            print(f"[✗] SSH tunnel error: {e}")
            raise
    
    def _close_ssh_tunnel(self):
        """Close SSH tunnel"""
        if self.tunnel_process:
            try:
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(self.tunnel_process.pid), 9)
                else:
                    self.tunnel_process.kill()
                self.tunnel_process.wait()
                print(f"[SSH] Tunnel closed")
            except Exception as e:
                print(f"[⚠] Error closing tunnel: {e}")
            
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        self._close_ssh_tunnel()
        
    def send_sensor_data(self, value, timestamp=None):
        """Send a single sensor reading"""
        if not self.connected:
            print("[✗] Not connected to broker")
            return False
            
        if timestamp is None:
            timestamp = time.time()
            
        topic = f"{self.topic_prefix}/{self.sensor_type}"
        payload = json.dumps({
            "timestamp": timestamp,
            "value": value,
            "sensor_type": self.sensor_type
        })
        
        self.client.publish(topic, payload)
        print(f"[→] {topic}: {value}")
        return True
        
    def simulate_continuous(self, duration_seconds, interval_seconds, base_value, variance):
        """Simulate continuous sensor readings"""
        print(f"\n[▶] Starting simulation for {duration_seconds}s (interval: {interval_seconds}s)")
        print(f"    Base value: {base_value}, Variance: ±{variance}\n")
        
        start_time = time.time()
        reading_count = 0
        
        try:
            while (time.time() - start_time) < duration_seconds:
                # Generate value with random variance
                value = base_value + random.uniform(-variance, variance)
                self.send_sensor_data(round(value, 2))
                reading_count += 1
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print(f"\n[⊥] Stopped by user")
        finally:
            elapsed = time.time() - start_time
            print(f"\n[✓] Simulation complete: {reading_count} readings sent in {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(
        description="IoT Sensor Simulator - Send data to QEMU edge node",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single reading
  python3 sensor_simulator.py --broker localhost --port 18830 --sensor temperature --value 25.5
  
  # Continuous simulation (temperature: 20-30°C, every 2 seconds, for 60 seconds)
  python3 sensor_simulator.py --broker localhost --port 18830 --sensor temperature \\
    --simulate --duration 60 --interval 2 --base 25 --variance 5
    
  # Humidity simulation (40-60%, every second, for 30 seconds)
  python3 sensor_simulator.py --broker localhost --port 18830 --sensor humidity \\
    --simulate --duration 30 --interval 1 --base 50 --variance 10
        """
    )
    
    parser.add_argument('--broker', default='localhost', help='MQTT broker address (default: localhost)')
    parser.add_argument('--port', type=int, default=1883, help='MQTT broker port (default: 1883)')
    parser.add_argument('--sensor', required=True, help='Sensor type (e.g., temperature, humidity, pressure)')
    parser.add_argument('--topic-prefix', default='sensors', help='MQTT topic prefix (default: sensors)')
    
    # SSH Tunnel options
    parser.add_argument('--ssh-tunnel', action='store_true', help='Use SSH tunnel to connect to MQTT broker')
    parser.add_argument('--ssh-host', default='localhost', help='SSH host (default: localhost)')
    parser.add_argument('--ssh-port', type=int, default=2222, help='SSH port (default: 2222)')
    parser.add_argument('--ssh-user', default='root', help='SSH username (default: root)')
    
    # Single reading or simulation
    parser.add_argument('--value', type=float, help='Single sensor value to send')
    parser.add_argument('--simulate', action='store_true', help='Enable continuous simulation')
    parser.add_argument('--duration', type=int, default=60, help='Simulation duration in seconds (default: 60)')
    parser.add_argument('--interval', type=float, default=1.0, help='Interval between readings in seconds (default: 1.0)')
    parser.add_argument('--base', type=float, help='Base value for simulation')
    parser.add_argument('--variance', type=float, default=5, help='Value variance for simulation (default: 5)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.simulate and args.value is None:
        parser.error('Either --value for single reading or --simulate for continuous simulation is required')
        
    if args.simulate and args.base is None:
        parser.error('--base is required when using --simulate')
    
    # Create simulator
    simulator = SensorSimulator(
        args.broker, 
        args.port, 
        args.sensor, 
        args.topic_prefix,
        ssh_tunnel=args.ssh_tunnel,
        ssh_host=args.ssh_host,
        ssh_port=args.ssh_port,
        ssh_user=args.ssh_user
    )
    
    try:
        print(f"\n{'='*60}")
        print(f"IoT Sensor Simulator")
        print(f"{'='*60}")
        if args.ssh_tunnel:
            print(f"SSH Tunnel: {args.ssh_user}@{args.ssh_host}:{args.ssh_port}")
            print(f"Broker (via tunnel): {args.broker}:{args.port}")
        else:
            print(f"Broker: {args.broker}:{args.port}")
        print(f"Sensor: {args.sensor}")
        print(f"Topic: {args.topic_prefix}/{args.sensor}")
        print(f"{'='*60}\n")
        
        simulator.connect()
        
        if args.simulate:
            simulator.simulate_continuous(args.duration, args.interval, args.base, args.variance)
        else:
            simulator.send_sensor_data(args.value)
            time.sleep(1)  # Give time to send
            
    except Exception as e:
        print(f"[✗] Error: {e}")
    finally:
        simulator.disconnect()
        print("[✓] Disconnected\n")


if __name__ == '__main__':
    main()
