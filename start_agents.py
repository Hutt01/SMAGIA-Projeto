import asyncio
from agents.TaskManagementAgent import TaskManagerAgent
from agents.MedicationRobotAgent import MedicationRobotAgent
from agents.BatteryStation import BatteryStationAgent



# === Async Main Entry Point ===

if __name__ == "__main__":

    async def main():

        all_ids = ["robot1@localhost", "robot2@localhost", "robot3@localhost"]
        # all_ids = ["robot1@localhost", "robot2@localhost", "robot3@localhost","robot4@localhost"]

        def get_peers(my_id):
            return [jid for jid in all_ids if jid != my_id]
        
        task_manager = TaskManagerAgent("taskmanager@localhost", "managerpassword", all_ids)
    
        robot1 = MedicationRobotAgent("robot1@localhost", "robotpassword", get_peers("robot1@localhost"),"robot1",100)
        robot2 = MedicationRobotAgent("robot2@localhost", "robotpassword", get_peers("robot2@localhost"),"robot2",19)
        robot3 = MedicationRobotAgent("robot3@localhost", "robotpassword", get_peers("robot3@localhost"),"robot3",100)
        # robot4 = MedicationRobotAgent("robot4@localhost", "robotpassword", get_peers("robot4@localhost"))

        await asyncio.gather(
            task_manager.start(),
            robot1.start(),
            robot2.start(),
            robot3.start(),
            # robot4.start()
        )

        print("Robots started. Press Ctrl+C to stop.")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Stopping agents...")
            await task_manager.stop()
            await robot1.stop()
            await robot2.stop()
            await robot3.stop()
            # await robot4.stop()
            print("Robots stopped.")

    asyncio.run(main())
