from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import asyncio
import requests
import json
from common.config import APP_API_URL

class TaskManagerAgent(Agent):
    def __init__(self, jid, password, robot_ids):
        super().__init__(jid, password)
        self.robot_ids = robot_ids
        self.current_robot = 0

    class TaskFetcherAndDispatcherBehaviour(CyclicBehaviour):
        async def on_start(self):
            print(f"[{self.agent.name}] Task dispatcher started. Polling API at {APP_API_URL}")

        async def run(self):
            try:
                response = requests.get(f"{APP_API_URL}/pending_tasks")
                if response.status_code == 200:
                    tasks = response.json().get("pending_tasks", [])
                    for task in tasks:
                        await self.dispatch_task(task)
                        requests.delete(f"{APP_API_URL}/pending_tasks/{task['ID']}")
                else:
                    print(f"[{self.agent.name}] Failed to fetch tasks: {response.status_code}")
            except Exception as e:
                print(f"[{self.agent.name}] Error fetching tasks: {e}")

            await asyncio.sleep(5)

        async def dispatch_task(self, task):
            if not self.agent.robot_ids:
                print(f"[{self.agent.name}] No robots to dispatch to.")
                return

            robot_jid = self.agent.robot_ids[self.agent.current_robot]
            self.agent.current_robot = (self.agent.current_robot + 1) % len(self.agent.robot_ids)

            msg = Message(to=robot_jid)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("task_type", "delivery")
            msg.body = json.dumps(task)

            await self.send(msg)
            print(f"[{self.agent.name}] Dispatched task {task['ID']} to {robot_jid}")