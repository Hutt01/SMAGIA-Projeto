from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import asyncio
import requests
import json
from common.config import APP_API_URL
from agents.robot3 import MedicationRobotAgent

class TaskManagerAgent(Agent):
    def __init__(self, jid, password, robot_ids):
        super().__init__(jid, password)
        self.robot_ids = robot_ids
        self.current_robot = 0
        self.robot_available_ids = []
        self.tasks = []

    async def setup(self):
            print(f"[{self.name}] TaskManagerAgent setup.")
            self.add_behaviour(self.TaskFetcherAndDispatcherBehaviour())
    class TaskFetcherAndDispatcherBehaviour(CyclicBehaviour):
        async def on_start(self):
            print(f"[{self.agent.name}] Task dispatcher started. Polling API at {APP_API_URL}")
            await asyncio.sleep(5)

        async def run(self):
            try:
                await asyncio.sleep(5)
                response = requests.get(f"{APP_API_URL}/pending_tasks")
                if response.status_code == 200:
                    received_tasks = response.json().get("pending_tasks", [])
                    if received_tasks == []:
                        print(f"[{self.agent.name}] No pending tasks found.")
                        return
                    existing_ids = {task["ID"] for task in self.agent.tasks}

                    for task in received_tasks:
                        if task["ID"] not in existing_ids:
                            self.agent.tasks.append(task)

                        requests.delete(f"{APP_API_URL}/pending_tasks")
                        for task in self.agent.tasks:
                            #await self.ask_for_availability(task)
                            #await self.dispatch_task(task)
                            robots = await self.get_available_robots_for_task(task)
                            print(robots)
                            self.agent.tasks.remove(task)

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
        
        async def ask_for_availability(self, task):
            
            for robot_jid in self.agent.robot_ids:
                msg = Message(to=robot_jid)
                msg.set_metadata("performative", "inform")
                msg.set_metadata("task_type", "availability")
                msg.body = json.dumps(task)
                await self.send(msg)
                print(f"[{self.agent.name}] Asked {robot_jid} for availability for task {task['ID']}")


            receivemsg = await self.receive(timeout=10)
            if receivemsg:
                if receivemsg.get_metadata("performative") == "inform" and receivemsg.get_metadata("task_type") == "availability_response":
                    print(f"[{self.agent.name}] Received availability response from {receivemsg.sender}")
                    # Here you can handle the availability response if needed
                    #self.agent.robot_available_ids.append(receivemsg.sender["ID"])
                    print(f"[{self.agent.name}] Expected message: {receivemsg.body}")
                else:
                    print(f"[{self.agent.name}] Received unexpected message: {receivemsg.body}")

        async def get_available_robots_for_task(self, task):
            available_robots = []

            for robot_jid in self.agent.robot_ids:
                msg = Message(to=robot_jid)
                msg.set_metadata("performative", "inform")
                msg.set_metadata("task_type", "availability")
                msg.body = json.dumps(task)
                await self.send(msg)
                print(f"[{self.agent.name}] Asked {robot_jid} for availability for task {task['ID']}")

            # Collect responses for up to 10 seconds
            end_time = asyncio.get_event_loop().time() + 10
            while asyncio.get_event_loop().time() < end_time:
                msg = await self.receive(timeout=1)
                if msg:
                    if (msg.get_metadata("performative") == "inform" and
                        msg.get_metadata("task_type") == "availability_response"):
                        
                        try:
                            robot_info = json.loads(msg.body)
                            if self.can_fulfill(task["medications"], robot_info["stock"]):
                                available_robots.append(str(msg.sender))
                                print(f"[{self.agent.name}] {msg.sender} CAN fulfill task {task['ID']}")
                            else:
                                print(f"[{self.agent.name}] {msg.sender} CANNOT fulfill task {task['ID']}")
                        except Exception as e:
                            print(f"[{self.agent.name}] Failed to parse robot response: {e}")
                await asyncio.sleep(0.1)

            return available_robots
        
        def can_fulfill(self, required, available):
            for med_type, qty in required.items():
                if available.get(med_type, 0) < qty:
                    return False
            return True

            

        



# # === Async Main Entry Point ===

# if __name__ == "__main__":

#     async def main():

#         all_ids = ["robot1@localhost", "robot2@localhost", "robot3@localhost"]

#         def get_peers(my_id):
#             return [jid for jid in all_ids if jid != my_id]
        
#         task_manager = TaskManagerAgent("taskmanager@localhost", "managerpassword", all_ids)

#         robot1 = MedicationRobotAgent("robot1@localhost", "robotpassword", get_peers("robot1@localhost"))
#         robot2 = MedicationRobotAgent("robot2@localhost", "robotpassword", get_peers("robot2@localhost"))
#         robot3 = MedicationRobotAgent("robot3@localhost", "robotpassword", get_peers("robot3@localhost"))

#         await asyncio.gather(
#             task_manager.start(),
#             robot1.start(),
#             robot2.start(),
#             robot3.start()
#         )
#         # await robot1.start(auto_register=True)
#         # await robot2.start(auto_register=True)
#         # await robot3.start(auto_register=True)
#         # await task_manager.start(auto_register=True)

#         print("Robots started. Press Ctrl+C to stop.")

#         try:
#             while True:
#                 await asyncio.sleep(1)
#         except KeyboardInterrupt:
#             print("Stopping agents...")
#             await task_manager.stop()
#             await robot1.stop()
#             await robot2.stop()
#             await robot3.stop()
#             print("Robots stopped.")

#     asyncio.run(main())

