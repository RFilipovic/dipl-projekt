#!/usr/bin/env python3
"""
IoT Command Sender
Sends commands from IoT edge device to sensors via MQTT.
Can be run on host machine with SSH tunnel or directly on IoT device.
"""

import paho.mqtt.client as mqtt
import json
import time
import argparse
import subprocess
import sys
import os

class CommandSender:
    def __init__(self, broker_host, broker_port, ssh_tunnel=False, ssh_host="localhost", ssh_port=2222, ssh_user="root"):
        self.broker_host = broker_host
        self.broker_port = broker_port
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
        self.local_forward_port = 11883
        
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
            if self.ssh_tunnel:
                self._setup_ssh_tunnel()
                connect_host = "localhost"
                connect_port = self.local_forward_port
                print(f"[SSH] Using tunnel: {connect_host}:{connect_port} -> {self.ssh_user}@{self.ssh_host}:{self.ssh_port}")
            else:
                connect_host = self.broker_host
                connect_port = self.broker_port
            
            self.client.connect(connect_host, connect_port, 60)
            self.client.loop_start()
            
            timeout = 10
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)
                
            if not self.connected:
                raise TimeoutError(f"Could not connect to {connect_host}:{connect_port} within {timeout}s")
                
        except Exception as e:
            print(f"[✗] Connection error: {e}")
            raise
    
    def _setup_ssh_tunnel(self):
        """Setup SSH port forwarding tunnel"""
        try:
            print(f"[SSH] Setting up tunnel...")
            cmd = [
                'ssh', '-N',
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
            
            time.sleep(2)
            
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
        
    def send_command(self, sensor_id, command_data):
        """Send command to specific sensor or all sensors"""
        if not self.connected:
            print("[✗] Not connected to broker")
            return False
            
        topic = f"commands/{sensor_id}"
        payload = json.dumps(command_data)
        
        result = self.client.publish(topic, payload)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[→] Command sent to {topic}: {command_data}")
            return True
        else:
            print(f"[✗] Failed to send command: {result.rc}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="IoT Command Sender - Send commands from IoT device to sensors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Request 10 measurements from temperature sensor
  python3 command_sender.py --sensor-id temperature --command measure --count 10 --interval 1
  
  # Request measurements with specific parameters
  python3 command_sender.py --sensor-id humidity --command measure --count 5 --interval 2 --base 50 --variance 10
  
  # Send command to all sensors
  python3 command_sender.py --sensor-id all --command measure --count 20 --interval 0.5
  
  # Using SSH tunnel (from host machine)
  python3 command_sender.py --ssh-tunnel --sensor-id temperature --command measure --count 10
        """
    )
    
    parser.add_argument('--broker', default='localhost', help='MQTT broker address (default: localhost)')
    parser.add_argument('--port', type=int, default=1883, help='MQTT broker port (default: 1883)')
    parser.add_argument('--sensor-id', required=True, help='Target sensor ID or "all" for broadcast')
    
    # SSH Tunnel options
    parser.add_argument('--ssh-tunnel', action='store_true', help='Use SSH tunnel to connect to MQTT broker')
    parser.add_argument('--ssh-host', default='localhost', help='SSH host (default: localhost)')
    parser.add_argument('--ssh-port', type=int, default=2222, help='SSH port (default: 2222)')
    parser.add_argument('--ssh-user', default='root', help='SSH username (default: root)')
    
    # Command parameters
    parser.add_argument('--command', required=True, choices=['measure', 'stop'], help='Command to send')
    parser.add_argument('--count', type=int, default=10, help='Number of measurements (default: 10)')
    parser.add_argument('--interval', type=float, default=1.0, help='Interval between measurements (default: 1.0)')
    parser.add_argument('--base', type=float, default=25.0, help='Base value for measurements (default: 25)')
    parser.add_argument('--variance', type=float, default=5.0, help='Variance for measurements (default: 5)')
    
    args = parser.parse_args()
    
    # Create command sender
    sender = CommandSender(
        args.broker,
        args.port,
        ssh_tunnel=args.ssh_tunnel,
        ssh_host=args.ssh_host,
        ssh_port=args.ssh_port,
        ssh_user=args.ssh_user
    )
    
    try:
        print(f"\n{'='*60}")
        print(f"IoT Command Sender")
        print(f"{'='*60}")
        if args.ssh_tunnel:
            print(f"SSH Tunnel: {args.ssh_user}@{args.ssh_host}:{args.ssh_port}")
            print(f"Broker (via tunnel): {args.broker}:{args.port}")
        else:
            print(f"Broker: {args.broker}:{args.port}")
        print(f"Target: {args.sensor_id}")
        print(f"Command: {args.command}")
        print(f"{'='*60}\n")
        
        sender.connect()
        
        # Prepare command data
        command_data = {
            'command': args.command
        }
        
        if args.command == 'measure':
            command_data.update({
                'count': args.count,
                'interval': args.interval,
                'base': args.base,
                'variance': args.variance
            })
        
        # Send command
        sender.send_command(args.sensor_id, command_data)
        time.sleep(1)  # Give time to send
        
        print("\n[✓] Command sent successfully")
        
    except Exception as e:
        print(f"[✗] Error: {e}")
        sys.exit(1)
    finally:
        sender.disconnect()
        print("[✓] Disconnected\n")


if __name__ == '__main__':
    main()
