import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour
from spade.message import Message
import random
import asyncio


class RoboAgente(Agent):
    class ReceberTarefa(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg and msg.metadata.get("performative") == "tarefa":
                print(f"[{self.agent.name}] Recebi tarefa: {msg.body}")
                custo = random.randint(1, 10)
                print(f"[{self.agent.name}] Custo: {custo}")
                resposta = Message(to=str(msg.sender))
                resposta.set_metadata("performative", "proposta")
                resposta.body = f"{self.agent.name}:{custo}"
                await self.send(resposta)

    async def setup(self):
        print(f"{self.jid} iniciado.")
        self.add_behaviour(self.ReceberTarefa())


class GestorAgente(Agent):
    class EnviarTarefa(OneShotBehaviour):
        async def run(self):
            print("[GESTOR] A enviar tarefa para os robôs...")
            # Enviar tarefa
            for robot in self.agent.robots:
                msg = Message(to=robot)
                msg.set_metadata("performative", "tarefa")
                msg.body = "Entrega no quarto 203"
                await self.send(msg)

            # Esperar propostas
            propostas = []
            for _ in range(len(self.agent.robots)):
                resposta = await self.receive(timeout=10)
                if resposta:
                    print(f"[GESTOR] Proposta recebida: {resposta.body}")
                    propostas.append(resposta.body)

            if propostas:
                melhor = min(propostas, key=lambda x: int(x.split(":")[1]))
                print(f"[GESTOR] Melhor proposta: {melhor}")
            else:
                print("[GESTOR] Nenhuma proposta recebida.")

    async def setup(self):
        print(f"{self.jid} iniciado.")
        self.robots = [
            "robo1@localhost",
            "robo2@localhost"
        ]
        self.add_behaviour(self.EnviarTarefa())


async def main():
    # Criar agentes com as mesmas passwords do Prosody local
    gestor = GestorAgente("gestor@localhost", "123")
    robo1 = RoboAgente("robo1@localhost", "123")
    robo2 = RoboAgente("robo2@localhost", "123")

    await robo1.start(auto_register=True)
    await robo2.start(auto_register=True)
    await gestor.start(auto_register=True)

    # Esperar pela conclusão
    await asyncio.sleep(10)

    await robo1.stop()
    await robo2.stop()
    await gestor.stop()

if __name__ == "__main__":
    spade.run(main())
