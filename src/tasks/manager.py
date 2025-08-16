#!/usr/bin/env python3
"""
Task Management Module
Handles async operations and task tracking for Redfish server.
"""

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages async tasks for Redfish operations"""
    
    def __init__(self):
        self.tasks = {}
        self.task_lock = threading.Lock()
        self._running = True
        self._start_task_manager()
        logger.info("🎯 Task manager initialized")
    
    def _start_task_manager(self):
        """Start the task management thread"""
        def task_manager():
            """Background task manager"""
            logger.info("🔄 Task manager thread started")
            
            while self._running:
                try:
                    # Clean up completed tasks older than 1 hour
                    current_time = time.time()
                    with self.task_lock:
                        completed_tasks = []
                        for task_id, task in self.tasks.items():
                            if (task['TaskState'] in ['Completed', 'Exception', 'Killed', 'Cancelled'] and 
                                current_time - task.get('EndTime', current_time) > 3600):
                                completed_tasks.append(task_id)
                        
                        for task_id in completed_tasks:
                            logger.debug(f"🧹 Cleaning up completed task: {task_id}")
                            del self.tasks[task_id]
                    
                    # Sleep for 30 seconds
                    time.sleep(30)
                    
                except Exception as e:
                    logger.error(f"❌ Task manager error: {e}")
                    time.sleep(5)
        
        # Start the task manager thread
        task_thread = threading.Thread(target=task_manager, daemon=True)
        task_thread.start()
        
        # Create some initial tasks for Metal3 compatibility
        self._create_initial_tasks()
    
    def _create_initial_tasks(self):
        """Create initial tasks that Metal3/Ironic expects to see"""
        logger.info("🎬 Creating initial tasks for Metal3/Ironic compatibility")
        
        # System initialization task
        self.create_task(
            'SystemInitialization',
            'System Initialization',
            'Initializing Redfish VMware Server for Metal3/Ironic compatibility'
        )
        
        # BIOS configuration task
        self.create_task(
            'BIOSConfiguration',
            'BIOS Configuration',
            'Configuring BIOS settings for secure boot and firmware management'
        )
        
        # Power management task
        self.create_task(
            'PowerManagement',
            'Power Management Initialization',
            'Initializing power management subsystem'
        )
        
        # Mark initial tasks as completed
        time.sleep(0.1)  # Small delay to ensure different timestamps
        
        for task_id in list(self.tasks.keys()):
            self.complete_task(task_id, 'Initial setup completed successfully')
    
    def create_task(self, task_type: str, name: str, description: str = None) -> str:
        """
        Create a new task
        
        Args:
            task_type: Type of task
            name: Task name
            description: Task description
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        current_time = time.time()
        
        task = {
            '@odata.type': '#Task.v1_4_3.Task',
            '@odata.id': f'/redfish/v1/TaskService/Tasks/{task_id}',
            'Id': task_id,
            'Name': name,
            'Description': description or f'{task_type} task',
            'TaskState': 'Running',
            'TaskStatus': 'OK',
            'PercentComplete': 0,
            'StartTime': datetime.fromtimestamp(current_time, tz=timezone.utc).isoformat(),
            'TaskType': task_type,
            'Messages': []
        }
        
        with self.task_lock:
            self.tasks[task_id] = task
        
        logger.info(f"📝 Created task: {name} (ID: {task_id})")
        return task_id
    
    def update_task_progress(self, task_id: str, percent_complete: int, message: str = None):
        """Update task progress"""
        with self.task_lock:
            if task_id in self.tasks:
                self.tasks[task_id]['PercentComplete'] = percent_complete
                if message:
                    self.tasks[task_id]['Messages'].append({
                        'MessageId': 'TaskProgress',
                        'Message': message,
                        'Severity': 'OK',
                        'Timestamp': datetime.now(tz=timezone.utc).isoformat()
                    })
                logger.debug(f"📊 Task {task_id} progress: {percent_complete}%")
    
    def complete_task(self, task_id: str, message: str = None, success: bool = True):
        """Mark task as completed"""
        with self.task_lock:
            if task_id in self.tasks:
                self.tasks[task_id]['TaskState'] = 'Completed' if success else 'Exception'
                self.tasks[task_id]['TaskStatus'] = 'OK' if success else 'Critical'
                self.tasks[task_id]['PercentComplete'] = 100
                self.tasks[task_id]['EndTime'] = datetime.now(tz=timezone.utc).isoformat()
                
                if message:
                    self.tasks[task_id]['Messages'].append({
                        'MessageId': 'TaskCompleted' if success else 'TaskFailed',
                        'Message': message,
                        'Severity': 'OK' if success else 'Critical',
                        'Timestamp': datetime.now(tz=timezone.utc).isoformat()
                    })
                
                logger.info(f"✅ Task completed: {task_id} - {message or 'Success'}")
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get task by ID"""
        with self.task_lock:
            return self.tasks.get(task_id)
    
    def list_tasks(self) -> Dict:
        """List all tasks"""
        with self.task_lock:
            return {
                '@odata.type': '#TaskCollection.TaskCollection',
                '@odata.id': '/redfish/v1/TaskService/Tasks',
                'Name': 'Task Collection',
                'Description': 'Collection of Tasks',
                'Members@odata.count': len(self.tasks),
                'Members': [
                    {
                        '@odata.id': f'/redfish/v1/TaskService/Tasks/{task_id}'
                    }
                    for task_id in self.tasks.keys()
                ]
            }
    
    def get_task_service(self) -> Dict:
        """Get TaskService information"""
        return {
            '@odata.type': '#TaskService.v1_1_4.TaskService',
            '@odata.id': '/redfish/v1/TaskService',
            'Id': 'TaskService',
            'Name': 'Task Service',
            'Description': 'Task Service for Redfish VMware Server',
            'Status': {
                'State': 'Enabled',
                'Health': 'OK'
            },
            'ServiceEnabled': True,
            'CompletedTaskOverWritePolicy': 'Oldest',
            'LifeCycleEventOnTaskStateChange': True,
            'Tasks': {
                '@odata.id': '/redfish/v1/TaskService/Tasks'
            }
        }
    
    def shutdown(self):
        """Shutdown task manager"""
        logger.info("🛑 Shutting down task manager")
        self._running = False
