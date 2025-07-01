from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import asyncio
import json
from common.config import ROBOT_MAX_MEDICATION, RobotStatus
from typing import List
import paho.mqtt.client as mqtt
import threading
from services.locationService import get_location, distance_between_points

CHARGING_STATION_LOCATION = {"x": 1.43, "y": -11.21}

# ---- ROOM COORDS PER ROBOT ----
ROBOT_LOCATIONS = {
    "robot1": {
        "Room A-101": {"x": -9.0, "y": 0.5},
        "Room B-202": {"x": 9.0, "y": -5.0},
        "Room C-303": {"x": -9.0, "y": -16.0}
    },
    "robot2": {
        "Room A-101": {"x": -9.0, "y": -2.0},
        "Room B-202": {"x": 9.0, "y": -3.0},
        "Room C-303": {"x": -9.0, "y": -18.0}
    },
    "robot3": {
        "Room A-101": {"x": -9.0, "y": -4.0},
        "Room B-202": {"x": 9.0, "y": -8.0},
        "Room C-303": {"x": -9.0, "y": -20.0}
    }
}


# ROBOT_LOCATIONS = {
#     "robot1": {
#         "Room A-101": {"x": 3.0, "y": 2.0},
#         "Room B-202": {"x": 9.0, "y": -5.0},
#         "Room C-303": {"x": -9.0, "y": -16.0}
#     },
#     "robot2": {
#         "Room A-101": {"x": -9.0, "y": -2.0},
#         "Room B-202": {"x": -3.0, "y": 1.0},
#         "Room C-303": {"x": -9.0, "y": -18.0}
#     },
#     "robot3": {
#         "Room A-101": {"x": -9.0, "y": -4.0},
#         "Room B-202": {"x": 9.0, "y": -8.0},
#         "Room C-303": {"x": 0.0, "y": 2.0}
#     }
# }


class MedicationRobotAgent(Agent):
    def __init__(self, jid, password, peer_robots: List[str], robot_name: str, battery_level: int):
        super().__init__(jid, password)
        self.robot_name = robot_name
        self.stock = ROBOT_MAX_MEDICATION.copy()
        self.peer_robots = peer_robots
        self.battery_level = battery_level
        self.robot_status = RobotStatus.AVAILABLE
        self.room_locations = ROBOT_LOCATIONS[robot_name]
        self.location = None  # Updated per task

        # --- MQTT ---
        self.mqtt_goal_succeeded = threading.Event()
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_message = self._on_mqtt_message
        self.mqtt_client.connect("broker.hivemq.com", 1883, 60)
        status_topic = f"123/meia/{self.robot_name.lower()}/status"
        self.mqtt_client.subscribe(status_topic)
        self.mqtt_client.loop_start()

    def _on_mqtt_message(self, client, userdata, msg):
        payload = msg.payload.decode()
        print(f"[{self.robot_name}] MQTT {msg.topic} → {payload}")
        try:
            data = json.loads(payload)
        except Exception:
            data = payload

        if (isinstance(data, dict) and data.get("status") == "goal_succeeded") or \
        (isinstance(data, str) and data == "goal_succeeded"):
            self.mqtt_goal_succeeded.set()
            self.robot_status = RobotStatus.AVAILABLE
            print(f"[{self.robot_name}] Estado atualizado para AVAILABLE após goal_succeeded.")

        elif (isinstance(data, dict) and data.get("status") == "goal_aborted") or \
            (isinstance(data, str) and data == "goal_aborted"):
            self.mqtt_goal_succeeded.set() 
            self.robot_status = RobotStatus.AVAILABLE
            print(f"[{self.robot_name}] Estado atualizado para AVAILABLE após goal_aborted.")


    async def setup(self):
        print(f"[{self.name}] MedicationRobotAgent setup.")
        self.add_behaviour(self.MessageReceiverBehaviour())

    class MessageReceiverBehaviour(CyclicBehaviour):
        async def on_start(self):
            print(f"[{self.agent.name}] Ready to receive tasks. Current stock: {self.agent.stock}")

        async def run(self):
            try:
                #print(f"[{self.agent.name}] [DEBUG] Ciclo de run está ativo! Estado atual: {self.agent.robot_status}")
                msg = await self.receive(timeout=10)
                if msg:
                    performative = msg.get_metadata("performative")
                    task_type = msg.get_metadata("task_type")

                    if performative == "inform" and task_type == "delivery":
                        print(f"[{self.agent.name}] Received task via message.")
                        try:
                            task = json.loads(msg.body)
                            print(f"[{self.agent.name}] Task details: {task}")
                            room = task.get("room")

                            if not room:
                                print(f"[{self.agent.name}] No 'room' in task, can't set location!")

                            peer_data = await self.ask_peers_about_location_and_status(room)

                            loc = get_location(self.agent.robot_name)
                            if loc is None:
                                print("[ERRO] Localização do robô é None! Não posso calcular distância.")
                                return
                            self_distance = distance_between_points(
                                loc[0], loc[1],
                                self.agent.room_locations[room]['x'], self.agent.room_locations[room]['y']
                            )

                            peer_candidates = [
                                p for p in peer_data
                                if p["status"] == "available"
                                and self.can_peer_fulfill(p["stock"], task["medications"])
                                and "distance_to_target" in p
                            ]

                            if peer_candidates:
                                closest = min(peer_candidates, key=lambda p: p["distance_to_target"])
                                
                                if closest["distance_to_target"] < self_distance:
                                    delegate_msg = Message(to=closest["jid"])
                                    delegate_msg.set_metadata("performative", "help_confirm")
                                    delegate_msg.body = json.dumps(task)
                                    await self.send(delegate_msg)
                                    print(f"[{self.agent.name}] Delegou a tarefa {task['ID']} para o robô mais próximo: {closest['jid']}")
                                    
                                    notice = Message(to="taskmanager@localhost")
                                    notice.set_metadata("performative", "inform")
                                    notice.set_metadata("task_type", "delegation_notice")
                                    notice.body = json.dumps({
                                        "robot": str(self.agent.jid).split("/")[0],
                                        "delegated_to": closest["jid"],
                                        "task_id": task["ID"]
                                    })
                                    await self.send(notice)
                                    return
                            if await self.can_fulfill(task["medications"]):
                                self.agent.robot_status = RobotStatus.DELIVERING
                                await self.deliver_medication(task, room)
                                print(f"[{self.agent.name}] Executou sozinho a tarefa {task['ID']}")

                            success = await self.ask_peers_for_help(task, room)
                            if success:
                                print(f"[{self.agent.name}] Dividiu a tarefa {task['ID']} com peers.")
                                return

                            print(f"[{self.agent.name}] Impossível cumprir a tarefa {task['ID']}, nem com ajuda. A devolver.")
                            fail_msg = Message(to="taskmanager@localhost")
                            fail_msg.set_metadata("performative", "inform")
                            fail_msg.set_metadata("task_type", "delivery_failed")
                            fail_msg.body = json.dumps(task)
                            await self.send(fail_msg)
                            print(f"[{self.agent.name}] Enviou devolução da tarefa {task['ID']} ao gestor.")

                        except Exception as e:
                            print(f"[{self.agent.name}] Error handling task message: {e}")

                    elif performative == "help_request":
                        await self.handle_help_request(msg)
                    elif performative == "help_confirm":
                        await self.handle_help_confirm(msg)
                    elif performative == "inform" and task_type == "availability_check":
                        await self.respond_to_availability_check(msg)
                    else:
                        print(f"[{self.agent.name}] Ignored unrelated message: performative={performative}, task_type={task_type}")
            except Exception as e:
                print(f"[{self.agent.name}] [FATAL ERROR no run()] {e}")


        async def can_fulfill(self, meds_required):
            if self.agent.battery_level < 20:
                print(f"[{self.agent.name}] Bateria baixa, não pode cumprir a tarefa.")
                await self.go_to_charging_station()
                return False
            return all(self.agent.stock.get(med, 0) >= amount for med, amount in meds_required.items())

        def can_peer_fulfill(self, stock, meds_required):
            return all(stock.get(m, 0) >= qtd for m, qtd in meds_required.items())


        async def deliver_medication(self, task, room):
            try:
                self.agent.robot_status = RobotStatus.DELIVERING
                
                
                current_location = get_location(self.agent.robot_name)
                print(f"[{self.agent.name}] Current location: {current_location}")
                
                
                room_coords = self.agent.room_locations.get(room)
                print(f"[{self.agent.name}] New Status: Delivering. Heading to {room} at {room_coords}")

                
                topic = f"123/meia/{self.agent.robot_name.lower()}/goal"
                self.agent.mqtt_goal_succeeded.clear()
                self.agent.mqtt_client.publish(topic, json.dumps(room_coords))
                print(f"[{self.agent.name}] Published goal to {topic}: {room_coords}")

                print(f"[{self.agent.name}] Waiting for goal_succeeded MQTT message...")
                await asyncio.get_event_loop().run_in_executor(None, self.agent.mqtt_goal_succeeded.wait)

                if self.agent.mqtt_goal_succeeded.is_set():
                    print(f"[{self.agent.name}] goal_succeeded received!")
                else:
                    print(f"[{self.agent.name}] MQTT goal_succeeded NOT received in time!")

                for med_type, amount in task["medications"].items():
                    self.agent.stock[med_type] -= amount

                
                msg = Message(to="taskmanager@localhost")
                msg.set_metadata("performative", "inform")
                msg.set_metadata("task_type", "delivery_complete")
                msg.body = json.dumps({"robot": str(self.agent.jid).split("/")[0]})
                await self.send(msg)
                print(f"[{self.agent.name}] Sent delivery_complete for task {task['ID']} to TaskManager.")

                self.agent.robot_status = RobotStatus.AVAILABLE
                print(f"[{self.agent.name}] Delivery complete. New stock: {self.agent.stock}. New Status: Available")
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"[{self.agent.name}] [ERRO NO DELIVER_MEDICATION] {e}")


        async def ask_peers_for_help(self, task, room):
            meds_needed = task["medications"]
            responses = []

            for peer in self.agent.peer_robots:
                msg = Message(to=peer)
                msg.set_metadata("performative", "help_request")
                msg.body = json.dumps({"medications": meds_needed, "room": room})
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
                    "room": room,
                    "medications": partial_task
                })
                await self.send(msg)
                print(f"[{self.agent.name}] Assigned part of task {task_id} to {peer} → {partial_task}")
            return True

        async def ask_peers_about_location_and_status(self, room):
            responses = []
            target_coords = self.agent.room_locations.get(room)
            if not target_coords:
                return responses

            for peer in self.agent.peer_robots:
                msg = Message(to=peer)
                msg.set_metadata("performative", "inform")
                msg.set_metadata("task_type", "availability_check")
                msg.body = room
                await self.send(msg)

            for peer in self.agent.peer_robots:
                reply = await self.receive(timeout=3)
                if reply and reply.get_metadata("task_type") == "availability_response":
                    try:
                        data = json.loads(reply.body)
                        data["jid"] = str(reply.sender)

                        location = get_location(data["jid"].split("@")[0]) 
                        if location:
                            dist = distance_between_points(location[0], location[1],
                                                          target_coords["x"], target_coords["y"])
                            data["distance_to_target"] = dist
                        else:
                            data["distance_to_target"] = float('inf')
                        responses.append(data)
                    except Exception as e:
                        print(f"[{self.agent.name}] Erro ao analisar resposta de localização: {e}")
            return responses

        async def handle_help_request(self, msg):
            try:
                data = json.loads(msg.body)
                meds = data.get("medications", {})
            except Exception:
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
            room = task.get("room")

            self.agent.robot_status = RobotStatus.DELIVERING
            print(f"[{self.agent.name}] Reservou tarefa {task['ID']} via peer. Estado → DELIVERING")

            if await self.can_fulfill(task["medications"]):
                await self.deliver_medication(task, room)
            else:
                print(f"[{self.agent.name}] Foi escolhido para a tarefa {task['ID']} mas não consegue cumprir.")
                self.agent.robot_status = RobotStatus.AVAILABLE

        async def respond_to_availability_check(self, msg):
            room = msg.body
            #print(f"[{self.agent.name}] [DEBUG] Mensagem de availability_check recebida de {msg.sender}")
            #print(f"[{self.agent.name}] [DEBUG] Pedido de availability_check recebido. Estado atual: {self.agent.robot_status}")
            reply = msg.make_reply()
            reply.set_metadata("performative", "inform")
            reply.set_metadata("task_type", "availability_response")
            reply.body = json.dumps({
                "room": self.agent.room_locations.get(room),
                "status": self.agent.robot_status.value,
                "stock": self.agent.stock,
                "battery": self.agent.battery_level
            })
            #print(f"[{self.agent.name}] Responding with status: {self.agent.robot_status.value}")
            await self.send(reply)

        async def go_to_charging_station(self):
            self.agent.robot_status = RobotStatus.CHARGING
            charging_coords = CHARGING_STATION_LOCATION
            topic = f"123/meia/{self.agent.robot_name.lower()}/goal"
            self.agent.mqtt_goal_succeeded.clear()
            self.agent.mqtt_client.publish(topic, json.dumps(charging_coords))
            print(f"[{self.agent.robot_name}] Indo para estação de carregamento em {charging_coords}...")

            print(f"[{self.agent.robot_name}] Esperando goal_succeeded para carregamento...")
            await asyncio.get_event_loop().run_in_executor(None, self.agent.mqtt_goal_succeeded.wait)

            if self.agent.mqtt_goal_succeeded.is_set():
                print(f"[{self.agent.robot_name}] Chegou à estação de carregamento!")
                self.agent.robot_status = RobotStatus.AVAILABLE
                self.agent.battery_level = 100
            else:
                print(f"[{self.agent.robot_name}] Não chegou à estação de carregamento (timeout?)")
