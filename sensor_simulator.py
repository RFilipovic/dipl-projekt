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
    def __init__(self, broker_host, broker_port, sensor_type, sensor_id=None, topic_prefix="sensors", ssh_tunnel=False, ssh_host="localhost", ssh_port=2222, ssh_user="root", listen_commands=False):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.sensor_type = sensor_type
        self.sensor_id = sensor_id or sensor_type  # Unique sensor ID
        self.topic_prefix = topic_prefix
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.connected = False
        self.listen_commands = listen_commands
        
        # Command handling
        self.command_active = False
        
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
            
            # Subscribe to commands if enabled
            if self.listen_commands:
                # Subscribe to sensor-specific and broadcast commands
                client.subscribe(f"commands/{self.sensor_id}")
                client.subscribe(f"commands/all")
                print(f"[✓] Subscribed to commands/{self.sensor_id} and commands/all")
        else:
            print(f"[✗] Failed to connect, return code {reason_code}")
            
    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        print(f"[✗] Disconnected from broker")
        self.connected = False
        
    def on_message(self, client, userdata, msg):
        """Handle incoming command messages"""
        try:
            command_data = json.loads(msg.payload.decode())
            print(f"\n[📩] Received command on {msg.topic}: {command_data}")
            
            command = command_data.get('command')
            
            if command == 'measure':
                count = command_data.get('count', 10)
                interval = command_data.get('interval', 1)
                base = command_data.get('base', 25)
                variance = command_data.get('variance', 5)
                
                print(f"[▶] Starting measurement: {count} readings, interval {interval}s")
                self.command_active = True
                
                # Execute measurement
                for i in range(count):
                    if not self.command_active:
                        print("[⊥] Measurement stopped")
                        break
                    value = base + random.uniform(-variance, variance)
                    self.send_sensor_data(round(value, 2))
                    if i < count - 1:  # Don't sleep after last reading
                        time.sleep(interval)
                
                self.command_active = False
                print(f"[✓] Measurement complete: {count} readings sent")
                
            elif command == 'stop':
                print(f"[⊥] Stop command received")
                self.command_active = False
                
            else:
                print(f"[⚠] Unknown command: {command}")
                
        except json.JSONDecodeError as e:
            print(f"[✗] Invalid command JSON: {e}")
        except Exception as e:
            print(f"[✗] Error processing command: {e}")
        
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
    
    # Command listening mode
    parser.add_argument('--listen', action='store_true', help='Listen for commands from IoT device')
    parser.add_argument('--sensor-id', help='Unique sensor ID (default: sensor type)')
    parser.add_argument('--daemon', action='store_true', help='Run in background (daemon mode)')
    
    # Single reading or simulation
    parser.add_argument('--value', type=float, help='Single sensor value to send')
    parser.add_argument('--simulate', action='store_true', help='Enable continuous simulation')
    parser.add_argument('--duration', type=int, default=60, help='Simulation duration in seconds (default: 60)')
    parser.add_argument('--interval', type=float, default=1.0, help='Interval between readings in seconds (default: 1.0)')
    parser.add_argument('--base', type=float, help='Base value for simulation')
    parser.add_argument('--variance', type=float, default=5, help='Value variance for simulation (default: 5)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.listen and not args.simulate and args.value is None:
        parser.error('Either --value for single reading, --simulate for continuous simulation, or --listen for command mode is required')
        
    if args.simulate and args.base is None:
        parser.error('--base is required when using --simulate')
    
    # Create simulator
    simulator = SensorSimulator(
        args.broker, 
        args.port, 
        args.sensor,
        sensor_id=args.sensor_id,
        topic_prefix=args.topic_prefix,
        ssh_tunnel=args.ssh_tunnel,
        ssh_host=args.ssh_host,
        ssh_port=args.ssh_port,
        ssh_user=args.ssh_user,
        listen_commands=args.listen
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
        print(f"Sensor: {args.sensor} (ID: {simulator.sensor_id})")
        print(f"Topic: {args.topic_prefix}/{args.sensor}")
        if args.listen:
            print(f"Command Mode: Listening on commands/{simulator.sensor_id}")
        print(f"{'='*60}\n")
        
        simulator.connect()
        
        if args.listen:
            # Command listening mode - keep running until interrupted
            if args.daemon:
                print("[🎧] Running in daemon mode (background)")
                print(f"     PID: {os.getpid()}")
                print(f"     Listening on: commands/{simulator.sensor_id}")
                print("[ℹ] To stop: kill {os.getpid()}\n")
            else:
                print("[🎧] Listening for commands... (Press Ctrl+C to stop)\n")
            
            sys.stdout.flush()
            
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n[⊥] Stopped by user")
                sys.stdout.flush()
        elif args.simulate:
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
