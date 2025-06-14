import asyncio
from agents.TaskManagementAgent import TaskManagerAgent
from agents.robot3 import MedicationRobotAgent

async def main():
    # Define robot JIDs and passwords
    robot1_jid = "robot1@localhost"
    robot1_pass = "robotpass"

    robot2_jid = "robot2@localhost"
    robot2_pass = "robotpass"

    manager_jid = "manager@localhost"
    manager_pass = "managerpass"

    # Create agents
    robot1 = MedicationRobotAgent(robot1_jid, robot1_pass, peer_robots=[robot2_jid])
    robot2 = MedicationRobotAgent(robot2_jid, robot2_pass, peer_robots=[robot1_jid])
    manager = TaskManagerAgent(manager_jid, manager_pass, robot_ids=[robot1_jid, robot2_jid])

    # Start agents with await
    await robot1.start(auto_register=True)
    await robot2.start(auto_register=True)
    await manager.start(auto_register=True)

    print("[System] Agents started. Press Ctrl+C to exit.")

    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
