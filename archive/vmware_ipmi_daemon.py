#!/usr/bin/env python3
"""
VMware IPMI BMC Daemon
Production daemon for VMware IPMI BMC Server
"""

import os
import sys
import time
import signal
import logging
import subprocess
from pathlib import Path

# Configuration
DAEMON_NAME = "vmware-ipmi-bmc"
PID_FILE = f"/var/run/{DAEMON_NAME}.pid"
LOG_FILE = f"/var/log/{DAEMON_NAME}.log"
WORK_DIR = "/home/lchiaret/git/ipmi-vmware"
PYTHON_SCRIPT = "vmware_ipmi_bmc.py"

class VMwareIPMIDaemon:
    """Daemon for VMware IPMI BMC"""
    
    def __init__(self):
        self.pid_file = PID_FILE
        self.log_file = LOG_FILE
        self.work_dir = WORK_DIR
        self.python_script = PYTHON_SCRIPT
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('vmware_ipmi_daemon')
    
    def daemonize(self):
        """Daemonize process using double fork"""
        try:
            # First fork
            pid = os.fork()
            if pid > 0:
                sys.exit(0)  # Exit parent
        except OSError as e:
            self.logger.error(f"Fork #1 failed: {e}")
            sys.exit(1)
        
        # Decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)
        
        try:
            # Second fork
            pid = os.fork()
            if pid > 0:
                sys.exit(0)  # Exit first child
        except OSError as e:
            self.logger.error(f"Fork #2 failed: {e}")
            sys.exit(1)
        
        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        
        with open('/dev/null', 'r') as si:
            os.dup2(si.fileno(), sys.stdin.fileno())
        with open('/dev/null', 'a+') as so:
            os.dup2(so.fileno(), sys.stdout.fileno())
        with open('/dev/null', 'a+') as se:
            os.dup2(se.fileno(), sys.stderr.fileno())
        
        # Write PID file
        self.write_pid()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def write_pid(self):
        """Write PID to file"""
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
        except Exception as e:
            self.logger.error(f"Failed to write PID file: {e}")
            sys.exit(1)
    
    def read_pid(self):
        """Read PID from file"""
        try:
            with open(self.pid_file, 'r') as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return None
    
    def remove_pid(self):
        """Remove PID file"""
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
        except Exception as e:
            self.logger.error(f"Failed to remove PID file: {e}")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def is_running(self):
        """Check if daemon is running"""
        pid = self.read_pid()
        if pid is None:
            return False
        
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    
    def start(self):
        """Start the daemon"""
        if self.is_running():
            self.logger.error("Daemon is already running")
            return False
        
        self.logger.info("Starting VMware IPMI BMC Daemon...")
        
        # Create directories if needed
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        os.makedirs(os.path.dirname(self.pid_file), exist_ok=True)
        
        # Daemonize
        self.daemonize()
        
        # Run the main process
        self.run()
    
    def stop(self):
        """Stop the daemon"""
        pid = self.read_pid()
        if pid is None:
            self.logger.error("PID file not found, daemon may not be running")
            return False
        
        try:
            # Try graceful shutdown first
            os.kill(pid, signal.SIGTERM)
            
            # Wait up to 10 seconds for shutdown
            for _ in range(100):
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except OSError:
                    break
            else:
                # Force kill if still running
                self.logger.warning("Forcing daemon shutdown...")
                os.kill(pid, signal.SIGKILL)
            
            self.remove_pid()
            self.logger.info("Daemon stopped")
            return True
            
        except OSError as e:
            self.logger.error(f"Failed to stop daemon: {e}")
            return False
    
    def restart(self):
        """Restart the daemon"""
        self.logger.info("Restarting daemon...")
        self.stop()
        time.sleep(1)
        self.start()
    
    def status(self):
        """Check daemon status"""
        if self.is_running():
            pid = self.read_pid()
            print(f"VMware IPMI BMC Daemon is running (PID: {pid})")
            return True
        else:
            print("VMware IPMI BMC Daemon is not running")
            return False
    
    def run(self):
        """Main daemon process"""
        self.logger.info("VMware IPMI BMC Daemon started")
        
        # Change to work directory
        os.chdir(self.work_dir)
        
        # Start the Python script with restart on failure
        restart_count = 0
        max_restarts = 5
        
        while restart_count < max_restarts:
            try:
                self.logger.info(f"Starting IPMI BMC server (attempt {restart_count + 1})")
                
                # Run the Python script
                process = subprocess.Popen([
                    'python3', self.python_script
                ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                   universal_newlines=True)
                
                # Monitor the process
                for line in process.stdout:
                    self.logger.info(f"BMC: {line.strip()}")
                
                # Process ended
                return_code = process.wait()
                self.logger.warning(f"IPMI BMC server exited with code {return_code}")
                
                if return_code == 0:
                    # Clean exit, don't restart
                    break
                
                restart_count += 1
                if restart_count < max_restarts:
                    self.logger.info(f"Restarting in 5 seconds... ({restart_count}/{max_restarts})")
                    time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Failed to start IPMI BMC server: {e}")
                restart_count += 1
                if restart_count < max_restarts:
                    time.sleep(5)
        
        self.logger.error("Max restart attempts reached. Daemon stopping.")
        self.remove_pid()

def main():
    """Main function"""
    daemon = VMwareIPMIDaemon()
    
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} {{start|stop|restart|status}}")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'start':
        daemon.start()
    elif command == 'stop':
        daemon.stop()
    elif command == 'restart':
        daemon.restart()
    elif command == 'status':
        daemon.status()
    else:
        print(f"Unknown command: {command}")
        print(f"Usage: {sys.argv[0]} {{start|stop|restart|status}}")
        sys.exit(1)

if __name__ == "__main__":
    main()
