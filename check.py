import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    print(f"{msg.topic} → {msg.payload.decode()}")

client = mqtt.Client()
client.on_message = on_message
client.connect("broker.hivemq.com", 1883, 60)
client.subscribe("123/meia/robot1/status")
client.subscribe("123/meia/robot2/status")
client.subscribe("123/meia/robot3/status")
client.loop_forever()
