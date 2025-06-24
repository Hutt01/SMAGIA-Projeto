from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import asyncio
import json
from common.config import ROBOT_MAX_MEDICATION, RobotStatus
from typing import List
from services.locationService import get_location_mock

class MedicationRobotAgent(Agent):
    def __init__(self, jid, password, peer_robots: List[str]):
        super().__init__(jid, password)
        self.stock = ROBOT_MAX_MEDICATION.copy()
        self.peer_robots = peer_robots
        self.battery_level = 100
        self.robot_status = RobotStatus.AVAILABLE
        self.location = get_location_mock()

    async def setup(self):
        print(f"[{self.name}] MedicationRobotAgent setup.")
        self.add_behaviour(self.MessageReceiverBehaviour())
        self.add_behaviour(self.BatteryBehaviour())

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

                        peer_data = await self.ask_peers_about_location_and_status(task["location"])
                        for peer in peer_data:
                            if peer["status"] in ["available", "delivering"]:
                                if self.can_peer_fulfill(peer["stock"], task["medications"]):
                                    
                                    msg = Message(to=peer["jid"])
                                    msg.set_metadata("performative", "help_confirm")
                                    msg.body = json.dumps(task)
                                    await self.send(msg)
                                    print(f"[{self.agent.name}] Delegou a tarefa {task['ID']} para {peer['jid']}")
                                    return

                        success = await self.ask_peers_for_help(task)
                        if success:
                            print(f"[{self.agent.name}] Dividiu a tarefa {task['ID']} com peers.")
                            return

                        if self.can_fulfill(task["medications"]):
                            self.agent.robot_status = RobotStatus.DELIVERING
                            await self.deliver_medication(task)
                            print(f"[{self.agent.name}] Executou sozinho a tarefa {task['ID']}")
                        else:
                            print(f"[{self.agent.name}] Impossível cumprir a tarefa {task['ID']}, nem com ajuda. A devolver.")
                            msg = Message(to="taskmanager@localhost") 
                            msg.set_metadata("performative", "inform")
                            msg.set_metadata("task_type", "delivery_failed")
                            msg.body = json.dumps(task)
                            await self.send(msg)
                            print(f"[{self.agent.name}] Enviou devolução da tarefa {task['ID']} ao gestor.")

                    except Exception as e:
                        print(f"[{self.agent.name}] Error handling task message: {e}")

                elif performative == "inform" and task_type == "availability":
                    print(f"[{self.agent.name}] Received availability request from {msg.sender}")
                    availability_info = {
                        "stock": self.agent.stock,
                        "status": self.agent.robot_status.value,
                        "battery": self.agent.battery_level,
                        "location": get_location_mock()
                    }
                    reply = msg.make_reply()
                    reply.set_metadata("performative", "inform")
                    reply.set_metadata("task_type", "availability_response")
                    reply.body = json.dumps(availability_info)
                    await self.send(reply)
                    print(f"[{self.agent.name}] Sent availability info to {msg.sender}")


                elif performative == "help_request":
                    await self.handle_help_request(msg)

                elif performative == "help_confirm":
                    await self.handle_help_confirm(msg)

                elif performative == "inform" and task_type == "availability_check":
                    await self.respond_to_availability_check(msg)

                else:
                    print(f"[{self.agent.name}] Ignored unrelated message: performative={performative}, task_type={task_type}")

        def can_fulfill(self, meds_required):
            return all(self.agent.stock.get(med, 0) >= amount for med, amount in meds_required.items())
        
        async def deliver_medication(self, task):
            self.agent.robot_status = RobotStatus.DELIVERING 
            print(f"[{self.agent.name}] New Status: Delivering")

            for med_type, amount in task["medications"].items():
                self.agent.stock[med_type] -= amount
            await asyncio.sleep(3)
            print(f"[{self.agent.name}] Delivery complete. New stock: {self.agent.stock}. New Status: Available")
            self.agent.robot_status = RobotStatus.AVAILABLE 

        async def ask_peers_for_help(self, task):
            meds_needed = task["medications"]
            responses = []

            for peer in self.agent.peer_robots:
                msg = Message(to=peer)
                msg.set_metadata("performative", "help_request")
                msg.body = json.dumps(meds_needed)
                await self.send(msg)

            for _ in self.agent.peer_robots:
                res = await self.receive(timeout=3)
                if res and res.metadata.get("performative") == "help_response":
                    available = json.loads(res.body)
                    responses.append((str(res.sender), available))

            if not responses:
                print(f"[{self.agent.name}] No peer responded to help request.")
                return False

            task_id = task["ID"]
            remaining = meds_needed.copy()
            assignments = {}

            for sender, offer in responses:
                contribution = {}
                for med, amount in remaining.items():
                    if med in offer and offer[med] > 0:
                        give = min(offer[med], remaining[med])
                        if give > 0:
                            contribution[med] = give
                            remaining[med] -= give
                if contribution:
                    assignments[sender] = contribution

                if all(v == 0 for v in remaining.values()):
                    break

            if not all(v == 0 for v in remaining.values()):
                print(f"[{self.agent.name}] Not enough peer capacity to split task {task_id}.")
                return False

            for peer, partial_task in assignments.items():
                msg = Message(to=peer)
                msg.set_metadata("performative", "help_confirm")
                msg.body = json.dumps({
                    "ID": task_id,
                    "location": task["location"],
                    "medications": partial_task
                })
                await self.send(msg)
                print(f"[{self.agent.name}] Assigned part of task {task_id} to {peer} → {partial_task}")
            return True

        async def ask_peers_about_location_and_status(self, delivery_location):
            responses = []
            for peer in self.agent.peer_robots:
                msg = Message(to=peer)
                msg.set_metadata("performative", "inform")
                msg.set_metadata("task_type", "availability_check")
                msg.body = delivery_location
                await self.send(msg)

            for _ in self.agent.peer_robots:
                reply = await self.receive(timeout=3)
                if reply and reply.get_metadata("task_type") == "availability_response":
                    try:
                        data = json.loads(reply.body)
                        data["jid"] = str(reply.sender)
                        responses.append(data)
                    except Exception as e:
                        print(f"[{self.agent.name}] Erro ao analisar resposta de localização: {e}")
            return responses

        async def handle_help_request(self, msg):
            meds = json.loads(msg.body)
            offer = {}
            for med, amount in meds.items():
                available = self.agent.stock.get(med, 0)
                if available > 0:
                    offer[med] = available
            reply = Message(to=str(msg.sender))
            reply.set_metadata("performative", "help_response")
            reply.body = json.dumps(offer)
            await self.send(reply)

        async def handle_help_confirm(self, msg):
            task = json.loads(msg.body)
            if self.can_fulfill(task["medications"]):
                await self.deliver_medication(task)
            else:
                print(f"[{self.agent.name}] Was asked to do {task['ID']} but cannot fulfill it.")

        async def respond_to_availability_check(self, msg):
            delivery_location = msg.body
            reply = msg.make_reply()
            reply.set_metadata("performative", "inform")
            reply.set_metadata("task_type", "availability_response")
            reply.body = json.dumps({
                "location": self.agent.location,
                "status": self.agent.robot_status.value,
                "stock": self.agent.stock,
                "battery": self.agent.battery_level
            })
            await self.send(reply)

        def can_peer_fulfill(self, stock, meds_required):
            return all(stock.get(m, 0) >= qtd for m, qtd in meds_required.items())
    class BatteryBehaviour(CyclicBehaviour):
        async def run(self):
            print(f"[{self.agent.name}] Battery level: {self.agent.battery_level}%")
            if self.agent.battery_level < 20 and self.agent.robot_status != RobotStatus.CHARGING:
                print(f"[{self.agent.name}] Battery low. Returning to charging station.")
                self.agent.robot_status = RobotStatus.CHARGING
                await self.agent.return_to_charging_station()
            self.agent.battery_level -= 1
            await asyncio.sleep(10)

    async def return_to_charging_station(self):
        print(f"[{self.name}] Returning to charging station...")
        await asyncio.sleep(5)
        print(f"[{self.name}] Reached charging station. Battery recharged.")
        self.battery_level = 100
        self.robot_status = RobotStatus.AVAILABLE
