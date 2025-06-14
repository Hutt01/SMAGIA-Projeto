from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import asyncio
import json
from common.config import ROBOT_MAX_MEDICATION
from typing import List

class MedicationRobotAgent(Agent):
    def __init__(self, jid, password, peer_robots: List[str]):
        super().__init__(jid, password)
        self.stock = ROBOT_MAX_MEDICATION.copy()
        self.peer_robots = peer_robots

    class MessageReceiverBehaviour(CyclicBehaviour):
        async def on_start(self):
            print(f"[{self.agent.name}] Ready to receive tasks. Current stock: {self.agent.stock}")

        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
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

        def can_fulfill(self, meds_required):
            return all(self.agent.stock.get(med, 0) >= amount for med, amount in meds_required.items())

        async def deliver_medication(self, task):
            for med_type, amount in task["medications"].items():
                self.agent.stock[med_type] -= amount
            await asyncio.sleep(3)
            print(f"[{self.agent.name}] Delivery complete. New stock: {self.agent.stock}")

