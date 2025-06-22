# subscriber.py
import paho.mqtt.client as mqtt

# Called when connected to broker
def on_connect(client, userdata, flags, rc):
    print("Connected with result code", rc)
    client.subscribe("mytest/topic")

# Called when a message is received
def on_message(client, userdata, msg):
    print(f"Received message: {msg.topic} -> {msg.payload.decode()}")

# Setup client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

# Connect to broker
client.connect("broker.hivemq.com", 1883, 60)

# Start listening
client.loop_forever()
