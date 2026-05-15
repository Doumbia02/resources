"""
Smart GreenHouse - Dashboard API
Serves sensor data to the web dashboard
"""

import json
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta
from decimal import Decimal

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('greenhouse-sensor-data')

# CORS headers for browser access
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
}


def decimal_default(obj):
    """JSON serializer for Decimal types"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def response(status_code, body):
    """Build API response with CORS headers"""
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(body, default=decimal_default)
    }


def get_latest_reading(greenhouse_id):
    """Get most recent sensor reading"""
    result = table.query(
        KeyConditionExpression=Key('greenhouse_id').eq(greenhouse_id),
        ScanIndexForward=False,
        Limit=1
    )
    
    if result['Items']:
        return result['Items'][0]
    return None


def get_readings_history(greenhouse_id, hours=6):
    """Get sensor readings for time period"""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    
    result = table.query(
        KeyConditionExpression=
            Key('greenhouse_id').eq(greenhouse_id) &
            Key('timestamp').between(
                start_time.isoformat() + 'Z',
                end_time.isoformat() + 'Z'
            ),
        ScanIndexForward=True
    )
    
    return result['Items']


def get_statistics(greenhouse_id, hours=24):
    """Calculate statistics for time period"""
    readings = get_readings_history(greenhouse_id, hours)
    
    if not readings:
        return None
    
    sensors = ['temperature', 'humidity', 'soil_moisture', 'light_intensity']
    stats = {}
    
    for sensor in sensors:
        values = [float(r['sensors'][sensor]['value']) for r in readings if sensor in r['sensors']]
        
        if values:
            stats[sensor] = {
                'min': round(min(values), 2),
                'max': round(max(values), 2),
                'avg': round(sum(values) / len(values), 2),
                'current': values[-1] if values else None
            }
    
    # Count alerts
    total_alerts = sum(int(r.get('alert_count', 0)) for r in readings)
    
    stats['summary'] = {
        'total_readings': len(readings),
        'total_alerts': total_alerts,
        'period_hours': hours
    }
    
    return stats


def get_recent_alerts(greenhouse_id, limit=10):
    """Get recent alerts"""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)
    
    result = table.query(
        KeyConditionExpression=
            Key('greenhouse_id').eq(greenhouse_id) &
            Key('timestamp').gte(start_time.isoformat() + 'Z'),
        FilterExpression='alert_count > :zero',
        ExpressionAttributeValues={':zero': 0},
        ScanIndexForward=False
    )
    
    alerts = []
    for item in result['Items'][:limit]:
        for alert in item.get('alerts', []):
            alert['reading_timestamp'] = item['timestamp']
            alerts.append(alert)
    
    return alerts


def list_greenhouses():
    """Get list of all greenhouses with data"""
    # Scan to get unique greenhouse IDs (okay for small datasets)
    result = table.scan(
        ProjectionExpression='greenhouse_id',
        Select='SPECIFIC_ATTRIBUTES'
    )
    
    # Get unique IDs
    greenhouse_ids = list(set(item['greenhouse_id'] for item in result['Items']))
    
    return sorted(greenhouse_ids)


def lambda_handler(event, context):
    """Main API handler"""
    
    # Handle CORS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return response(200, {'message': 'OK'})
    
    # Parse path and parameters
    path = event.get('path', '/')
    params = event.get('queryStringParameters') or {}
    
    greenhouse_id = params.get('greenhouse_id', 'greenhouse-01')
    
    try:
        # Route: GET /latest
        if path == '/latest':
            data = get_latest_reading(greenhouse_id)
            if data:
                return response(200, data)
            return response(404, {'error': 'No data found'})
        
        # Route: GET /history
        elif path == '/history':
            hours = int(params.get('hours', 6))
            hours = min(hours, 168)  # Cap at 1 week
            data = get_readings_history(greenhouse_id, hours)
            return response(200, {'readings': data, 'count': len(data)})
        
        # Route: GET /stats
        elif path == '/stats':
            hours = int(params.get('hours', 24))
            data = get_statistics(greenhouse_id, hours)
            if data:
                return response(200, data)
            return response(404, {'error': 'No data found'})
        
        # Route: GET /alerts
        elif path == '/alerts':
            limit = int(params.get('limit', 10))
            data = get_recent_alerts(greenhouse_id, limit)
            return response(200, {'alerts': data, 'count': len(data)})
        
        # Route: GET /greenhouses
        elif path == '/greenhouses':
            data = list_greenhouses()
            return response(200, {'greenhouses': data})
        
        # Route: GET / (health check)
        elif path == '/':
            return response(200, {
                'service': 'Smart GreenHouse API',
                'status': 'healthy',
                'endpoints': ['/latest', '/history', '/stats', '/alerts', '/greenhouses']
            })
        
        else:
            return response(404, {'error': f'Unknown endpoint: {path}'})
    
    except Exception as e:
        print(f"Error: {e}")
        return response(500, {'error': str(e)})