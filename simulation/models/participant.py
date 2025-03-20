# simulation/models/participant.py

import random
from dataclasses import dataclass
from simulation.utils import generate_ethereum_address
from simulation.models.enums import Role

@dataclass
class RoundData:
    id: str
    role: Role
    reward: int

class Participant:
    def __init__(self, id: str | None = None, stake: int | None = None):
        self.id = id if id else generate_ethereum_address()
        self.rounds: dict[str,RoundData] = {}
        if stake:
            self.stake = stake
        else:
            self.stake = random.randint(100000, 10000000)

    def add_to_round(self, round_id: str, role: Role) -> None:
        if round_id in self.rounds and self.rounds[round_id].role == Role.LEADER:
            return
        self.rounds[round_id] = RoundData(round_id, role, 0)

    def get_total_rewards(self) -> int:
        return sum(round.reward for round in self.rounds.values())
        
    def get_role_in_round(self, round_id: str) -> Role | None:
        return self.rounds[round_id].role

    def __repr__(self) -> str:
        return f"Participant(id={self.id}, rounds={len(self.rounds)}, total_rewards={self.get_total_rewards()})"
