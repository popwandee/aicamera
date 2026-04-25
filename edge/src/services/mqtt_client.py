import paho.mqtt.client as mqtt
import json
import logging
import time
from typing import Optional, Callable

class MQTTClient:
    def __init__(self, host='localhost', port=1883, topic_prefix='aicamera/edge', client_id=None):
        self.host = host
        self.port = port
        self.topic_prefix = topic_prefix
        self.client_id = client_id or f"edge-{int(time.time())}"
        self.client = mqtt.Client(client_id=self.client_id)
        self.connected = False
        self.setup_callbacks()
        
    def setup_callbacks(self):
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_publish = self.on_publish
        self.client.on_message = self.on_message
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logging.info(f"Connected to MQTT broker at {self.host}:{self.port}")
            # Subscribe to relevant topics
            self.client.subscribe(f"{self.topic_prefix}/+/command")
        else:
            logging.error(f"Failed to connect to MQTT broker, return code: {rc}")
            
    def on_disconnect(self, client, userdata, rc):
        self.connected = False
        logging.info("Disconnected from MQTT broker")
        
    def on_publish(self, client, userdata, mid):
        logging.debug(f"Message published with ID: {mid}")
        
    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            logging.info(f"Received message on {msg.topic}: {payload}")
        except json.JSONDecodeError:
            logging.warning(f"Received non-JSON message on {msg.topic}")
            
    def connect(self):
        try:
            self.client.connect(self.host, self.port, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            logging.error(f"Failed to connect to MQTT broker: {e}")
            return False
            
    def disconnect(self):
        if self.connected:
            self.client.loop_stop()
            self.client.disconnect()
            
    def publish_detection(self, device_id: str, detection_data: dict) -> bool:
        if not self.connected:
            logging.error("Not connected to MQTT broker")
            return False
            
        topic = f"{self.topic_prefix}/{device_id}/detection"
        message = json.dumps(detection_data)
        result = self.client.publish(topic, message, qos=1)
        return result.rc == 0
        
    def publish_heartbeat(self, device_id: str, status: str = "online") -> bool:
        if not self.connected:
            return False
            
        topic = f"{self.topic_prefix}/{device_id}/heartbeat"
        message = json.dumps({
            "status": status,
            "timestamp": time.time(),
            "device_id": device_id
        })
        result = self.client.publish(topic, message, qos=0)
        return result.rc == 0

    def publish_health(self, device_id: str, payload: dict) -> bool:
        """Publish health status to topic aicamera/device/{device_id}/health (QoS 1)."""
        if not self.connected:
            logging.error("Not connected to MQTT broker")
            return False
        topic = f"camera/{device_id}/health"
        message = json.dumps(payload)
        result = self.client.publish(topic, message, qos=1)
        return result.rc == 0
