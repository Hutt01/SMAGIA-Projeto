from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
import requests
import asyncio
from common.config import APP_API_URL, ROBOT_MAX_MEDICATION

class MedicationRobotAgent(Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.stock = ROBOT_MAX_MEDICATION.copy()

    class TaskManagerBehaviour(CyclicBehaviour):
        async def on_start(self):
            print(f"[{self.agent.name}] TaskManagerBehaviour started with stock: {self.agent.stock}")

        async def run(self):
            print(f"\n[{self.agent.name}] Checking for tasks...")
            try:
                response = requests.get(f"{APP_API_URL}/pending_tasks")
                if response.status_code == 200:
                    tasks = response.json().get("pending_tasks", [])
                    if tasks:
                        for task in tasks:
                            if self.can_fulfill(task["medications"]):
                                await self.deliver_medication(task)
                                print(f"[{self.agent.name}] Completed task: {task['ID']}")
                                break  # Only take one task at a time
                        else:
                            print(f"[{self.agent.name}] No task matches available stock.")
                    else:
                        print(f"[{self.agent.name}] No pending tasks.")
                else:
                    print(f"[{self.agent.name}] Error fetching tasks.")
            except Exception as e:
                print(f"[{self.agent.name}] Exception during task fetch: {e}")

            await asyncio.sleep(5)

        def can_fulfill(self, meds_required):
            for med_type, amount in meds_required.items():
                if self.agent.stock.get(med_type, 0) < amount:
                    return False
            return True

        async def deliver_medication(self, task):
            meds_required = task["medications"]
            print(f"[{self.agent.name}] Delivering to {task['location']}: {meds_required}")

            for med_type, amount in meds_required.items():
                self.agent.stock[med_type] -= amount

            requests.delete(f"{APP_API_URL}/pending_tasks/{task['ID']}")

            await asyncio.sleep(3)
            print(f"[{self.agent.name}] Delivery complete. New stock: {self.agent.stock}")

    async def setup(self):
        print(f"Agent {self.name} ({self.jid}) starting...")
        b = self.TaskManagerBehaviour()
        self.add_behaviour(b)


# === Async Main Entry Point ===

if __name__ == "__main__":

    async def main():
        robot = MedicationRobotAgent("robot@localhost", "robotpassword")

        await robot.start(auto_register=True)
        print("Robot started. Press Ctrl+C to stop.")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Stopping agent...")
            await robot.stop()
            print("Robot stopped.")

    asyncio.run(main())
