from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import asyncio
import json
from common.config import ROBOT_MAX_MEDICATION, RobotStatus
from typing import List

class MedicationRobotAgent(Agent):
    def __init__(self, jid, password, peer_robots: List[str]):
        super().__init__(jid, password)
        self.stock = ROBOT_MAX_MEDICATION.copy()
        self.peer_robots = peer_robots
        self.battery_level = 100  # Placeholder for battery level management
        self.robot_status = RobotStatus.AVAILABLE # Placeholder for robot status management
        
    async def setup(self):
        print(f"[{self.name}] MedicationRobotAgent setup.")
        self.add_behaviour(self.MessageReceiverBehaviour())

    class MessageReceiverBehaviour(CyclicBehaviour):
        async def on_start(self):
            print(f"[{self.agent.name}] Ready to receive tasks. Current stock: {self.agent.stock}")

        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                performative = msg.get_metadata("performative")
                task_type = msg.get_metadata("task_type")

                if performative == "inform" and task_type == "delivery":
                    print(f"[{self.agent.name}] Received task via message.")
                    try:
                        task = json.loads(msg.body)
                        if self.can_fulfill(task["medications"]):
                            await self.deliver_medication(task)
                            print(f"[{self.agent.name}] Task fulfilled: {task['ID']}")
                        else:
                            print(f"[{self.agent.name}] Cannot fulfill task {task['ID']} due to stock.")
                    except Exception as e:
                        print(f"[{self.agent.name}] Error handling task message: {e}")
                elif performative == "inform" and task_type == "availability":
                    print(f"[{self.agent.name}] Received availability request from {msg.sender}")
                    # Prepare availability response
                    availability_info = {
                        #"ID": str(self.agent.jid),
                        "stock": self.agent.stock,
                        #"location": self.agent.location  
                        "status": self.agent.robot_status.value
                    }

                    reply = msg.make_reply()
                    reply.set_metadata("performative", "inform")
                    reply.set_metadata("task_type", "availability_response")
                    reply.body = json.dumps(availability_info)

                    await self.send(reply)
                    print(f"[{self.agent.name}] Sent availability info to {msg.sender}")

                else:
                    print(f"[{self.agent.name}] Ignored unrelated message: performative={performative}, task_type={task_type}")

        def can_fulfill(self, meds_required):
            return all(self.agent.stock.get(med, 0) >= amount for med, amount in meds_required.items())

        async def deliver_medication(self, task):
            for med_type, amount in task["medications"].items():
                self.agent.stock[med_type] -= amount
            await asyncio.sleep(3)
            print(f"[{self.agent.name}] Delivery complete. New stock: {self.agent.stock}")

    class BatteryBehaviour(CyclicBehaviour):
        async def run(self):
            # Simulate battery check
            print(f"[{self.agent.name}] Battery level: {self.battery_level}%")
            if self.battery_level < 20 and self.robot_status != RobotStatus.AVAILABLE:
                print(f"[{self.agent.name}] Battery low. Returning to charging station.")
                self.robot_status = RobotStatus.CHARGING
                await self.return_to_charging_station()
            await asyncio.sleep(10)

    async def return_to_charging_station(self):
        print(f"[{self.name}] Returning to charging station...")
        await asyncio.sleep(5)  # Simulate time taken to return
        print(f"[{self.name}] Reached charging station. Ready for next task.")
        self.battery_level = 100  # Recharge the battery
        self.robot_status = RobotStatus.AVAILABLE
        # Here you could implement logic to recharge the robot's battery if needed