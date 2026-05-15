#!/usr/bin/env python3
"""
Smart GreenHouse IoT Sensor Simulator
Generates realistic sensor data for cloud pipeline testing
"""

import json
import time
import random
import math
from datetime import datetime
import boto3

# Configuration
GREENHOUSE_ID = ["greenhouse-01", "greenhouse-02", "greenhouse-03", "greenhouse-04", "greenhouse-05"]
SEND_INTERVAL = 5  # seconds between readings
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:381492245188:greenhouse-sensor-data"  # Replace with your SNS topic

# Initialize AWS client
 sSsns_client = boto3.client('sns', region_name='us-east-1')

class GreenhouseSensor:
    def __init__(self, greenhouse_id):
        self.greenhouse_id = greenhouse_id
        self.hour_of_day = 8  # Start at 8 AM
        self.soil_moisture = 50.0
        self.last_watering = 0
        
    def _get_time_factor(self):
        """Simulate day/night cycle (0-24 hours)"""
        self.hour_of_day = (self.hour_of_day + 0.1) % 24
        return self.hour_of_day
    
    def _add_noise(self, value, noise_level=0.5):
        """Add realistic sensor noise"""
        return value + random.gauss(0, noise_level)
    
    def read_temperature(self):
        """Temperature follows daily cycle: cooler at night, warmer midday"""
        hour = self._get_time_factor()
        # Peak at 14:00 (2 PM), lowest at 4:00 AM
        base_temp = 25 + 8 * math.sin((hour - 8) * math.pi / 12)
        temp = self._add_noise(base_temp, 0.3)
        
        # Occasional heat spike (simulating equipment or weather)
        if random.random() < 0.02:
            temp += random.uniform(5, 10)
        
        return round(max(10, min(45, temp)), 2)
    
    def read_humidity(self, temperature):
        """Humidity inversely related to temperature"""
        base_humidity = 80 - (temperature - 20) * 1.5
        humidity = self._add_noise(base_humidity, 2)
        
        return round(max(20, min(95, humidity)), 2)
    
    def read_soil_moisture(self):
        """Soil moisture decreases over time, jumps up when 'watered'"""
        # Gradual decrease
        self.soil_moisture -= random.uniform(0.1, 0.3)
        
        # Auto-watering when too dry (or random watering event)
        self.last_watering += 1
        if self.soil_moisture < 30 or (self.last_watering > 50 and random.random() < 0.1):
            self.soil_moisture = random.uniform(55, 70)
            self.last_watering = 0
        
        moisture = self._add_noise(self.soil_moisture, 1)
        return round(max(10, min(90, moisture)), 2)
    
    def read_light(self):
        """Light follows day/night cycle"""
        hour = self.hour_of_day
        
        if 6 <= hour <= 20:  # Daytime
            # Peak at noon
            intensity = 500 + 400 * math.sin((hour - 6) * math.pi / 14)
            light = self._add_noise(intensity, 20)
        else:  # Nighttime
            light = self._add_noise(5, 2)
        
        return round(max(0, min(1200, light)), 2)
    
    def generate_reading(self):
        """Generate complete sensor reading"""
        temperature = self.read_temperature()
        
        reading = {
            "greenhouse_id": self.greenhouse_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "sensors": {
                "temperature": {
                    "value": temperature,
                    "unit": "celsius"
                },
                "humidity": {
                    "value": self.read_humidity(temperature),
                    "unit": "percent"
                },
                "soil_moisture": {
                    "value": self.read_soil_moisture(),
                    "unit": "percent"
                },
                "light_intensity": {
                    "value": self.read_light(),
                    "unit": "lux"
                }
            },
            "metadata": {
                "simulated_hour": round(self.hour_of_day, 1),
                "firmware_version": "1.0.0"
            }
        }
        
        return reading


def check_alerts(reading):
    """Check for alert conditions"""
    alerts = []
    sensors = reading["sensors"]
    
    temp = sensors["temperature"]["value"]
    if temp > 35:
        alerts.append({"type": "HIGH_TEMPERATURE", "value": temp, "threshold": 35})
    elif temp < 15:
        alerts.append({"type": "LOW_TEMPERATURE", "value": temp, "threshold": 15})
    
    humidity = sensors["humidity"]["value"]
    if humidity > 85:
        alerts.append({"type": "HIGH_HUMIDITY", "value": humidity, "threshold": 85})
    elif humidity < 40:
        alerts.append({"type": "LOW_HUMIDITY", "value": humidity, "threshold": 40})
    
    moisture = sensors["soil_moisture"]["value"]
    if moisture < 30:
        alerts.append({"type": "LOW_SOIL_MOISTURE", "value": moisture, "threshold": 30})
    
    light = sensors["light_intensity"]["value"]
    if 6 <= reading["metadata"]["simulated_hour"] <= 18 and light < 100:
        alerts.append({"type": "LOW_LIGHT", "value": light, "threshold": 100})
    
    return alerts


def publish_to_sns(reading, alerts):
    """Publish sensor data to SNS topic"""
    message = {
        "reading": reading,
        "alerts": alerts,
        "alert_count": len(alerts)
    }
    
    try:
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps(message),
            Subject=f"GreenHouse Data: {reading['greenhouse_id']}",
            MessageAttributes={
                'greenhouse_id': {
                    'DataType': 'String',
                    'StringValue': reading['greenhouse_id']
                },
                'has_alerts': {
                    'DataType': 'String',
                    'StringValue': str(len(alerts) > 0)
                }
            }
        )
        return response['MessageId']
    except Exception as e:
        print(f"Error publishing to SNS: {e}")
        return None


def main():
    """Main loop - continuously generate and send sensor data"""
    print("🌱 Smart GreenHouse Simulator Starting...")
    print(f"   Greenhouse ID: {GREENHOUSE_ID}")
    print(f"   Send Interval: {SEND_INTERVAL} seconds")
    print("-" * 50)
    
    sensor = {
        gh_id: GreenhouseSensor(gh_id)
        for gh_id in GREENHOUSE_IDS
        }
    reading_count = 0
    
    try:
        while True:
            # Generate sensor reading
            for gh_id, sensor in sensors.items():
            
            reading = sensor.generate_reading()
            alerts = check_alerts(reading)
            
            reading_count += 1
            
            # Display locally
            print(f"\n📊 [{gh_id}] Reading #{reading_count} | Hour: {reading['metadata']['simulated_hour']}")
            print(f"   🌡️  Temp: {reading['sensors']['temperature']['value']}°C")
            print(f"   💧 Humidity: {reading['sensors']['humidity']['value']}%")
            print(f"   🌍 Soil: {reading['sensors']['soil_moisture']['value']}%")
            print(f"   ☀️  Light: {reading['sensors']['light_intensity']['value']} lux")
            
            if alerts:
                print(f"   ⚠️  ALERTS: {[a['type'] for a in alerts]}")
            
            # Publish to SNS
            msg_id = publish_to_sns(reading, alerts)
            if msg_id:
                print(f"   ✅ Published: {msg_id[:20]}...")
            
            time.sleep(SEND_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Simulator stopped.")
        print(f"   Total readings sent: {reading_count}")


if __name__ == "__main__":
    main()
