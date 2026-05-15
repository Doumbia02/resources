#!/usr/bin/env python3
"""
DynamoDB Query Test Script for Smart GreenHouse
Run this after the pipeline has collected some data
"""

import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta
from decimal import Decimal

# Initialize
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('greenhouse-sensor-data')

def decimal_to_float(obj):
    """Convert DynamoDB Decimals to floats for display"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(i) for i in obj]
    return obj


def test_queries():
    print("=" * 60)
    print("🌱 Smart GreenHouse - DynamoDB Query Tests")
    print("=" * 60)
    
    greenhouse_id = "greenhouse-01"
    
    # Test 1: Count total items
    print("\n📊 Test 1: Count total readings")
    response = table.scan(Select='COUNT')
    print(f"   Total readings in table: {response['Count']}")
    
    # Test 2: Latest reading
    print("\n📊 Test 2: Latest reading")
    response = table.query(
        KeyConditionExpression=Key('greenhouse_id').eq(greenhouse_id),
        ScanIndexForward=False,
        Limit=1
    )
    if response['Items']:
        item = decimal_to_float(response['Items'][0])
        print(f"   Greenhouse: {item['greenhouse_id']}")
        print(f"   Timestamp: {item['timestamp']}")
        print(f"   Temperature: {item['sensors']['temperature']['value']}°C")
        print(f"   Humidity: {item['sensors']['humidity']['value']}%")
        print(f"   Soil Moisture: {item['sensors']['soil_moisture']['value']}%")
        print(f"   Light: {item['sensors']['light_intensity']['value']} lux")
    else:
        print("   No readings found!")
    
    # Test 3: Last hour readings
    print("\n📊 Test 3: Readings from last hour")
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)
    
    response = table.query(
        KeyConditionExpression=
            Key('greenhouse_id').eq(greenhouse_id) &
            Key('timestamp').gte(start_time.isoformat() + 'Z')
    )
    print(f"   Readings in last hour: {len(response['Items'])}")
    
    # Test 4: Readings with alerts
    print("\n📊 Test 4: Readings with alerts (last 24 hours)")
    start_24h = datetime.utcnow() - timedelta(hours=24)
    
    # Note: This requires a full query since we're filtering on non-key attribute
    response = table.query(
        KeyConditionExpression=
            Key('greenhouse_id').eq(greenhouse_id) &
            Key('timestamp').gte(start_24h.isoformat() + 'Z'),
        FilterExpression='alert_count > :zero',
        ExpressionAttributeValues={':zero': 0}
    )
    print(f"   Readings with alerts: {len(response['Items'])}")
    
    if response['Items']:
        print("   Recent alerts:")
        for item in response['Items'][:3]:  # Show first 3
            item = decimal_to_float(item)
            for alert in item.get('alerts', []):
                print(f"      • {alert['alert_type']}: {alert['value']}{alert['unit']}")
    
    # Test 5: Calculate averages
    print("\n📊 Test 5: 24-hour averages")
    response = table.query(
        KeyConditionExpression=
            Key('greenhouse_id').eq(greenhouse_id) &
            Key('timestamp').gte(start_24h.isoformat() + 'Z')
    )
    
    if response['Items']:
        readings = [decimal_to_float(item) for item in response['Items']]
        
        avg_temp = sum(r['sensors']['temperature']['value'] for r in readings) / len(readings)
        avg_humidity = sum(r['sensors']['humidity']['value'] for r in readings) / len(readings)
        avg_soil = sum(r['sensors']['soil_moisture']['value'] for r in readings) / len(readings)
        
        print(f"   Average Temperature: {avg_temp:.1f}°C")
        print(f"   Average Humidity: {avg_humidity:.1f}%")
        print(f"   Average Soil Moisture: {avg_soil:.1f}%")
        print(f"   Sample size: {len(readings)} readings")
    
    print("\n" + "=" * 60)
    print("✅ Query tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_queries()