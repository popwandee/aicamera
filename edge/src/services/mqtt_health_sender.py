#!/usr/bin/env python3
"""
MQTT Health Sender Service for AI Camera Edge.

Sends unsent health check records from the database to the server via MQTT
on a configurable interval. Used when health status is sent over MQTT instead of WebSocket.

Author: AI Camera Team
"""

import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional

from edge.src.core.config import AICAMERA_ID, CHECKPOINT_ID, HEALTH_SENDER_INTERVAL
from edge.src.core.config_communication import (
    MQTT_ENABLED,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    MQTT_TOPIC_PREFIX,
    MQTT_CLIENT_ID,
)


def create_mqtt_health_sender(database_manager=None, logger=None) -> "MqttHealthSender":
    """Factory for MqttHealthSender with optional dependencies."""
    return MqttHealthSender(database_manager=database_manager, logger=logger)


class MqttHealthSender:
    """
    Sends health check records to server via MQTT.
    Runs a single thread that periodically fetches unsent health checks and publishes them.
    """

    def __init__(self, database_manager=None, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.database_manager = database_manager
        self._mqtt_client = None
        self._thread = None
        self._running = False
        self._stop_event = threading.Event()
        self._device_id = AICAMERA_ID
        self._checkpoint_id = CHECKPOINT_ID
        self._total_sent = 0

    def initialize(self) -> bool:
        """Initialize the sender. Returns True if MQTT is enabled and dependencies are available."""
        if not MQTT_ENABLED:
            self.logger.info("MQTT Health Sender disabled (MQTT_ENABLED=false)")
            return False
        if not self.database_manager:
            try:
                from edge.src.core.dependency_container import get_service
                self.database_manager = get_service("database_manager")
            except Exception:
                pass
        if not self.database_manager:
            self.logger.error("MQTT Health Sender: database manager not available")
            return False
        self.logger.info("MQTT Health Sender initialized (device_id=%s)", self._device_id)
        return True

    def start(self) -> bool:
        """Start the health sender thread and MQTT connection."""
        if not MQTT_ENABLED:
            return False
        if self._running:
            self.logger.warning("MQTT Health Sender already running")
            return True
        if not self.initialize():
            return False
        try:
            from edge.src.services.mqtt_client import MQTTClient
            self._mqtt_client = MQTTClient(
                host=MQTT_BROKER_HOST,
                port=int(MQTT_BROKER_PORT),
                topic_prefix=MQTT_TOPIC_PREFIX,
                client_id=MQTT_CLIENT_ID or f"mqtt-health-{self._device_id}-{id(self)}",
            )
            if not self._mqtt_client.connect():
                self.logger.warning("MQTT Health Sender: broker connection failed; will retry in thread")
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._sender_loop,
                name="MQTT-Health-Sender",
                daemon=True,
            )
            self._thread.start()
            self.logger.info("MQTT Health Sender started (interval=%ss)", HEALTH_SENDER_INTERVAL)
            return True
        except Exception as e:
            self.logger.error("MQTT Health Sender start failed: %s", e)
            return False

    def stop(self):
        """Stop the health sender thread and disconnect MQTT."""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        if self._mqtt_client:
            try:
                self._mqtt_client.disconnect()
            except Exception as e:
                self.logger.debug("MQTT disconnect: %s", e)
            self._mqtt_client = None
        self.logger.info("MQTT Health Sender stopped")

    def _sender_loop(self):
        while self._running and not self._stop_event.is_set():
            try:
                sent = self._send_health_data()
                if sent > 0:
                    self._total_sent += sent
                    self.logger.info("Sent %d health record(s) via MQTT", sent)
            except Exception as e:
                self.logger.error("MQTT Health Sender loop error: %s", e)
            if self._stop_event.wait(HEALTH_SENDER_INTERVAL):
                break
        self.logger.info("MQTT Health Sender thread stopped")

    def _send_health_data(self) -> int:
        """Fetch unsent health checks, publish via MQTT, mark sent. Returns count sent."""
        if not self.database_manager or not self._mqtt_client:
            return 0
        unsent = self.database_manager.get_unsent_health_checks()
        if not unsent:
            return 0
        if not self._mqtt_client.connected:
            try:
                self._mqtt_client.connect()
            except Exception:
                pass
        if not self._mqtt_client.connected:
            return 0
        sent_count = 0
        for rec in unsent:
            payload = {
                "type": "health_check",
                "aicamera_id": self._device_id,
                "checkpoint_id": self._checkpoint_id,
                "timestamp": rec["timestamp"],
                "component": rec["component"],
                "status": rec["status"],
                "message": rec["message"],
                "details": rec.get("details") or "{}",
                "created_at": rec["created_at"],
            }
            if self._mqtt_client.publish_health(self._device_id, payload):
                self.database_manager.mark_health_check_sent(
                    rec["id"], "Sent via MQTT"
                )
                sent_count += 1
            else:
                self.logger.warning("MQTT publish_health failed for record id=%s", rec.get("id"))
        return sent_count

    def get_status(self) -> Dict[str, Any]:
        """Return current status for dashboards."""
        return {
            "enabled": MQTT_ENABLED,
            "running": self._running,
            "connected": self._mqtt_client.connected if self._mqtt_client else False,
            "device_id": self._device_id,
            "total_health_sent": self._total_sent,
            "thread_alive": self._thread.is_alive() if self._thread else False,
        }
