#!/usr/bin/env python3
"""
Cisco Configuration Backup Manager
Automated backup solution for Cisco network devices

Features:
- Multi-device backup support
- Timestamped configuration files
- Automatic directory organization
- Connection retry logic
- Comprehensive logging
- Configuration comparison
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import difflib
import concurrent.futures

try:
    from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
except ImportError:
    print("Error: netmiko library required. Install with: pip install netmiko")
    sys.exit(1)

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    import config
except ImportError:
    print("Error: config.py not found. Please ensure config.py exists in project root.")
    sys.exit(1)


class CiscoBackupManager:
    """
    Manages automated backups of Cisco device configurations
    """
    
    def __init__(self, backup_dir="configs/backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.setup_logging()
        self.stats = {
            'successful': 0,
            'failed': 0,
            'total_devices': 0,
            'start_time': datetime.now()
        }
    
    def setup_logging(self):
        """Configure logging for backup operations"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'backup_manager.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def create_device_directory(self, hostname):
        """Create device-specific backup directory"""
        device_dir = self.backup_dir / hostname
        device_dir.mkdir(exist_ok=True)
        return device_dir
    
    def get_timestamp(self):
        """Generate timestamp for backup files"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def backup_device_config(self, device_info):
        """
        Backup configuration from a single device
        
        Args:
            device_info (dict): Device connection parameters
            
        Returns:
            dict: Backup result with status and details
        """
        hostname = device_info.get('hostname', device_info['host'])
        self.logger.info(f"Starting backup for {hostname}")
        
        try:
            # Establish connection
            connection = ConnectHandler(**device_info)
            self.logger.info(f"Connected to {hostname}")
            
            # Get running configuration
            config_output = connection.send_command('show running-config')
            
            # Get device info for metadata
            device_info_output = connection.send_command('show version | include uptime|Software|System')
            
            # Close connection
            connection.disconnect()
            
            # Create device directory
            device_dir = self.create_device_directory(hostname)
            
            # Generate filename with timestamp
            timestamp = self.get_timestamp()
            config_filename = f"{hostname}_config_{timestamp}.txt"
            info_filename = f"{hostname}_info_{timestamp}.txt"
            
            # Save configuration
            config_path = device_dir / config_filename
            with open(config_path, 'w') as f:
                f.write(f"# Configuration backup for {hostname}\n")
                f.write(f"# Backup date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Device: {hostname}\n\n")
                f.write(config_output)
            
            # Save device info
            info_path = device_dir / info_filename
            with open(info_path, 'w') as f:
                f.write(f"# Device information for {hostname}\n")
                f.write(f"# Backup date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(device_info_output)
            
            # Create latest symlinks for easy access
            latest_config = device_dir / f"{hostname}_latest_config.txt"
            latest_info = device_dir / f"{hostname}_latest_info.txt"
            
            if latest_config.exists():
                latest_config.unlink()
            if latest_info.exists():
                latest_info.unlink()
                
            latest_config.symlink_to(config_filename)
            latest_info.symlink_to(info_filename)
            
            self.stats['successful'] += 1
            self.logger.info(f"Successfully backed up {hostname}")
            
            return {
                'hostname': hostname,
                'status': 'success',
                'config_file': str(config_path),
                'info_file': str(info_path),
                'timestamp': timestamp,
                'config_size': len(config_output)
            }
            
        except NetmikoAuthenticationException as e:
            error_msg = f"Authentication failed for {hostname}: {str(e)}"
            self.logger.error(error_msg)
            self.stats['failed'] += 1
            return {'hostname': hostname, 'status': 'auth_error', 'error': error_msg}
            
        except NetmikoTimeoutException as e:
            error_msg = f"Connection timeout for {hostname}: {str(e)}"
            self.logger.error(error_msg)
            self.stats['failed'] += 1
            return {'hostname': hostname, 'status': 'timeout_error', 'error': error_msg}
            
        except Exception as e:
            error_msg = f"Unexpected error backing up {hostname}: {str(e)}"
            self.logger.error(error_msg)
            self.stats['failed'] += 1
            return {'hostname': hostname, 'status': 'error', 'error': error_msg}
    
    def backup_multiple_devices(self, devices, max_workers=5):
        """
        Backup multiple devices concurrently
        
        Args:
            devices (list): List of device dictionaries
            max_workers (int): Maximum concurrent connections
            
        Returns:
            list: List of backup results
        """
        self.stats['total_devices'] = len(devices)
        self.logger.info(f"Starting backup for {len(devices)} devices")
        
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_device = {executor.submit(self.backup_device_config, device): device 
                              for device in devices}
            
            for future in concurrent.futures.as_completed(future_to_device):
                result = future.result()
                results.append(result)
        
        return results
    
    def compare_configs(self, hostname, config1_timestamp, config2_timestamp):
        """
        Compare two configuration versions for a device
        
        Args:
            hostname (str): Device hostname
            config1_timestamp (str): First config timestamp
            config2_timestamp (str): Second config timestamp
            
        Returns:
            str: Diff output or error message
        """
        device_dir = self.backup_dir / hostname
        
        config1_path = device_dir / f"{hostname}_config_{config1_timestamp}.txt"
        config2_path = device_dir / f"{hostname}_config_{config2_timestamp}.txt"
        
        if not config1_path.exists():
            return f"Error: Config file for {config1_timestamp} not found"
        if not config2_path.exists():
            return f"Error: Config file for {config2_timestamp} not found"
        
        try:
            with open(config1_path, 'r') as f:
                config1_lines = f.readlines()
            with open(config2_path, 'r') as f:
                config2_lines = f.readlines()
            
            diff = difflib.unified_diff(
                config1_lines,
                config2_lines,
                fromfile=f"{hostname}_{config1_timestamp}",
                tofile=f"{hostname}_{config2_timestamp}",
                lineterm=''
            )
            
            return '\n'.join(diff)
            
        except Exception as e:
            return f"Error comparing configs: {str(e)}"
    
    def get_backup_report(self):
        """Generate backup operation report"""
        duration = datetime.now() - self.stats['start_time']
        
        report = {
            'summary': {
                'total_devices': self.stats['total_devices'],
                'successful': self.stats['successful'],
                'failed': self.stats['failed'],
                'success_rate': f"{(self.stats['successful']/self.stats['total_devices']*100):.1f}%" 
                             if self.stats['total_devices'] > 0 else "0%",
                'duration': str(duration).split('.')[0]  # Remove microseconds
            },
            'timestamp': datetime.now().isoformat()
        }
        
        return report
    
    def cleanup_old_backups(self, hostname, keep_days=30):
        """
        Clean up old backup files
        
        Args:
            hostname (str): Device hostname
            keep_days (int): Days to retain backups
        """
        device_dir = self.backup_dir / hostname
        if not device_dir.exists():
            return
        
        cutoff_date = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
        
        for file_path in device_dir.glob(f"{hostname}_config_*.txt"):
            if file_path.stat().st_mtime < cutoff_date:
                file_path.unlink()
                self.logger.info(f"Cleaned up old backup: {file_path}")


def main():
    """Main execution function with CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Cisco Configuration Backup Manager')
    parser.add_argument('--device', help='Single device hostname to backup')
    parser.add_argument('--all', action='store_true', help='Backup all devices from config')
    parser.add_argument('--compare', nargs=3, help='Compare configs: hostname timestamp1 timestamp2')
    parser.add_argument('--cleanup', nargs=2, help='Cleanup old backups: hostname days_to_keep')
    parser.add_argument('--workers', type=int, default=5, help='Max concurrent connections')
    
    args = parser.parse_args()
    
    backup_manager = CiscoBackupManager()
    
    if args.compare:
        hostname, ts1, ts2 = args.compare
        diff_output = backup_manager.compare_configs(hostname, ts1, ts2)
        print(diff_output)
        return
    
    if args.cleanup:
        hostname, days = args.cleanup
        backup_manager.cleanup_old_backups(hostname, int(days))
        return
    
    # Get devices from config
    try:
        if args.device:
            # Backup single device
            devices = [d for d in config.DEVICES if d.get('hostname', d['host']) == args.device]
            if not devices:
                print(f"Device {args.device} not found in config")
                return
        elif args.all:
            # Backup all devices
            devices = config.DEVICES
        else:
            print("Please specify --device <hostname> or --all")
            return
            
    except AttributeError:
        print("Error: DEVICES list not found in config.py")
        return
    
    # Perform backups
    results = backup_manager.backup_multiple_devices(devices, args.workers)
    
    # Display results
    print("\n" + "="*60)
    print("BACKUP OPERATION SUMMARY")
    print("="*60)
    
    for result in results:
        status_symbol = "✅" if result['status'] == 'success' else "❌"
        print(f"{status_symbol} {result['hostname']}: {result['status']}")
        
        if result['status'] == 'success':
            print(f"   📁 Config: {result['config_file']}")
            print(f"   📊 Size: {result['config_size']} bytes")
        else:
            print(f"   ⚠️  Error: {result.get('error', 'Unknown error')}")
    
    # Final report
    report = backup_manager.get_backup_report()
    print(f"\n📈 Success Rate: {report['summary']['success_rate']}")
    print(f"⏱️  Duration: {report['summary']['duration']}")
    print(f"📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
