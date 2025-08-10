#!/usr/bin/env python3
"""
Database Manager Component for AI Camera v1.3

This component provides database operations for storing detection results
and managing application data using SQLite database.

Features:
- SQLite database connection management
- Detection results storage and retrieval
- Database schema creation and maintenance
- Query execution and error handling

Author: AI Camera Team
Version: 1.3
Date: August 2025
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from v1_3.src.core.utils.logging_config import get_logger
from v1_3.src.core.config import DATABASE_PATH

logger = get_logger(__name__)


class DatabaseManager:
    """
    Database Manager Component for managing application data storage.
    
    This component handles:
    - Database connection and initialization
    - Detection results storage and retrieval
    - Database schema management
    - Data serialization and cleanup
    """
    
    def __init__(self, logger=None):
        """
        Initialize Database Manager.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger or get_logger(__name__)
        self.database_path = DATABASE_PATH
        self.connection = None
        
        self.logger.info("DatabaseManager initialized")
    
    def initialize(self) -> bool:
        """
        Initialize the database connection and create tables.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Create database directory if it doesn't exist
            if self.database_path:
                Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Connect to database
            self.connection = sqlite3.connect(self.database_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row  # Enable column access by name
            
            # Create tables
            self._create_tables()
            
            self.logger.info(f"Database initialized successfully: {self.database_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            return False
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        try:
            cursor = self.connection.cursor()
            
            # Detection results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detection_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    vehicles_count INTEGER DEFAULT 0,
                    plates_count INTEGER DEFAULT 0,
                    ocr_results TEXT,
                    annotated_image_path TEXT,
                    cropped_plates_paths TEXT,
                    vehicle_detections TEXT,
                    plate_detections TEXT,
                    processing_time_ms REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    sent_to_server BOOLEAN DEFAULT 0,
                    sent_at DATETIME,
                    server_response TEXT
                )
            """)
            
            # System events table for logging
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    event_data TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Configuration table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS configuration (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Health checks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS health_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    component TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    details TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    sent_to_server BOOLEAN DEFAULT 0,
                    sent_at DATETIME,
                    server_response TEXT
                )
            """)
            
            # WebSocket sender logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS websocket_sender_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    data_type TEXT,
                    record_count INTEGER DEFAULT 0,
                    server_response TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.connection.commit()
            self.logger.info("Database tables created successfully")
            
        except Exception as e:
            self.logger.error(f"Error creating database tables: {e}")
            raise
    
    def insert_detection_result(self, detection_data: Dict[str, Any]) -> Optional[int]:
        """
        Insert detection result into database.
        
        Args:
            detection_data: Dictionary containing detection results
            
        Returns:
            Optional[int]: ID of inserted record, None if failed
        """
        try:
            if not self.connection:
                self.logger.error("Database connection not available")
                return None
            
            cursor = self.connection.cursor()
            
            # Serialize complex data to JSON
            ocr_results_json = json.dumps(detection_data.get('ocr_results', []))
            cropped_paths_json = json.dumps(detection_data.get('cropped_plates_paths', []))
            vehicle_detections_json = json.dumps(detection_data.get('vehicle_detections', []))
            plate_detections_json = json.dumps(detection_data.get('plate_detections', []))
            
            cursor.execute("""
                INSERT INTO detection_results (
                    timestamp, vehicles_count, plates_count, ocr_results,
                    annotated_image_path, cropped_plates_paths,
                    vehicle_detections, plate_detections, processing_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                detection_data.get('timestamp'),
                detection_data.get('vehicles_count', 0),
                detection_data.get('plates_count', 0),
                ocr_results_json,
                detection_data.get('annotated_image_path', ''),
                cropped_paths_json,
                vehicle_detections_json,
                plate_detections_json,
                detection_data.get('processing_time_ms', 0.0)
            ))
            
            self.connection.commit()
            record_id = cursor.lastrowid
            
            self.logger.debug(f"Detection result inserted with ID: {record_id}")
            return record_id
            
        except Exception as e:
            self.logger.error(f"Error inserting detection result: {e}")
            return None
    
    def get_recent_detections(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent detection results from database.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List[Dict[str, Any]]: List of detection records
        """
        try:
            if not self.connection:
                self.logger.error("Database connection not available")
                return []
            
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT * FROM detection_results
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            results = []
            
            for row in rows:
                result = {
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'vehicles_count': row['vehicles_count'],
                    'plates_count': row['plates_count'],
                    'annotated_image_path': row['annotated_image_path'],
                    'processing_time_ms': row['processing_time_ms'],
                    'created_at': row['created_at']
                }
                
                # Deserialize JSON fields
                try:
                    result['ocr_results'] = json.loads(row['ocr_results'] or '[]')
                    result['cropped_plates_paths'] = json.loads(row['cropped_plates_paths'] or '[]')
                    result['vehicle_detections'] = json.loads(row['vehicle_detections'] or '[]')
                    result['plate_detections'] = json.loads(row['plate_detections'] or '[]')
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Error deserializing JSON for record {row['id']}: {e}")
                    result['ocr_results'] = []
                    result['cropped_plates_paths'] = []
                    result['vehicle_detections'] = []
                    result['plate_detections'] = []
                
                results.append(result)
            
            self.logger.debug(f"Retrieved {len(results)} recent detection records")
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting recent detections: {e}")
            return []
    
    def get_detection_results_paginated(self, page: int = 1, per_page: int = 20, 
                                      search: str = None, sort_by: str = 'created_at', 
                                      sort_order: str = 'desc', date_from: str = None, 
                                      date_to: str = None, has_vehicles: bool = None, 
                                      has_plates: bool = None) -> Dict[str, Any]:
        """
        Get paginated detection results with search, filter, and sort capabilities.
        
        Args:
            page: Page number (1-based)
            per_page: Number of records per page
            search: Search term for OCR results or plate text
            sort_by: Column to sort by
            sort_order: Sort order ('asc' or 'desc')
            date_from: Start date filter (ISO format)
            date_to: End date filter (ISO format)
            has_vehicles: Filter by presence of vehicles
            has_plates: Filter by presence of license plates
            
        Returns:
            Dict containing results, pagination info, and metadata
        """
        try:
            if not self.connection:
                self.logger.error("Database connection not available")
                return {'results': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}
            
            cursor = self.connection.cursor()
            
            # Build WHERE clause
            where_conditions = []
            params = []
            
            if search:
                where_conditions.append("(ocr_results LIKE ? OR vehicle_detections LIKE ? OR plate_detections LIKE ?)")
                search_term = f"%{search}%"
                params.extend([search_term, search_term, search_term])
            
            if date_from:
                where_conditions.append("date(created_at) >= ?")
                params.append(date_from)
            
            if date_to:
                where_conditions.append("date(created_at) <= ?")
                params.append(date_to)
            
            if has_vehicles is not None:
                if has_vehicles:
                    where_conditions.append("vehicles_count > 0")
                else:
                    where_conditions.append("vehicles_count = 0")
            
            if has_plates is not None:
                if has_plates:
                    where_conditions.append("plates_count > 0")
                else:
                    where_conditions.append("plates_count = 0")
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # Validate sort parameters
            valid_sort_columns = ['id', 'created_at', 'timestamp', 'vehicles_count', 'plates_count', 'processing_time_ms']
            if sort_by not in valid_sort_columns:
                sort_by = 'created_at'
            
            if sort_order.lower() not in ['asc', 'desc']:
                sort_order = 'desc'
            
            # Get total count
            count_query = f"SELECT COUNT(*) as total FROM detection_results {where_clause}"
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']
            
            # Calculate pagination
            offset = (page - 1) * per_page
            total_pages = (total + per_page - 1) // per_page
            
            # Get paginated results
            query = f"""
                SELECT * FROM detection_results 
                {where_clause}
                ORDER BY {sort_by} {sort_order.upper()}
                LIMIT ? OFFSET ?
            """
            
            cursor.execute(query, params + [per_page, offset])
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                result = {
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'vehicles_count': row['vehicles_count'],
                    'plates_count': row['plates_count'],
                    'annotated_image_path': row['annotated_image_path'],
                    'processing_time_ms': row['processing_time_ms'],
                    'created_at': row['created_at']
                }
                
                # Deserialize JSON fields
                try:
                    result['ocr_results'] = json.loads(row['ocr_results'] or '[]')
                    result['cropped_plates_paths'] = json.loads(row['cropped_plates_paths'] or '[]')
                    result['vehicle_detections'] = json.loads(row['vehicle_detections'] or '[]')
                    result['plate_detections'] = json.loads(row['plate_detections'] or '[]')
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Error deserializing JSON for record {row['id']}: {e}")
                    result['ocr_results'] = []
                    result['cropped_plates_paths'] = []
                    result['vehicle_detections'] = []
                    result['plate_detections'] = []
                
                results.append(result)
            
            return {
                'results': results,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
            
        except Exception as e:
            self.logger.error(f"Error getting paginated detection results: {e}")
            return {'results': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}
    
    def get_detection_result_by_id(self, result_id: int) -> Optional[Dict[str, Any]]:
        """
        Get single detection result by ID with full details.
        
        Args:
            result_id: ID of the detection result
            
        Returns:
            Optional[Dict[str, Any]]: Detection result with full details or None
        """
        try:
            if not self.connection:
                self.logger.error("Database connection not available")
                return None
            
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM detection_results WHERE id = ?", (result_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            result = {
                'id': row['id'],
                'timestamp': row['timestamp'],
                'vehicles_count': row['vehicles_count'],
                'plates_count': row['plates_count'],
                'annotated_image_path': row['annotated_image_path'],
                'processing_time_ms': row['processing_time_ms'],
                'created_at': row['created_at']
            }
            
            # Deserialize JSON fields with full details
            try:
                result['ocr_results'] = json.loads(row['ocr_results'] or '[]')
                result['cropped_plates_paths'] = json.loads(row['cropped_plates_paths'] or '[]')
                result['vehicle_detections'] = json.loads(row['vehicle_detections'] or '[]')
                result['plate_detections'] = json.loads(row['plate_detections'] or '[]')
            except json.JSONDecodeError as e:
                self.logger.warning(f"Error deserializing JSON for record {result_id}: {e}")
                result['ocr_results'] = []
                result['cropped_plates_paths'] = []
                result['vehicle_detections'] = []
                result['plate_detections'] = []
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting detection result by ID {result_id}: {e}")
            return None
    
    def get_detection_statistics(self) -> Dict[str, Any]:
        """
        Get detection statistics from database.
        
        Returns:
            Dict[str, Any]: Statistics summary
        """
        try:
            if not self.connection:
                return {}
            
            cursor = self.connection.cursor()
            
            # Get counts
            cursor.execute("SELECT COUNT(*) as total_detections FROM detection_results")
            total_detections = cursor.fetchone()['total_detections']
            
            cursor.execute("SELECT SUM(vehicles_count) as total_vehicles FROM detection_results")
            total_vehicles = cursor.fetchone()['total_vehicles'] or 0
            
            cursor.execute("SELECT SUM(plates_count) as total_plates FROM detection_results")
            total_plates = cursor.fetchone()['total_plates'] or 0
            
            cursor.execute("SELECT AVG(processing_time_ms) as avg_processing_time FROM detection_results")
            avg_processing_time = cursor.fetchone()['avg_processing_time'] or 0
            
            # Get recent activity
            cursor.execute("""
                SELECT timestamp FROM detection_results 
                ORDER BY created_at DESC LIMIT 1
            """)
            last_result = cursor.fetchone()
            last_detection = last_result['timestamp'] if last_result else None
            
            return {
                'total_detections': total_detections,
                'total_vehicles': total_vehicles,
                'total_plates': total_plates,
                'avg_processing_time_ms': round(avg_processing_time, 2),
                'last_detection': last_detection
            }
            
        except Exception as e:
            self.logger.error(f"Error getting detection statistics: {e}")
            return {}
    
    def log_system_event(self, event_type: str, event_data: Any = None):
        """
        Log system event to database.
        
        Args:
            event_type: Type of event (e.g., 'detection_start', 'model_load', etc.)
            event_data: Additional event data
        """
        try:
            if not self.connection:
                return
            
            cursor = self.connection.cursor()
            event_data_json = json.dumps(event_data) if event_data else None
            
            cursor.execute("""
                INSERT INTO system_events (event_type, event_data)
                VALUES (?, ?)
            """, (event_type, event_data_json))
            
            self.connection.commit()
            self.logger.debug(f"System event logged: {event_type}")
            
        except Exception as e:
            self.logger.warning(f"Error logging system event: {e}")
    
    def cleanup_old_records(self, days_to_keep: int = 30):
        """
        Clean up old records from database.
        
        Args:
            days_to_keep: Number of days to keep records
        """
        try:
            if not self.connection:
                return
            
            cursor = self.connection.cursor()
            
            # Clean up old detection results
            cursor.execute("""
                DELETE FROM detection_results 
                WHERE created_at < datetime('now', '-{} days')
            """.format(days_to_keep))
            
            # Clean up old system events
            cursor.execute("""
                DELETE FROM system_events 
                WHERE timestamp < datetime('now', '-{} days')
            """.format(days_to_keep))
            
            self.connection.commit()
            self.logger.info(f"Cleaned up old records older than {days_to_keep} days")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old records: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get database manager status.
        
        Returns:
            Dict[str, Any]: Status information
        """
        try:
            connected = self.connection is not None
            
            # Get database file size if connected
            db_size = 0
            record_count = 0
            
            if connected and Path(self.database_path).exists():
                db_size = Path(self.database_path).stat().st_size
                
                # Get record count
                cursor = self.connection.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM detection_results")
                record_count = cursor.fetchone()['count']
            
            return {
                'connected': connected,
                'database_path': self.database_path,
                'database_size_bytes': db_size,
                'detection_records_count': record_count,
                'last_update': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting database status: {e}")
        return {
                'connected': False,
                'error': str(e),
                'last_update': datetime.now().isoformat()
        }

    
    def insert_health_check_result(self, timestamp: str, component: str, status: str, message: str, details: str = None) -> Optional[int]:
        """
        Insert health check result into database.
        
        Args:
            timestamp: Timestamp of the health check
            component: Component being checked
            status: Status result ('PASS', 'FAIL', 'WARNING')
            message: Status message
            details: Additional details as JSON string
            
        Returns:
            Optional[int]: ID of inserted record, None if failed
        """
        try:
            if not self.connection:
                self.logger.warning("Database connection not available")
                return None
            
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO health_checks (timestamp, component, status, message, details)
                VALUES (?, ?, ?, ?, ?)
            """, (timestamp, component, status, message, details))
            
            self.connection.commit()
            record_id = cursor.lastrowid
            
            self.logger.debug(f"Health check result logged: {component} - {status}")
            return record_id
            
        except Exception as e:
            self.logger.error(f"Error inserting health check result: {e}")
            return None
    
    def get_latest_health_checks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get latest health check results.
        
        Args:
            limit: Number of recent checks to retrieve
            
        Returns:
            List[Dict[str, Any]]: List of health check results
        """
        try:
            if not self.connection:
                return []
            
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT timestamp, component, status, message, details
                FROM health_checks
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            results = []
            
            for row in rows:
                result = {
                    'timestamp': row[0],
                    'component': row[1],
                    'status': row[2],
                    'message': row[3],
                    'details': row[4]
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting latest health checks: {e}")
            return []
    
    def get_unsent_detection_results(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get detection results that haven't been sent to server yet.
        
        Args:
            limit: Maximum number of results to retrieve
            
        Returns:
            List[Dict[str, Any]]: List of unsent detection results
        """
        try:
            if not self.connection:
                return []
            
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT id, timestamp, vehicles_count, plates_count, ocr_results,
                       annotated_image_path, cropped_plates_paths, vehicle_detections,
                       plate_detections, processing_time_ms, created_at
                FROM detection_results
                WHERE sent_to_server = 0
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            results = []
            
            for row in rows:
                result = {
                    'id': row[0],
                    'timestamp': row[1],
                    'vehicles_count': row[2],
                    'plates_count': row[3],
                    'ocr_results': row[4],
                    'annotated_image_path': row[5],
                    'cropped_plates_paths': row[6],
                    'vehicle_detections': row[7],
                    'plate_detections': row[8],
                    'processing_time_ms': row[9],
                    'created_at': row[10]
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting unsent detection results: {e}")
            return []
    
    def get_unsent_health_checks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get health check results that haven't been sent to server yet.
        
        Args:
            limit: Maximum number of results to retrieve
            
        Returns:
            List[Dict[str, Any]]: List of unsent health checks
        """
        try:
            if not self.connection:
                return []
            
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT id, timestamp, component, status, message, details, created_at
                FROM health_checks
                WHERE sent_to_server = 0
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            results = []
            
            for row in rows:
                result = {
                    'id': row[0],
                    'timestamp': row[1],
                    'component': row[2],
                    'status': row[3],
                    'message': row[4],
                    'details': row[5],
                    'created_at': row[6]
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting unsent health checks: {e}")
            return []
    
    def mark_detection_result_sent(self, record_id: int, server_response: str = None) -> bool:
        """
        Mark a detection result as sent to server.
        
        Args:
            record_id: ID of the detection result record
            server_response: Server response text (optional)
            
        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            if not self.connection:
                return False
            
            cursor = self.connection.cursor()
            cursor.execute("""
                UPDATE detection_results
                SET sent_to_server = 1, sent_at = CURRENT_TIMESTAMP, server_response = ?
                WHERE id = ?
            """, (server_response, record_id))
            
            self.connection.commit()
            self.logger.debug(f"Detection result {record_id} marked as sent")
            return True
            
        except Exception as e:
            self.logger.error(f"Error marking detection result as sent: {e}")
            return False
    
    def mark_health_check_sent(self, record_id: int, server_response: str = None) -> bool:
        """
        Mark a health check as sent to server.
        
        Args:
            record_id: ID of the health check record
            server_response: Server response text (optional)
            
        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            if not self.connection:
                return False
            
            cursor = self.connection.cursor()
            cursor.execute("""
                UPDATE health_checks
                SET sent_to_server = 1, sent_at = CURRENT_TIMESTAMP, server_response = ?
                WHERE id = ?
            """, (server_response, record_id))
            
            self.connection.commit()
            self.logger.debug(f"Health check {record_id} marked as sent")
            return True
            
        except Exception as e:
            self.logger.error(f"Error marking health check as sent: {e}")
            return False
    
    def log_websocket_action(self, action: str, status: str, message: str = None, 
                           data_type: str = None, record_count: int = 0, 
                           server_response: str = None) -> Optional[int]:
        """
        Log WebSocket sender action to database.
        
        Args:
            action: Action performed ('connect', 'disconnect', 'send_detection', 'send_health')
            status: Status of action ('success', 'failed', 'no_data')
            message: Log message
            data_type: Type of data being processed
            record_count: Number of records processed
            server_response: Server response text
            
        Returns:
            Optional[int]: ID of inserted log record, None if failed
        """
        try:
            if not self.connection:
                return None
            
            timestamp = datetime.now().isoformat()
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO websocket_sender_logs 
                (timestamp, action, status, message, data_type, record_count, server_response)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, action, status, message, data_type, record_count, server_response))
            
            self.connection.commit()
            record_id = cursor.lastrowid
            
            self.logger.debug(f"WebSocket action logged: {action} - {status}")
            return record_id
            
        except Exception as e:
            self.logger.error(f"Error logging WebSocket action: {e}")
            return None
    
    def get_websocket_sender_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get WebSocket sender logs.
        
        Args:
            limit: Maximum number of logs to retrieve
            
        Returns:
            List[Dict[str, Any]]: List of WebSocket sender logs
        """
        try:
            if not self.connection:
                return []
            
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT timestamp, action, status, message, data_type, record_count, server_response
                FROM websocket_sender_logs
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            results = []
            
            for row in rows:
                result = {
                    'timestamp': row[0],
                    'action': row[1],
                    'status': row[2],
                    'message': row[3],
                    'data_type': row[4],
                    'record_count': row[5],
                    'server_response': row[6]
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting WebSocket sender logs: {e}")
            return []
    
    def cleanup(self):
        """Clean up database connection and resources."""
        try:
            self.logger.info("Cleaning up DatabaseManager...")
            
            if self.connection:
                self.connection.close()
                self.connection = None
                self.logger.info("DatabaseManager cleanup completed")

            
        except Exception as e:
            self.logger.error(f"Error during DatabaseManager cleanup: {e}")
