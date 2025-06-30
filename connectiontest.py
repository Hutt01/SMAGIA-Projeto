# # subscriber.py
# import paho.mqtt.client as mqtt

# # Called when connected to broker
# def on_connect(client, userdata, flags, rc):
#     print("Connected with result code", rc)
#     client.subscribe("mytest/topic")

# # Called when a message is received
# def on_message(client, userdata, msg):
#     print(f"Received message: {msg.topic} -> {msg.payload.decode()}")

# # Setup client
# client = mqtt.Client()
# client.on_connect = on_connect
# client.on_message = on_message

# # Connect to broker
# client.connect("broker.hivemq.com", 1883, 60)

# # Start listening
# client.loop_forever()


# subscriber.py

#####
# import paho.mqtt.client as mqtt

# def on_connect(client, userdata, flags, rc):
#     print("Connected with result code", rc)
#     client.subscribe("123/meia/clock")  # Subscribe to the /clock topic

# def on_message(client, userdata, msg):
#     print(f"Received message: {msg.topic} -> {msg.payload.decode()}")

# client = mqtt.Client()
# client.on_connect = on_connect
# client.on_message = on_message

# client.connect("broker.hivemq.com", 1883, 60)
# client.loop_forever()


# publisher.py

# import paho.mqtt.client as mqtt
# import json
# import time

# # MQTT Configuration
# MQTT_BROKER = "broker.hivemq.com"
# MQTT_PORT = 1883
# MQTT_TOPIC_GOAL = "123/meia/goal"

# # Position to send
# goal_data = {
#     "x": 1.09,
#     "y": 0.47,
#     "theta_deg": 90  # Orientation in degrees
# }

# # Create MQTT client and connect
# client = mqtt.Client()
# client.connect(MQTT_BROKER, MQTT_PORT, 60)
# client.loop_start()

# time.sleep(1)  # Wait for connection to establish

# # Publish the message
# payload = json.dumps(goal_data)
# client.publish(MQTT_TOPIC_GOAL, payload)
# print(f"Sent goal to topic {MQTT_TOPIC_GOAL}: {payload}")

# client.loop_stop()
# client.disconnect()


import paho.mqtt.client as mqtt
import json
import time

client = mqtt.Client()
client.connect("broker.hivemq.com", 1883, 60)
client.loop_start()
time.sleep(1)
-9.09, 0.47

goal1 = {"x": -9.0, "y": 0.5 }
client.publish("123/meia/robot1/goal", json.dumps(goal1))

print("Sent goal to robot1")

# goal2 = {"x": -9.0, "y": -2.0}
# client.publish("123/meia/robot2/goal", json.dumps(goal2))

# print("Sent goal to robot2")


# goal3 = {"x": -9.0, "y": -4.0}
# client.publish("123/meia/robot3/goal", json.dumps(goal3))

# print("Sent goal to robot3")
client.loop_stop()
client.disconnect()
