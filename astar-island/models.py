from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Settlement:
    x: int
    y: int
    population: Optional[float] = None
    food: Optional[float] = None
    wealth: Optional[float] = None
    defense: Optional[float] = None
    has_port: Optional[bool] = None
    alive: Optional[bool] = None
    owner_id: Optional[int] = None


@dataclass
class SimulationResult:
    grid: list[list[int]]
    settlements: list[Settlement]
    viewport: dict
    queries_used: int
    queries_max: int

    @staticmethod
    def sim_code_to_class(code: int) -> int:
        return {10: 0, 11: 0, 0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5}[code]


@dataclass
class InitialState:
    grid: list[list[int]]
    settlements: list[Settlement]


@dataclass
class Round:
    id: str
    round_number: int
    status: str
    map_width: int
    map_height: int
    prediction_window_minutes: int
    started_at: str
    closes_at: str
    round_weight: float
    seeds_count: int = 5
    initial_states: Optional[list[InitialState]] = None


@dataclass
class SeedObservation:
    seed_index: int
    viewport_x: int
    viewport_y: int
    viewport_w: int
    viewport_h: int
    result: SimulationResult
