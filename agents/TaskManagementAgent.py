from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import asyncio
import requests
import json
from common.config import APP_API_URL
from agents.MedicationRobotAgent import MedicationRobotAgent

print("A iniciar os agentes...")

class TaskManagerAgent(Agent):
    def __init__(self, jid, password, robot_ids):
        super().__init__(jid, password)
        self.robot_ids = robot_ids
        self.reserved_robots = set()
        self.pending = [] 

    async def setup(self):
        print(f"[{self.name}] TaskManagerAgent setup.")
        self.add_behaviour(self.TaskFetcherAndDispatcherBehaviour())

    class TaskFetcherAndDispatcherBehaviour(CyclicBehaviour):
        async def on_start(self):
            print(f"[{self.agent.name}] Task dispatcher started. Polling API at {APP_API_URL}")
            await asyncio.sleep(5)

        async def run(self):
            msg = await self.receive(timeout=1)
            if msg and msg.get_metadata("task_type") == "delivery_failed":
                failed_task = json.loads(msg.body)
                print(f"[{self.agent.name}] Tarefa devolvida recebida: {failed_task['ID']}. Reenfileirada.")
                self.agent.pending.append(failed_task)

            if self.agent.pending:
                task = self.agent.pending.pop(0)
                await self.dispatch_task(task)
                return

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
            respostas = []

            
            for robot_jid in self.agent.robot_ids:
                msg = Message(to=robot_jid)
                msg.set_metadata("performative", "inform")
                msg.set_metadata("task_type", "availability_check")
                msg.body = task.get("room", "")  
                await self.send(msg)

            
            for _ in self.agent.robot_ids:
                response = await self.receive(timeout=3)
                if response and response.get_metadata("task_type") == "availability_response":
                    try:
                        data = json.loads(response.body)
                        data["jid"] = str(response.sender)
                        respostas.append(data)
                    except Exception as e:
                        print(f"[{self.agent.name}] Erro ao processar disponibilidade: {e}")

            
            respostas_disponiveis = [r for r in respostas if r.get("status") == "available" and r["jid"] not in self.agent.reserved_robots]

            if not respostas_disponiveis:
                print(f"[{self.agent.name}] No robot is available for task {task['ID']}. Added {task['ID']} to the task pile again.")
                self.agent.pending.append(task)
                return

            
            melhor = max(respostas_disponiveis, key=lambda r: r.get("battery", 0))
            robot_jid = melhor["jid"]

           
            confirm_msg = Message(to=robot_jid)
            confirm_msg.set_metadata("performative", "inform")
            confirm_msg.set_metadata("task_type", "availability_check")
            confirm_msg.body = task.get("room", "")
            await self.send(confirm_msg)

            confirm_response = await self.receive(timeout=2)
            if confirm_response and confirm_response.get_metadata("task_type") == "availability_response":
                confirm_data = json.loads(confirm_response.body)
                if confirm_data.get("status") == "available":
                    msg = Message(to=robot_jid)
                    msg.set_metadata("performative", "inform")
                    msg.set_metadata("task_type", "delivery")
                    msg.body = json.dumps(task)
                    await self.send(msg)
                    print(f"[{self.agent.name}] Atribuiu a tarefa {task['ID']} ao robô {robot_jid}")
                    return

            
            print(f"[{self.agent.name}] Robot {robot_jid} became unavailable. Added {task['ID']} to the task pile again")
            self.agent.pending.append(task)


