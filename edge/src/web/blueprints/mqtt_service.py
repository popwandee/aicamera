#!/usr/bin/env python3
"""
MQTT Service Blueprint for AI Camera Edge.

Provides MQTT service dashboard and status API for monitoring connection
and data sending via MQTT (broker port 1883, topics per plan).
"""

import time
from datetime import datetime

from flask import Blueprint, render_template, jsonify
from edge.src.core.dependency_container import get_service
from edge.src.core.utils.logging_config import get_logger
from edge.src.core.config_communication import (
    MQTT_ENABLED,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    MQTT_TOPIC_PREFIX,
)

mqtt_service_bp = Blueprint("mqtt_service", __name__, url_prefix="/mqtt-service")
logger = get_logger(__name__)


@mqtt_service_bp.route("/")
def mqtt_service_dashboard():
    """Render MQTT Service dashboard."""
    try:
        return render_template(
            "mqtt_service/dashboard.html",
            active_page="mqtt_service",
            title="MQTT Service",
            timestamp=int(time.time()),
        )
    except Exception as e:
        logger.error("Error rendering MQTT service dashboard: %s", e)
        return "MQTT service dashboard not available", 500


@mqtt_service_bp.route("/status")
def get_mqtt_service_status():
    """
    Get MQTT service status (connection and sending info).

    Returns:
        JSON with success, status (enabled, running, connected, device_id,
        total_health_sent, thread_alive), and broker_url for display.
    """
    try:
        broker_url = f"mqtt://{MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}"
        try:
            mqtt_sender = get_service("mqtt_health_sender")
        except Exception:
            mqtt_sender = None
        if not mqtt_sender:
            return jsonify({
                "success": False,
                "error": "MQTT health sender service not available",
                "status": {
                    "enabled": MQTT_ENABLED,
                    "running": False,
                    "connected": False,
                    "device_id": "",
                    "total_health_sent": 0,
                    "thread_alive": False,
                    "broker_url": broker_url,
                },
                "timestamp": datetime.now().isoformat(),
            }), 200
        status = mqtt_sender.get_status()
        status["broker_url"] = broker_url
        status["topic_prefix"] = MQTT_TOPIC_PREFIX
        response = jsonify({
            "success": True,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        })
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        logger.error("Error getting MQTT service status: %s", e)
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }), 500
