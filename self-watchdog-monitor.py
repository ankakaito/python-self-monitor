# Configuration Variables
SERVER_NAME = "server_name" # Replace with you server name
TELEGRAM_BOT_TOKEN = "telegram_token" # Place With Your Telegram Token
TELEGRAM_CHAT_ID = "telegram_chat_id" # Place With Your Telegram Chat ID
THRESHOLD = 80  # Alert threshold percentage
ALERT_INTERVAL = 300  # Time between alert checks in seconds (300 = 5 minutes)
STATUS_INTERVAL = 4  # Time between regular status updates in hours, 0.5 for half hour
LOG_DIR = "path_file_log" # fill with path do you want to store the log file
LOG_FILE = "system_monitor.log"

import psutil
import time
import logging
from datetime import datetime
import requests
import socket
import platform
import os
import threading
import subprocess

# Create log directory if it doesn't exist
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except PermissionError:
    LOG_DIR = os.path.expanduser('~/.system_monitor')
    os.makedirs(LOG_DIR, exist_ok=True)

# Set up logging
log_file_path = os.path.join(LOG_DIR, LOG_FILE)
logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class SystemMonitor:
    def __init__(self):
        """Initialize SystemMonitor"""
        self.threshold = THRESHOLD
        self.alert_interval = ALERT_INTERVAL
        self.status_interval = STATUS_INTERVAL * 3600
        self.server_name = SERVER_NAME
        self.os_info = self._get_os_info()
        self.arch_info = platform.machine()
        self.prev_network_bytes = self._get_network_bytes()

        # Telegram configuration
        self.telegram_config = {
            'bot_token': TELEGRAM_BOT_TOKEN,
            'chat_id': TELEGRAM_CHAT_ID
        }

    def _get_os_info(self):
        """Get detailed OS information"""
        try:
            # Get basic OS info
            os_name = platform.system()
            if os_name == "Linux":
                # Try to get Linux distribution info
                try:
                    # Try reading from os-release file first
                    with open("/etc/os-release") as f:
                        lines = f.readlines()
                        os_info = {}
                        for line in lines:
                            if "=" in line:
                                key, value = line.rstrip().split("=", 1)
                                os_info[key] = value.strip('"')
                        if "PRETTY_NAME" in os_info:
                            return os_info["PRETTY_NAME"]
                except:
                    # Fallback to lsb_release command
                    try:
                        os_info = subprocess.check_output(['lsb_release', '-ds']).decode().strip()
                        return os_info
                    except:
                        pass
            
            # Fallback to basic platform info
            return f"{platform.system()} {platform.release()}"
        except Exception as e:
            logging.error(f"Error getting OS info: {e}")
            return f"{platform.system()} {platform.release()}"

    def _get_network_bytes(self):
        """Get current network bytes"""
        net_io = psutil.net_io_counters()
        return (net_io.bytes_sent, net_io.bytes_recv)

    def get_network_speed(self):
        """Calculate network speed"""
        try:
            current_bytes = self._get_network_bytes()
            sent_speed = (current_bytes[0] - self.prev_network_bytes[0]) / self.alert_interval
            recv_speed = (current_bytes[1] - self.prev_network_bytes[1]) / self.alert_interval
            self.prev_network_bytes = current_bytes
            return f"↑ {sent_speed/1024:.2f} KB/s | ↓ {recv_speed/1024:.2f} KB/s"
        except:
            return "N/A"

    def get_cpu_temperature(self):
        """Get CPU temperature with multiple methods"""
        try:
            # Method 1: Using psutil
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        for entry in entries:
                            if any(x in entry.label.lower() for x in ['core', 'cpu', 'package']):
                                return f"{entry.current}°C"

            # Method 2: Try reading from thermal zone on Linux
            if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
                with open('/sys/class/thermal/thermal_zone0/temp') as f:
                    temp = int(f.read()) / 1000.0
                    return f"{temp}°C"

            # Method 3: Using vcgencmd for Raspberry Pi
            if os.path.exists('/opt/vc/bin/vcgencmd'):
                temp = subprocess.check_output(['/opt/vc/bin/vcgencmd', 'measure_temp'])
                return temp.decode('utf-8').replace('temp=', '').strip()
            
            # Method 4: Using sensors command
            try:
                temp = subprocess.check_output(['sensors']).decode()
                for line in temp.split('\n'):
                    if 'Core 0' in line:
                        return line.split('+')[1].split('°')[0].strip() + '°C'
            except:
                pass

            return "N/A"
        except Exception as e:
            logging.error(f"Error reading CPU temperature: {e}")
            return "N/A"

    def get_disk_usage(self):
        """Get disk usage for all mounted partitions excluding /snap"""
        disk_usage = {}
        for partition in psutil.disk_partitions():
            try:
                # Skip if mountpoint is or contains /snap
                if '/snap' in partition.mountpoint:
                    continue
                    
                # Skip if the partition's root path contains /snap
                root_path = os.path.realpath(partition.mountpoint)
                if '/snap' in root_path:
                    continue

                usage = psutil.disk_usage(partition.mountpoint)
                disk_usage[partition.mountpoint] = {
                    'percent': usage.percent,
                    'total': f"{usage.total / (1024**3):.1f}GB",
                    'used': f"{usage.used / (1024**3):.1f}GB",
                    'free': f"{usage.free / (1024**3):.1f}GB"
                }
            except Exception as e:
                logging.error(f"Error getting disk usage for {partition.mountpoint}: {e}")
        return disk_usage

    def get_system_metrics(self):
        """Get comprehensive system metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_freq = psutil.cpu_freq()
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return {
                'cpu_percent': cpu_percent,
                'cpu_freq': f"{cpu_freq.current/1000:.2f}GHz" if cpu_freq else "N/A",
                'cpu_temp': self.get_cpu_temperature(),
                'memory_total': f"{memory.total / (1024**3):.2f}GB",
                'memory_used': f"{memory.used / (1024**3):.2f}GB",
                'memory_percent': memory.percent,
                'swap_used': f"{swap.used / (1024**3):.2f}GB",
                'swap_percent': swap.percent,
                'network_speed': self.get_network_speed()
            }
        except Exception as e:
            logging.error(f"Error getting system metrics: {e}")
            return {}

    def send_telegram_message(self, title, message_type="status"):
        """Send message via Telegram"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            metrics = self.get_system_metrics()
            disk_usage = self.get_disk_usage()

            # Create detailed disk usage string
            disk_info = []
            for mount, usage in disk_usage.items():
                disk_info.append(
                    f"💽 {mount}:\n"
                    f"   Used: {usage['used']}/{usage['total']} ({usage['percent']}%)\n"
                    f"   Free: {usage['free']}"
                )
            disk_info = "\n".join(disk_info)

            icon = "⚠" if message_type == "alert" else "ℹ"

            message = (
                f"{icon} <b>{title}</b>\n\n"
                f"🖥 Server: <b>{self.server_name}</b>\n"
                f"💻 OS: {self.os_info}\n"
                f"🔧 Architecture: {self.arch_info}\n"
                f"🕒 Time: {timestamp}\n\n"
                f"📊 System Metrics:\n"
                f"CPU Usage: {metrics.get('cpu_percent', 'N/A')}%\n"
                f"CPU Frequency: {metrics.get('cpu_freq', 'N/A')}\n"
                f"CPU Temperature: {metrics.get('cpu_temp', 'N/A')}\n"
                f"RAM Used: {metrics.get('memory_used', 'N/A')}/{metrics.get('memory_total', 'N/A')} "
                f"({metrics.get('memory_percent', 'N/A')}%)\n"
                f"Swap Used: {metrics.get('swap_used', 'N/A')} ({metrics.get('swap_percent', 'N/A')}%)\n"
                f"Network: {metrics.get('network_speed', 'N/A')}\n\n"
                f"Storage Usage:\n{disk_info}"
            )

            url = f"https://api.telegram.org/bot{self.telegram_config['bot_token']}/sendMessage"
            data = {
                "chat_id": self.telegram_config['chat_id'],
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=data)

            if response.status_code == 200:
                logging.info(f"Telegram message sent: {title}")
            else:
                logging.error(f"Failed to send Telegram message. Status code: {response.status_code}")

        except Exception as e:
            logging.error(f"Error sending Telegram message: {e}")

    def check_thresholds(self):
        """Check system resources against thresholds"""
        metrics = self.get_system_metrics()
        disk_usage = self.get_disk_usage()

        # Check RAM
        if metrics.get('memory_percent', 0) >= self.threshold:
            self.send_telegram_message(
                "High RAM Usage Alert",
                message_type="alert"
            )

        # Check Swap
        if metrics.get('swap_percent', 0) >= self.threshold:
            self.send_telegram_message(
                "High Swap Usage Alert",
                message_type="alert"
            )

        # Check CPU
        if metrics.get('cpu_percent', 0) >= self.threshold:
            self.send_telegram_message(
                "High CPU Usage Alert",
                message_type="alert"
            )

        # Check Disk (excluding /snap)
        for mountpoint, usage in disk_usage.items():
            if usage['percent'] >= self.threshold:
                self.send_telegram_message(
                    f"High Disk Usage Alert for {mountpoint}",
                    message_type="alert"
                )
                break

    def alert_monitor(self):
        """Continuous monitoring for alerts"""
        while True:
            try:
                self.check_thresholds()
                time.sleep(self.alert_interval)
            except Exception as e:
                logging.error(f"Error in alert monitoring: {e}")
                time.sleep(self.alert_interval)

    def status_update(self):
        """Regular status update monitoring"""
        while True:
            try:
                self.send_telegram_message("Regular Status Update")
                time.sleep(self.status_interval)
            except Exception as e:
                logging.error(f"Error in status update: {e}")
                time.sleep(self.status_interval)

    def start_monitoring(self):
        """Start all monitoring threads"""
        logging.info(f"Starting system monitoring for server: {self.server_name}")

        # Send startup notification
        self.send_telegram_message("Monitoring Started")

        try:
            # Create and start monitoring threads
            alert_thread = threading.Thread(target=self.alert_monitor)
            status_thread = threading.Thread(target=self.status_update)

            alert_thread.daemon = True
            status_thread.daemon = True

            alert_thread.start()
            status_thread.start()

            # Keep main thread alive
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            logging.info("Monitoring stopped by user")
            self.send_telegram_message("Monitoring Stopped")
        except Exception as e:
            logging.error(f"Error in main monitoring loop: {e}")
            self.send_telegram_message(f"Monitoring Error: {str(e)}")

if __name__ == "__main__":
    monitor = SystemMonitor()
    monitor.start_monitoring()

