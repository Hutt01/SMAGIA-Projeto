import paho.mqtt.client as mqtt
import json
import time
import threading
import math
import random

def get_location_mock():
    x = random.randint(0, 250)
    y = random.randint(0, 250)
    z = 0
    return x, y, z

def get_location(robot_name, timeout=5):
    location_topic = f"123/meia/{robot_name}/location"
    location_data = {}
    event = threading.Event()

    def on_connect(client, userdata, flags, rc):
        client.subscribe(location_topic)

    def on_message(client, userdata, msg):
        try:
            payload = msg.payload.decode()
            location = json.loads(payload)
            location_data.update(location)
            event.set()  # Notify main thread that we have the data
        except Exception as e:
            print("Error parsing message:", e)

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("broker.hivemq.com", 1883, 60)
    client.loop_start()

    # Wait for a message or timeout
    got_message = event.wait(timeout=timeout)

    client.loop_stop()
    client.disconnect()

    if got_message:
        return location_data["x"], location_data["y"]
    else:
        print(f"No location message received for {robot_name} within {timeout} seconds.")
        return None
    


def distance_between_points(x1, y1, x2, y2):
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

# Example usage:
xy = get_location("robot1")
if xy:
    x, y = xy
    print(f"robot1 location: x = {x}, y = {y}")
else:
    print("Could not get location.")