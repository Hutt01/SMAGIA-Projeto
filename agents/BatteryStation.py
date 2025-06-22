from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import asyncio
import json
from common.config import ROBOT_MAX_MEDICATION, RobotStatus
from typing import List

class BatteryStationAgent(Agent):
    def __init__(self, jid, password, peer_robots: List[str]):
        super().__init__(jid, password)
        self.location = [[0,0,0], [1,1,1]]  # Placeholder for battery station location
        self.peer_robots = peer_robots
        
    async def setup(self):
        print(f"[{self.name}] Battery Station setup.")
        self.add_behaviour(self.BatteryBehaviour())

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