#!/usr/bin/env python3
"""
Cisco Network Monitoring System
Real-time network monitoring and alerting solution

Features:
- Multi-device connectivity monitoring
- SNMP metrics collection
- Real-time alerting system
- Performance threshold monitoring
- Web dashboard interface
- Historical data logging
- Automated incident reporting
"""

import os
import sys
import json
import time
import logging
import threading
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
import statistics

try:
    from pysnmp.hlapi import *
    import requests
except ImportError:
    print("Error: Required libraries missing. Install with:")
    print("pip install pysnmp requests")
    sys.exit(1)

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    import config
except ImportError:
    print("Error: config.py not found. Please ensure config.py exists in project root.")
    sys.exit(1)


class NetworkMonitor:
    """
    Comprehensive network monitoring system for Cisco devices
    """
    
    def __init__(self, monitoring_interval=60):
        self.monitoring_interval = monitoring_interval
        self.devices_status = {}
        self.metrics_history = defaultdict(lambda: deque(maxlen=100))
        self.alerts_queue = deque(maxlen=1000)
        self.monitoring_active = False
        self.setup_logging()
        self.setup_directories()
        
        # Default thresholds
        self.thresholds = {
            'ping_timeout': 5.0,
            'cpu_critical': 90.0,
            'cpu_warning': 75.0,
            'memory_critical': 95.0,
            'memory_warning': 85.0,
            'interface_util_critical': 90.0,
            'interface_util_warning': 80.0
        }
    
    def setup_logging(self):
        """Configure logging for monitoring operations"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Main logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'network_monitor.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Alerts logger
        self.alerts_logger = logging.getLogger('alerts')
        alerts_handler = logging.FileHandler(log_dir / 'alerts.log')
        alerts_handler.setFormatter(logging.Formatter('%(asctime)s - ALERT - %(message)s'))
        self.alerts_logger.addHandler(alerts_handler)
        self.alerts_logger.setLevel(logging.WARNING)
    
    def setup_directories(self):
        """Create necessary directories for monitoring data"""
        directories = ['data/monitoring', 'data/reports', 'configs/sample_outputs']
        for dir_path in directories:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def ping_device(self, hostname, timeout=5):
        """
        Ping device to check basic connectivity
        
        Args:
            hostname (str): Device hostname or IP
            timeout (int): Ping timeout in seconds
            
        Returns:
            dict: Ping results with latency and packet loss
        """
        try:
            # Use system ping command
            cmd = ['ping', '-c', '4', '-W', str(timeout * 1000), hostname]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            
            if result.returncode == 0:
                # Parse ping output for statistics
                lines = result.stdout.strip().split('\n')
                stats_line = [line for line in lines if 'packet loss' in line]
                time_line = [line for line in lines if 'min/avg/max' in line]
                
                packet_loss = 0
                avg_latency = 0
                
                if stats_line:
                    # Extract packet loss percentage
                    packet_loss = float(stats_line[0].split('%')[0].split()[-1])
                
                if time_line:
                    # Extract average latency
                    times = time_line[0].split('=')[1].strip().split('/')
                    avg_latency = float(times[1])  # avg time
                
                return {
                    'status': 'up',
                    'packet_loss': packet_loss,
                    'avg_latency': avg_latency,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'status': 'down',
                    'packet_loss': 100,
                    'avg_latency': 0,
                    'error': result.stderr.strip(),
                    'timestamp': datetime.now().isoformat()
                }
                
        except subprocess.TimeoutExpired:
            return {
                'status': 'timeout',
                'packet_loss': 100,
                'avg_latency': 0,
                'error': 'Ping timeout exceeded',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'status': 'error',
                'packet_loss': 100,
                'avg_latency': 0,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_snmp_metric(self, hostname, community, oid):
        """
        Get SNMP metric from device
        
        Args:
            hostname (str): Device hostname or IP
            community (str): SNMP community string
            oid (str): SNMP OID to query
            
        Returns:
            str: SNMP response value or None if failed
        """
        try:
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(community),
                UdpTransportTarget((hostname, 161)),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False,
                ignoreNonIncreasingOid=True,
                maxRows=1):

                if errorIndication:
                    self.logger.debug(f"SNMP error indication: {errorIndication}")
                    break
                elif errorStatus:
                    self.logger.debug(f"SNMP error status: {errorStatus.prettyPrint()}")
                    break
                else:
                    for varBind in varBinds:
                        return str(varBind[1])
            return None
        except Exception as e:
            self.logger.debug(f"SNMP query failed for {hostname}: {str(e)}")
            return None
    
    def collect_device_metrics(self, device_info):
        """
        Collect comprehensive metrics from a device
        
        Args:
            device_info (dict): Device connection information
            
        Returns:
            dict: Collected metrics and status
        """
        hostname = device_info.get('hostname', device_info['host'])
        host_ip = device_info['host']
        snmp_community = device_info.get('snmp_community', 'public')
        
        metrics = {
            'hostname': hostname,
            'timestamp': datetime.now().isoformat(),
            'connectivity': {},
            'performance': {},
            'interfaces': {},
            'system': {}
        }
        
        # 1. Connectivity Test
        ping_result = self.ping_device(host_ip)
        metrics['connectivity'] = ping_result
        
        if ping_result['status'] != 'up':
            metrics['overall_status'] = 'down'
            return metrics
        
        # 2. SNMP System Information
        system_oids = {
            'sysUpTime': '1.3.6.1.2.1.1.3.0',
            'sysDescr': '1.3.6.1.2.1.1.1.0',
            'sysName': '1.3.6.1.2.1.1.5.0'
        }
        
        for metric_name, oid in system_oids.items():
            value = self.get_snmp_metric(host_ip, snmp_community, oid)
            metrics['system'][metric_name] = value
        
        # 3. CPU and Memory (Cisco specific OIDs)
        performance_oids = {
            'cpu_5min': '1.3.6.1.4.1.9.9.109.1.1.1.1.8.1',  # Cisco CPU 5min avg
            'memory_used': '1.3.6.1.4.1.9.9.48.1.1.1.5.1',   # Cisco memory used
            'memory_free': '1.3.6.1.4.1.9.9.48.1.1.1.6.1'    # Cisco memory free
        }
        
        for metric_name, oid in performance_oids.items():
            value = self.get_snmp_metric(host_ip, snmp_community, oid)
            if value:
                try:
                    metrics['performance'][metric_name] = float(value)
                except ValueError:
                    metrics['performance'][metric_name] = value
        
        # Calculate memory percentage if both used and free are available
        if 'memory_used' in metrics['performance'] and 'memory_free' in metrics['performance']:
            used = metrics['performance']['memory_used']
            free = metrics['performance']['memory_free']
            total = used + free
            if total > 0:
                metrics['performance']['memory_percent'] = (used / total) * 100
        
        # 4. Interface Statistics (basic check for first few interfaces)
        interface_base_oid = '1.3.6.1.2.1.2.2.1'
        interface_metrics = {}
        
        # Check first 5 interfaces
        for i in range(1, 6):
            if_name = self.get_snmp_metric(host_ip, snmp_community, f'{interface_base_oid}.2.{i}')
            if_status = self.get_snmp_metric(host_ip, snmp_community, f'{interface_base_oid}.8.{i}')
            if_speed = self.get_snmp_metric(host_ip, snmp_community, f'{interface_base_oid}.5.{i}')
            
            if if_name:
                interface_metrics[f'interface_{i}'] = {
                    'name': if_name,
                    'status': 'up' if if_status == '1' else 'down',
                    'speed': if_speed
                }
        
        metrics['interfaces'] = interface_metrics
        metrics['overall_status'] = 'up'
        
        return metrics
    
    def evaluate_alerts(self, metrics):
        """
        Evaluate metrics against thresholds and generate alerts
        
        Args:
            metrics (dict): Device metrics to evaluate
            
        Returns:
            list: List of generated alerts
        """
        alerts = []
        hostname = metrics['hostname']
        timestamp = metrics['timestamp']
        
        # Connectivity alerts
        if metrics['connectivity']['status'] != 'up':
            alert = {
                'hostname': hostname,
                'severity': 'critical',
                'type': 'connectivity',
                'message': f"Device {hostname} is unreachable",
                'details': metrics['connectivity'],
                'timestamp': timestamp
            }
            alerts.append(alert)
            return alerts  # If device is down, don't check other metrics
        
        # High latency alert
        if metrics['connectivity']['avg_latency'] > 100:
            alerts.append({
                'hostname': hostname,
                'severity': 'warning',
                'type': 'latency',
                'message': f"High latency detected: {metrics['connectivity']['avg_latency']:.1f}ms",
                'timestamp': timestamp
            })
        
        # CPU alerts
        if 'cpu_5min' in metrics['performance']:
            cpu_usage = metrics['performance']['cpu_5min']
            if cpu_usage > self.thresholds['cpu_critical']:
                alerts.append({
                    'hostname': hostname,
                    'severity': 'critical',
                    'type': 'cpu',
                    'message': f"Critical CPU usage: {cpu_usage:.1f}%",
                    'timestamp': timestamp
                })
            elif cpu_usage > self.thresholds['cpu_warning']:
                alerts.append({
                    'hostname': hostname,
                    'severity': 'warning',
                    'type': 'cpu',
                    'message': f"High CPU usage: {cpu_usage:.1f}%",
                    'timestamp': timestamp
                })
        
        # Memory alerts
        if 'memory_percent' in metrics['performance']:
            memory_usage = metrics['performance']['memory_percent']
            if memory_usage > self.thresholds['memory_critical']:
                alerts.append({
                    'hostname': hostname,
                    'severity': 'critical',
                    'type': 'memory',
                    'message': f"Critical memory usage: {memory_usage:.1f}%",
                    'timestamp': timestamp
                })
            elif memory_usage > self.thresholds['memory_warning']:
                alerts.append({
                    'hostname': hostname,
                    'severity': 'warning',
                    'type': 'memory',
                    'message': f"High memory usage: {memory_usage:.1f}%",
                    'timestamp': timestamp
                })
        
        # Interface down alerts
        for if_id, if_info in metrics['interfaces'].items():
            if if_info['status'] == 'down' and 'Ethernet' in if_info['name']:
                alerts.append({
                    'hostname': hostname,
                    'severity': 'warning',
                    'type': 'interface',
                    'message': f"Interface {if_info['name']} is down",
                    'timestamp': timestamp
                })
        
        return alerts
    
    def process_alerts(self, alerts):
        """
        Process and log alerts
        
        Args:
            alerts (list): List of alerts to process
        """
        for alert in alerts:
            # Add to alerts queue
            self.alerts_queue.append(alert)
            
            # Log alert
            severity_symbol = "🔴" if alert['severity'] == 'critical' else "🟡"
            log_message = f"{severity_symbol} {alert['hostname']}: {alert['message']}"
            
            if alert['severity'] == 'critical':
                self.alerts_logger.error(log_message)
            else:
                self.alerts_logger.warning(log_message)
            
            self.logger.info(f"Alert generated: {alert['type']} - {alert['message']}")
    
    def monitor_device(self, device_info):
        """
        Monitor a single device
        
        Args:
            device_info (dict): Device information
        """
        hostname = device_info.get('hostname', device_info['host'])
        
        try:
            # Collect metrics
            metrics = self.collect_device_metrics(device_info)
            
            # Store metrics
            self.devices_status[hostname] = metrics
            self.metrics_history[hostname].append(metrics)
            
            # Evaluate alerts
            alerts = self.evaluate_alerts(metrics)
            
            # Process alerts
            if alerts:
                self.process_alerts(alerts)
            
            # Log successful monitoring
            status_symbol = "✅" if metrics['overall_status'] == 'up' else "❌"
            self.logger.info(f"{status_symbol} Monitored {hostname}: {metrics['overall_status']}")
            
        except Exception as e:
            error_msg = f"Error monitoring {hostname}: {str(e)}"
            self.logger.error(error_msg)
            
            # Create error metrics entry
            error_metrics = {
                'hostname': hostname,
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'error',
                'error': error_msg
            }
            self.devices_status[hostname] = error_metrics
    
    def monitoring_loop(self, devices):
        """
        Main monitoring loop
        
        Args:
            devices (list): List of devices to monitor
        """
        self.logger.info(f"Starting monitoring loop for {len(devices)} devices")
        self.monitoring_active = True
        
        while self.monitoring_active:
            start_time = time.time()
            
            # Monitor all devices concurrently
            threads = []
            for device in devices:
                thread = threading.Thread(target=self.monitor_device, args=(device,))
                threads.append(thread)
                thread.start()
            
            # Wait for all monitoring threads to complete
            for thread in threads:
                thread.join(timeout=30)  # 30 second timeout per device
            
            # Calculate sleep time to maintain interval
            elapsed = time.time() - start_time
            sleep_time = max(0, self.monitoring_interval - elapsed)
            
            if sleep_time > 0:
                self.logger.debug(f"Monitoring cycle completed in {elapsed:.1f}s, sleeping for {sleep_time:.1f}s")
                time.sleep(sleep_time)
            else:
                self.logger.warning(f"Monitoring cycle took {elapsed:.1f}s, exceeding interval of {self.monitoring_interval}s")
    
    def generate_status_report(self):
        """Generate current status report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_devices': len(self.devices_status),
                'devices_up': sum(1 for status in self.devices_status.values() 
                                if status.get('overall_status') == 'up'),
                'devices_down': sum(1 for status in self.devices_status.values() 
                                  if status.get('overall_status') == 'down'),
                'devices_error': sum(1 for status in self.devices_status.values() 
                                   if status.get('overall_status') == 'error'),
                'active_alerts': len([alert for alert in self.alerts_queue 
                                    if alert['severity'] == 'critical'])
            },
            'devices': self.devices_status,
            'recent_alerts': list(self.alerts_queue)[-10:]  # Last 10 alerts
        }
        
        return report
    
    def save_report(self, report, filename=None):
        """Save report to file"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"data/reports/network_status_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.logger.info(f"Report saved to {filename}")
        return filename
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.monitoring_active = False
        self.logger.info("Monitoring stopped")


def main():
    """Main execution function with CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Cisco Network Monitoring System')
    parser.add_argument('--interval', type=int, default=60, help='Monitoring interval in seconds')
    parser.add_argument('--device', help='Monitor single device by hostname')
    parser.add_argument('--report', action='store_true', help='Generate status report only')
    parser.add_argument('--continuous', action='store_true', help='Run continuous monitoring')
    
    args = parser.parse_args()
    
    # Initialize monitor
    monitor = NetworkMonitor(args.interval)
    
    try:
        # Get devices from config
        if args.device:
            devices = [d for d in config.DEVICES if d.get('hostname', d['host']) == args.device]
            if not devices:
                print(f"Device {args.device} not found in config")
                return
        else:
            devices = config.DEVICES
            
    except AttributeError:
        print("Error: DEVICES list not found in config.py")
        return
    
    try:
        if args.report:
            # Single report generation
            print("Generating network status report...")
            
            # Monitor all devices once
            for device in devices:
                monitor.monitor_device(device)
            
            # Generate and save report
            report = monitor.generate_status_report()
            report_file = monitor.save_report(report)
            
            # Display summary
            print(f"\n📊 NETWORK STATUS SUMMARY")
            print(f"{'='*50}")
            print(f"Total Devices: {report['summary']['total_devices']}")
            print(f"Devices Up: ✅ {report['summary']['devices_up']}")
            print(f"Devices Down: ❌ {report['summary']['devices_down']}")
            print(f"Devices Error: ⚠️ {report['summary']['devices_error']}")
            print(f"Critical Alerts: 🔴 {report['summary']['active_alerts']}")
            print(f"\n📁 Report saved: {report_file}")
            
        elif args.continuous:
            # Continuous monitoring
            print(f"Starting continuous monitoring of {len(devices)} devices...")
            print(f"Monitoring interval: {args.interval} seconds")
            print("Press Ctrl+C to stop")
            
            try:
                monitor.monitoring_loop(devices)
            except KeyboardInterrupt:
                print("\nStopping monitoring...")
                monitor.stop_monitoring()
                
        else:
            # Single monitoring cycle
            print("Performing single monitoring cycle...")
            
            for device in devices:
                monitor.monitor_device(device)
            
            # Display results
            report = monitor.generate_status_report()
            print(f"\n📊 MONITORING RESULTS")
            print(f"{'='*40}")
            
            for hostname, status in report['devices'].items():
                status_symbol = "✅" if status.get('overall_status') == 'up' else "❌"
                print(f"{status_symbol} {hostname}: {status.get('overall_status', 'unknown')}")
                
                if status.get('connectivity', {}).get('avg_latency'):
                    latency = status['connectivity']['avg_latency']
                    print(f"   🔗 Latency: {latency:.1f}ms")
                
                if 'cpu_5min' in status.get('performance', {}):
                    cpu = status['performance']['cpu_5min']
                    print(f"   💻 CPU: {cpu:.1f}%")
                
                if 'memory_percent' in status.get('performance', {}):
                    memory = status['performance']['memory_percent']
                    print(f"   🧠 Memory: {memory:.1f}%")
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"Error: {str(e)}")
        monitor.logger.error(f"Unexpected error: {str(e)}")


if __name__ == "__main__":
    main()
