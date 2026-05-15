"""
Smart GreenHouse - Lambda Data Processor
Processes IoT sensor data from SQS, validates, checks alerts, stores in DynamoDB
"""

import json
import boto3
import os
from datetime import datetime
from decimal import Decimal

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

# Configuration from environment variables
TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'greenhouse-sensor-data')
ALERT_TOPIC_ARN = os.environ.get('ALERT_TOPIC_ARN', '')

# Alert thresholds
THRESHOLDS = {
    'temperature': {'min': 15, 'max': 35, 'unit': '°C'},
    'humidity': {'min': 40, 'max': 85, 'unit': '%'},
    'soil_moisture': {'min': 30, 'max': 80, 'unit': '%'},
    'light_intensity': {'min': 100, 'max': 1000, 'unit': 'lux'}
}


def parse_sqs_message(record):
    """
    Extract sensor data from SQS message.
    SQS wraps SNS messages, so we need to unwrap twice.
    """
    try:
        # First level: SQS message body (contains SNS notification)
        sqs_body = json.loads(record['body'])
        
        # Second level: SNS message (contains our sensor data)
        if 'Message' in sqs_body:
            sensor_payload = json.loads(sqs_body['Message'])
        else:
            # Direct message (for testing)
            sensor_payload = sqs_body
        
        return sensor_payload
    
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        return None
    except KeyError as e:
        print(f"Missing expected key: {e}")
        return None


def validate_reading(reading):
    """
    Validate sensor reading has required fields and reasonable values.
    Returns (is_valid, errors)
    """
    errors = []
    
    # Check required fields
    required_fields = ['greenhouse_id', 'timestamp', 'sensors']
    for field in required_fields:
        if field not in reading.get('reading', {}):
            errors.append(f"Missing required field: {field}")
    
    if errors:
        return False, errors
    
    sensors = reading.get('reading', {}).get('sensors', {})
    
    # Validate each sensor value is numeric and within possible range
    for sensor_name, sensor_data in sensors.items():
        value = sensor_data.get('value')
        
        if value is None:
            errors.append(f"{sensor_name}: missing value")
            continue
            
        if not isinstance(value, (int, float)):
            errors.append(f"{sensor_name}: value must be numeric")
            continue
        
        # Sanity checks (not alert thresholds, just physically possible)
        if sensor_name == 'temperature' and not (-40 <= value <= 60):
            errors.append(f"{sensor_name}: value {value} outside possible range")
        elif sensor_name == 'humidity' and not (0 <= value <= 100):
            errors.append(f"{sensor_name}: value {value} outside possible range")
        elif sensor_name == 'soil_moisture' and not (0 <= value <= 100):
            errors.append(f"{sensor_name}: value {value} outside possible range")
        elif sensor_name == 'light_intensity' and not (0 <= value <= 10000):
            errors.append(f"{sensor_name}: value {value} outside possible range")
    
    return len(errors) == 0, errors


def check_alerts(sensors, greenhouse_id, timestamp):
    """
    Check sensor values against alert thresholds.
    Returns list of alert objects.
    """
    alerts = []
    
    for sensor_name, threshold in THRESHOLDS.items():
        if sensor_name not in sensors:
            continue
            
        value = sensors[sensor_name]['value']
        
        if value < threshold['min']:
            alerts.append({
                'alert_type': f"LOW_{sensor_name.upper()}",
                'sensor': sensor_name,
                'value': value,
                'threshold': threshold['min'],
                'direction': 'below',
                'unit': threshold['unit'],
                'greenhouse_id': greenhouse_id,
                'timestamp': timestamp,
                'severity': 'WARNING' if sensor_name != 'temperature' else 'CRITICAL'
            })
        
        elif value > threshold['max']:
            alerts.append({
                'alert_type': f"HIGH_{sensor_name.upper()}",
                'sensor': sensor_name,
                'value': value,
                'threshold': threshold['max'],
                'direction': 'above',
                'unit': threshold['unit'],
                'greenhouse_id': greenhouse_id,
                'timestamp': timestamp,
                'severity': 'WARNING' if sensor_name != 'temperature' else 'CRITICAL'
            })
    
    return alerts


def send_alert_notification(alerts):
    """
    Send alert notifications via SNS.
    """
    if not ALERT_TOPIC_ARN or not alerts:
        return
    
    # Group alerts by severity
    critical = [a for a in alerts if a['severity'] == 'CRITICAL']
    warnings = [a for a in alerts if a['severity'] == 'WARNING']
    
    # Build alert message
    message_lines = [
        "🚨 GREENHOUSE ALERT NOTIFICATION",
        f"Time: {alerts[0]['timestamp']}",
        f"Greenhouse: {alerts[0]['greenhouse_id']}",
        ""
    ]
    
    if critical:
        message_lines.append("⛔ CRITICAL ALERTS:")
        for alert in critical:
            message_lines.append(
                f"  • {alert['sensor']}: {alert['value']}{alert['unit']} "
                f"({alert['direction']} {alert['threshold']}{alert['unit']})"
            )
        message_lines.append("")
    
    if warnings:
        message_lines.append("⚠️ WARNINGS:")
        for alert in warnings:
            message_lines.append(
                f"  • {alert['sensor']}: {alert['value']}{alert['unit']} "
                f"({alert['direction']} {alert['threshold']}{alert['unit']})"
            )
    
    try:
        sns.publish(
            TopicArn=ALERT_TOPIC_ARN,
            Message='\n'.join(message_lines),
            Subject=f"🚨 GreenHouse Alert: {len(critical)} Critical, {len(warnings)} Warnings"
        )
        print(f"Alert notification sent: {len(alerts)} alerts")
    except Exception as e:
        print(f"Failed to send alert notification: {e}")


def float_to_decimal(obj):
    """
    Convert floats to Decimal for DynamoDB.
    DynamoDB doesn't support float type directly.
    """
    if isinstance(obj, float):
        return Decimal(str(round(obj, 4)))
    elif isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [float_to_decimal(i) for i in obj]
    return obj


def store_in_dynamodb(reading, alerts, processing_metadata):
    """
    Store processed sensor data in DynamoDB.
    """
    table = dynamodb.Table(TABLE_NAME)
    
    reading_data = reading.get('reading', {})
    
    item = {
        'greenhouse_id': reading_data['greenhouse_id'],
        'timestamp': reading_data['timestamp'],
        'sensors': float_to_decimal(reading_data['sensors']),
        'alert_count': len(alerts),
        'alerts': alerts if alerts else [],
        'metadata': float_to_decimal(reading_data.get('metadata', {})),
        'processing': {
            'processed_at': processing_metadata['processed_at'],
            'lambda_request_id': processing_metadata['request_id'],
            'validation_passed': processing_metadata['valid']
        }
    }
    
    try:
        table.put_item(Item=item)
        print(f"Stored reading for {reading_data['greenhouse_id']} at {reading_data['timestamp']}")
        return True
    except Exception as e:
        print(f"DynamoDB error: {e}")
        return False


def lambda_handler(event, context):
    """
    Main Lambda handler.
    Processes batch of SQS messages containing sensor data.
    """
    print(f"Processing {len(event['Records'])} records")
    
    results = {
        'processed': 0,
        'failed': 0,
        'alerts_triggered': 0
    }
    
    for record in event['Records']:
        try:
            # Parse the message
            payload = parse_sqs_message(record)
            
            if payload is None:
                print(f"Failed to parse message: {record['messageId']}")
                results['failed'] += 1
                continue
            
            # Validate the reading
            is_valid, errors = validate_reading(payload)
            
            if not is_valid:
                print(f"Validation failed: {errors}")
                results['failed'] += 1
                continue
            
            reading_data = payload.get('reading', {})
            sensors = reading_data.get('sensors', {})
            
            # Check for alerts
            alerts = check_alerts(
                sensors,
                reading_data['greenhouse_id'],
                reading_data['timestamp']
            )
            
            if alerts:
                results['alerts_triggered'] += len(alerts)
                send_alert_notification(alerts)
            
            # Prepare processing metadata
            processing_metadata = {
                'processed_at': datetime.utcnow().isoformat() + 'Z',
                'request_id': context.aws_request_id,
                'valid': is_valid
            }
            
            # Store in DynamoDB
            stored = store_in_dynamodb(payload, alerts, processing_metadata)
            
            if stored:
                results['processed'] += 1
            else:
                results['failed'] += 1
                
        except Exception as e:
            print(f"Error processing record: {e}")
            results['failed'] += 1
    
    print(f"Processing complete: {results}")
    
    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }