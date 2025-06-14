from spade.agent import Agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour
from spade.message import Message
import requests
import json
from typing import Dict, List
from common.config import APP_API_URL, ROBOT_MAX_MEDICATION
import asyncio
from copy import deepcopy

class MedicationRobotAgent(Agent):
    def __init__(self, jid, password, peer_robots: List[str], *args, **kwargs):
        super().__init__(jid, password, *args, **kwargs)
        self.peer_robots = peer_robots
        self.medication_stock = deepcopy(ROBOT_MAX_MEDICATION)
        self.task_map = {}
        self.reserved_stock = {k: 0 for k in self.medication_stock}
        self.pending_tasks = set()

    class ReceiveTasksBehaviour(OneShotBehaviour):
        async def run(self):
            tasks = self.fetch_pending_tasks()
            for task in tasks:
                self.agent.add_behaviour(self.agent.CFPTaskBehaviour(task))

        def fetch_pending_tasks(self) -> List[Dict]:
            response = requests.get(f"{APP_API_URL}/pending_tasks")
            if response.status_code == 200:
                tasks = response.json().get("pending_tasks", [])
                for i, task in enumerate(tasks):
                    task["ID"] = f"task_{i+1:03}"
                return tasks
            else:
                print(f"Failed to fetch tasks, status code: {response.status_code}")
                return []

    class DelayedTaskStartBehaviour(OneShotBehaviour):
        def __init__(self, delay: int = 5):
            super().__init__()
            self.delay = delay

        async def run(self):
            await asyncio.sleep(self.delay)
            self.agent.add_behaviour(self.agent.ReceiveTasksBehaviour())

    class CFPTaskBehaviour(OneShotBehaviour):
        def __init__(self, task: Dict):
            super().__init__()
            self.task = task

        async def run(self):
            task_id = self.task["ID"]
            print(f"[{self.agent.name}] Broadcasting CFP for task: {self.task}")
            self.agent.task_map[task_id] = self.task
            for peer in self.agent.peer_robots:
                msg = Message(to=peer)
                msg.set_metadata("performative", "cfp")
                msg.set_metadata("type", "task")
                msg.body = json.dumps(self.task)
                await self.send(msg)

            self.agent.add_behaviour(self.agent.ProposalDecisionBehaviour(task_id))

    class ReceiveCFPBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg and msg.get_metadata("performative") == "cfp":
                task = json.loads(msg.body)
                print(f"[{self.agent.name}] Received CFP from {msg.sender}: {task}")
                task_id = task.get("ID")
                self.agent.task_map[task_id] = task

                can_do = self.agent.can_perform_task(task)
                reply = msg.make_reply()
                if can_do:
                    estimated_cost = self.agent.estimate_cost(task)
                    reply.set_metadata("performative", "propose")
                    reply.body = json.dumps({"cost": estimated_cost, "ID": task_id})

                    for med, qty in task.get("medications", {}).items():
                        self.agent.reserved_stock[med] += qty
                    self.agent.pending_tasks.add(task_id)
                else:
                    reply.set_metadata("performative", "refuse")
                await self.send(reply)

    class ReceiveProposalBehaviour(CyclicBehaviour):
        def __init__(self):
            super().__init__()
            self.proposals = {}

        async def run(self):
            msg = await self.receive(timeout=10)
            if msg and msg.get_metadata("performative") == "propose":
                sender = str(msg.sender)
                proposal = json.loads(msg.body)
                task_id = proposal.get("ID")

                if not task_id or "cost" not in proposal:
                    return

                if task_id not in self.proposals:
                    self.proposals[task_id] = {}

                self.proposals[task_id][sender] = proposal

    class ProposalDecisionBehaviour(OneShotBehaviour):
        def __init__(self, task_id: str, delay: int = 3):
            super().__init__()
            self.task_id = task_id
            self.delay = delay

        async def run(self):
            await asyncio.sleep(self.delay)
            proposals = self.agent.receive_proposal_behaviour.proposals.get(self.task_id)
            task = self.agent.task_map.get(self.task_id)
            print(f"[{self.agent.name}] Proposals for {self.task_id}: {proposals}")
            if not proposals or not task:
                print(f"[{self.agent.name}] No proposals or missing task for {self.task_id}")
                return

            best = min(proposals.items(), key=lambda x: x[1]["cost"])
            winner = best[0]

            for peer in proposals:
                reply = Message(to=peer)
                if peer == winner:
                    reply.set_metadata("performative", "accept-proposal")
                    reply.body = json.dumps(task)
                else:
                    reply.set_metadata("performative", "reject-proposal")
                    reply.body = json.dumps(task)
                await self.send(reply)

            print(f"[{self.agent.name}] Selected winner {winner} for {self.task_id}")
            del self.agent.receive_proposal_behaviour.proposals[self.task_id]
            del self.agent.task_map[self.task_id]

    class AcceptTaskBehaviour(CyclicBehaviour):
        def __init__(self):
            super().__init__()
            self.completed_tasks = set()

        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                performative = msg.get_metadata("performative")
                task = json.loads(msg.body)
                task_id = task.get("ID")

                if performative == "accept-proposal":
                    if task_id in self.completed_tasks:
                        print(f"[{self.agent.name}] Task {task_id} already completed.")
                        return
                    print(f"[{self.agent.name}] Task accepted: {task}")
                    self.agent.perform_task(task)
                    self.completed_tasks.add(task_id)
                    self.agent.pending_tasks.discard(task_id)

                elif performative == "reject-proposal":
                    if task_id in self.agent.pending_tasks:
                        print(f"[{self.agent.name}] Proposal rejected: {task_id}")
                        for med, qty in task.get("medications", {}).items():
                            self.agent.reserved_stock[med] -= qty
                        self.agent.pending_tasks.discard(task_id)

    def can_perform_task(self, task: Dict) -> bool:
        for med, qty in task.get("medications", {}).items():
            available = self.medication_stock.get(med, 0) - self.reserved_stock.get(med, 0)
            if available < qty:
                return False
        return True

    def estimate_cost(self, task: Dict) -> int:
        return sum(task.get("medications", {}).values())

    def perform_task(self, task: Dict):
        for med, qty in task.get("medications", {}).items():
            self.medication_stock[med] -= qty
        print(f"[{self.name}] Task completed. Remaining stock: {self.medication_stock}")

    async def setup(self):
        print(f"[{self.name}] Agent starting...")
        if self.name == "robot1":
            self.add_behaviour(self.DelayedTaskStartBehaviour())

        self.receive_proposal_behaviour = self.ReceiveProposalBehaviour()
        self.add_behaviour(self.ReceiveCFPBehaviour())
        self.add_behaviour(self.receive_proposal_behaviour)
        self.add_behaviour(self.AcceptTaskBehaviour())


if __name__ == "__main__":
    async def main():
        all_ids = ["robot1@localhost", "robot2@localhost", "robot3@localhost"]

        def get_peers(my_id):
            return [jid for jid in all_ids if jid != my_id]

        robot1 = MedicationRobotAgent("robot1@localhost", "robotpassword", get_peers("robot1@localhost"))
        robot2 = MedicationRobotAgent("robot2@localhost", "robotpassword", get_peers("robot2@localhost"))
        robot3 = MedicationRobotAgent("robot3@localhost", "robotpassword", get_peers("robot3@localhost"))

        await asyncio.gather(
            robot1.start(auto_register=True),
            robot2.start(auto_register=True),
            robot3.start(auto_register=True),
        )

        print("Robots started.")
        await asyncio.sleep(10)

        input("Press Enter to stop the agents...\n")
        await robot1.stop()
        await robot2.stop()
        await robot3.stop()
        print("Robots stopped.")

    asyncio.run(main())
