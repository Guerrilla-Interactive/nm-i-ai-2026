from __future__ import annotations

import time

import httpx

try:
    from . import config
    from .models import InitialState, Round, Settlement, SimulationResult
except ImportError:
    import config
    from models import InitialState, Round, Settlement, SimulationResult


class AstarClient:
    def __init__(self, token: str | None = None):
        self._token = token or config.TOKEN
        self._client = httpx.Client(
            base_url=config.API_BASE,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=30.0,
        )
        self._last_simulate = 0.0
        self._last_submit = 0.0

    def _request(self, method: str, path: str, **kwargs) -> dict | list:
        max_attempts = 3
        for attempt in range(max_attempts):
            resp = self._client.request(method, path, **kwargs)
            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return resp.json()

    # -- Round endpoints --

    def get_rounds(self) -> list[Round]:
        data = self._request("GET", "/rounds")
        return [self._parse_round(r) for r in data]

    def get_round(self, round_id: str) -> Round:
        data = self._request("GET", f"/rounds/{round_id}")
        return self._parse_round(data)

    def get_active_round(self) -> Round | None:
        for r in self.get_rounds():
            if r.status == "active":
                return self.get_round(r.id)
        return None

    # -- Budget --

    def get_budget(self) -> dict:
        return self._request("GET", "/budget")

    # -- Simulate --

    def simulate(
        self,
        round_id: str,
        seed_index: int,
        x: int,
        y: int,
        w: int = 15,
        h: int = 15,
    ) -> SimulationResult:
        # Rate limiting
        elapsed = time.time() - self._last_simulate
        if elapsed < config.SIMULATE_DELAY:
            time.sleep(config.SIMULATE_DELAY - elapsed)

        data = self._request(
            "POST",
            "/simulate",
            json={
                "round_id": round_id,
                "seed_index": seed_index,
                "viewport_x": x,
                "viewport_y": y,
                "viewport_w": w,
                "viewport_h": h,
            },
        )
        self._last_simulate = time.time()

        settlements = [Settlement(**s) for s in data.get("settlements", [])]
        return SimulationResult(
            grid=data["grid"],
            settlements=settlements,
            viewport=data.get("viewport", {"x": x, "y": y, "w": w, "h": h}),
            queries_used=data["queries_used"],
            queries_max=data["queries_max"],
        )

    # -- Submit --

    def submit(self, round_id: str, seed_index: int, prediction: list) -> dict:
        # Rate limiting
        elapsed = time.time() - self._last_submit
        if elapsed < config.SUBMIT_DELAY:
            time.sleep(config.SUBMIT_DELAY - elapsed)

        result = self._request(
            "POST",
            "/submit",
            json={
                "round_id": round_id,
                "seed_index": seed_index,
                "prediction": prediction,
            },
        )
        self._last_submit = time.time()
        return result

    # -- Info endpoints --

    def get_my_rounds(self) -> list:
        return self._request("GET", "/my-rounds")

    def get_leaderboard(self) -> list:
        return self._request("GET", "/leaderboard")

    # -- Helpers --

    @staticmethod
    def _parse_round(data: dict) -> Round:
        initial_states = None
        if "initial_states" in data and data["initial_states"]:
            initial_states = []
            for state in data["initial_states"]:
                settlements = [Settlement(**s) for s in state.get("settlements", [])]
                initial_states.append(
                    InitialState(grid=state["grid"], settlements=settlements)
                )
        return Round(
            id=data["id"],
            round_number=data["round_number"],
            status=data["status"],
            map_width=data["map_width"],
            map_height=data["map_height"],
            prediction_window_minutes=data["prediction_window_minutes"],
            started_at=data["started_at"],
            closes_at=data["closes_at"],
            round_weight=data["round_weight"],
            seeds_count=data.get("seeds_count", 5),
            initial_states=initial_states,
        )
