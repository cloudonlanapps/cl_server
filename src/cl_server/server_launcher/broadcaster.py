import json
import subprocess
import threading
import time
from typing import Dict, Optional, Any

import requests
from loguru import logger
from cl_ml_tools import get_broadcaster

class HealthBroadcaster:
    def __init__(
        self,
        auth_url: str,
        store_url: str,
        compute_url: str,
        mqtt_url: str,
        store_port: int,
        capability_topic_prefix: str,
        host_port: int,
        expected_worker_ids: list[str],
        interval: float = 5.0,
        service_name: str = "server100@cloudonlapapps",
        service_type: str = "_http._tcp",
        txt_record: str = "desc=CL Image Repo Service",
    ):
        self.auth_url = auth_url
        self.store_url = store_url
        self.compute_url = compute_url
        self.mqtt_url = mqtt_url
        self.store_port = store_port
        self.capability_topic_prefix = capability_topic_prefix
        self.host_port = host_port
        self.expected_worker_ids = set(expected_worker_ids)
        self.check_interval = interval
        self.service_name = service_name
        self.service_type = service_type
        self.txt_record = txt_record

        self.running = False
        self.broadcast_process: Optional[subprocess.Popen[Any]] = None
        self.health_status: Dict[str, bool] = {
            "auth": False,
            "store": False,
            "compute": False,
            "m_insight": False,
        }
        # Initialize worker status for each expected worker
        for worker_id in self.expected_worker_ids:
            self.health_status[f"worker:{worker_id}"] = False

        self.last_heartbeat: Dict[str, float] = {
            "m_insight": 0,
        }
        # Initialize worker heartbeats
        for worker_id in self.expected_worker_ids:
            self.last_heartbeat[f"worker:{worker_id}"] = 0

        self.mqtt_client: Any = None
        self._lock = threading.Lock()

    def start(self):
        self.running = True
        
        # Start MQTT listener
        self._start_mqtt_listener()

        # Start health check loop
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info(f"Health Broadcaster started (monitoring workers: {self.expected_worker_ids})")

    def stop(self):
        self.running = False
        if self.broadcast_process:
            self.broadcast_process.terminate()
            self.broadcast_process = None
        if self.mqtt_client:
             # Best effort disconnect, though cl_ml_tools wrapper might not expose it directly or easily
             try:
                 self.mqtt_client.loop_stop()
             except Exception:
                 pass

    def _start_mqtt_listener(self):
        try:
            broadcaster = get_broadcaster(url=self.mqtt_url)
            if hasattr(broadcaster, "client"):
                self.mqtt_client = broadcaster.client
                
                # Subscribe to m_insight status
                m_insight_topic = f"mInsight/{self.store_port}/status"
                self.mqtt_client.subscribe(m_insight_topic)
                
                # Subscribe to worker capabilities
                worker_topic = f"{self.capability_topic_prefix}/+"
                self.mqtt_client.subscribe(worker_topic)

                self.mqtt_client.on_message = self._on_mqtt_message
                self.mqtt_client.loop_start()
                logger.info(f"Subscribed to MQTT topics: {m_insight_topic}, {worker_topic}")
            else:
                 logger.error("Failed to get underlying MQTT client from broadcaster")
        except Exception as e:
            logger.error(f"Failed to start MQTT listener: {e}")

    def _on_mqtt_message(self, client: Any, userdata: Any, msg: Any):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            timestamp = time.time()

            with self._lock:
                if "mInsight" in topic:
                    # Update m_insight heartbeat
                    # We consider it healthy if status is "running" or "idle"
                    status = payload.get("status")
                    if status in ["running", "idle"]:
                         self.last_heartbeat["m_insight"] = timestamp
                elif self.capability_topic_prefix in topic:
                     # Update worker heartbeat
                     worker_id = payload.get("worker_id")
                     if worker_id in self.expected_worker_ids:
                         self.last_heartbeat[f"worker:{worker_id}"] = timestamp
                     else:
                         # Log unexpected worker? Or ignore
                         pass

        except Exception as e:
            logger.debug(f"Error processing MQTT message: {e}")

    def _check_http(self, url: str) -> bool:
        try:
            response = requests.get(url, timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def _check_mqtt_heartbeats(self):
        now = time.time()
        timeout = 30.0 # 30 seconds timeout for heartbeats

        with self._lock:
            # Check m_insight
            self.health_status["m_insight"] = (now - self.last_heartbeat["m_insight"]) < timeout
            
            # Check workers
            for worker_id in self.expected_worker_ids:
                key = f"worker:{worker_id}"
                self.health_status[key] = (now - self.last_heartbeat.get(key, 0)) < timeout

    def _update_broadcast(self):
        is_healthy = all(self.health_status.values())
        
        # Prepare broadcast command
        # Base command with service details
        cmd = [
            "dns-sd", 
            "-R", 
            self.service_name, 
            self.service_type, 
            "local", 
            str(self.host_port), 
            self.txt_record
        ]
        
        # Add service URLs as additional TXT records
        cmd.append(f"auth_url={self.auth_url}")
        cmd.append(f"store_url={self.store_url}")
        cmd.append(f"compute_url={self.compute_url}")
        cmd.append(f"mqtt_url={self.mqtt_url}")

        if not is_healthy:
             # Find unhealthy services
             unhealthy = [k for k, v in self.health_status.items() if not v]
             cmd.append("status=unhealthy")
             cmd.append(f"error={','.join(unhealthy)}")
        
        # Check if we need to restart broadcast
        # For simplicity, we can restart it if the command args change (which implies content change)
        # But to avoid constant restarting, we store the last broadcast command signature
        
        current_cmd_str = str(cmd)
        
        if not hasattr(self, "_last_broadcast_cmd"):
            self._last_broadcast_cmd = None
            
        if self._last_broadcast_cmd != current_cmd_str:
            logger.info(f"Broadcasting status change: {cmd}")
            if self.broadcast_process:
                self.broadcast_process.terminate()
                self.broadcast_process.wait()
            
            # Start new broadcast
            try:
                self.broadcast_process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
            except Exception as e:
                logger.error(f"Failed to start broadcast process: {e}")
                
            self._last_broadcast_cmd = current_cmd_str

    def _run_loop(self):
        while self.running:
            # HTTP Checks
            self.health_status["auth"] = self._check_http(f"{self.auth_url}/health")
            # Store and Compute might have different health endpoints or just root
            # Based on inspection, they often use / or /health. Let's assume /health or /docs or verify with user?
            # User said "just by getting the root url". Let's stick to that for now or try / if /health fails?
            # Actually user said "getting the root url of each server".
            self.health_status["auth"] = self._check_http(self.auth_url) 
            self.health_status["store"] = self._check_http(self.store_url)
            self.health_status["compute"] = self._check_http(self.compute_url)
            
            # MQTT Checks
            self._check_mqtt_heartbeats()
            
            # Log status
            logger.debug(f"Health Status: {self.health_status}")
            
            # Update Broadcast
            self._update_broadcast()
            
            time.sleep(self.check_interval)
