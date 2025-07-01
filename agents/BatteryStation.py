from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
import asyncio
import json
from common.config import RobotStatus
from typing import List, Dict
import paho.mqtt.client as mqtt
import threading

CHARGING_STATION_LOCATION = {"x": 1.43, "y": -11.21}

class BatteryStationAgent(Agent):
    def __init__(self, jid, password, peer_robots: List[str]):
        super().__init__(jid, password)
        self.peer_robots = peer_robots
        # Track status and battery for each robot
        self.robot_status: Dict[str, RobotStatus] = {r: RobotStatus.AVAILABLE for r in peer_robots}
        self.battery_level: Dict[str, int] = {r: 100 for r in peer_robots}
        self.mqtt_goal_succeeded: Dict[str, threading.Event] = {r: threading.Event() for r in peer_robots}

        # MQTT setup
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_message = self._on_mqtt_message
        self.mqtt_client.connect("broker.hivemq.com", 1883, 60)

        # Subscribe to status updates for each robot
        for robot in self.peer_robots:
            status_topic = f"123/meia/{robot.lower()}/status"
            self.mqtt_client.subscribe(status_topic)
        self.mqtt_client.loop_start()

    def _on_mqtt_message(self, client, userdata, msg):
        payload = msg.payload.decode()
        print(f"[{self.name}] MQTT {msg.topic} → {payload}")
        try:
            data = json.loads(payload)
        except Exception:
            data = payload

        # Check which robot this message is for
        for robot in self.peer_robots:
            topic_check = f"123/meia/{robot.lower()}/status"
            if msg.topic == topic_check:
                # You could parse and update battery level if your robots send it!
                if isinstance(data, dict) and "battery" in data:
                    self.battery_level[robot] = int(data["battery"])
                # Confirm charging finished
                if (isinstance(data, dict) and data.get("status") == "goal_succeeded") or \
                   (isinstance(data, str) and data == "goal_succeeded"):
                    self.mqtt_goal_succeeded[robot].set()
                    self.robot_status[robot] = RobotStatus.AVAILABLE
                    self.battery_level[robot] = 100
                    print(f"[{self.name}] {robot} chegou à estação de carregamento.")

    async def setup(self):
        print(f"[{self.name}] Battery Station setup.")
        self.add_behaviour(self.BatteryBehaviour())

    class BatteryBehaviour(CyclicBehaviour):
        async def run(self):
            agent = self.agent
            # Check each robot's battery
            for robot in agent.peer_robots:
                if agent.battery_level[robot] < 20 and agent.robot_status[robot] != RobotStatus.CHARGING:
                    print(f"[{agent.name}] {robot}: Battery low ({agent.battery_level[robot]}%). Sending to charging station.")
                    agent.robot_status[robot] = RobotStatus.CHARGING
                    await agent.send_robot_to_charging(robot)
            await asyncio.sleep(10)

    async def send_robot_to_charging(self, robot_name: str):
        print(f"[{self.name}] {robot_name}: Sending goal to charging station...")
        topic = f"123/meia/{robot_name.lower()}/goal"
        self.mqtt_goal_succeeded[robot_name].clear()
        self.mqtt_client.publish(topic, json.dumps(CHARGING_STATION_LOCATION))
        print(f"[{self.name}] {robot_name}: Published goal to {topic}: {CHARGING_STATION_LOCATION}")

        print(f"[{self.name}] {robot_name}: Waiting for goal_succeeded MQTT message...")
        await asyncio.get_event_loop().run_in_executor(None, self.mqtt_goal_succeeded[robot_name].wait)

        if self.mqtt_goal_succeeded[robot_name].is_set():
            print(f"[{self.name}] {robot_name}: Charging complete. Battery set to 100%.")
            self.battery_level[robot_name] = 100
            self.robot_status[robot_name] = RobotStatus.AVAILABLE
        else:
            print(f"[{self.name}] {robot_name}: Did not receive goal_succeeded MQTT message in time.")
