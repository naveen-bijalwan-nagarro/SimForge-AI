"""Agent-based populations (Mesa) that react to a world's incident and decisions.

The SimPy world models systems and queues; these Mesa models add autonomous populations:
people in an epidemic, drones in a fleet, vehicles at junctions, traders in a market and
accounts in a fraud ring. The shock starts at the world's incident minute and is mitigated
when the learner commits the root-cause repair, so decisions change population outcomes.
"""

import random

import networkx as nx

try:  # Mesa is the preferred engine; a tiny compatible fallback keeps tests portable.
    import mesa

    Agent, Model = mesa.Agent, mesa.Model
    ENGINE = f"Mesa {getattr(mesa, '__version__', '')}".strip()
except ImportError:  # pragma: no cover - exercised only without Mesa installed
    ENGINE = "built-in agent loop"

    class _AgentSet(list):
        def shuffle_do(self, method):
            items = list(self)
            self.model.random.shuffle(items)
            for a in items:
                getattr(a, method)()

    class Model:  # type: ignore[no-redef]
        def __init__(self, rng=None):
            self.random = random.Random(rng)
            self.agents = _AgentSet()
            self.agents.model = self

    class Agent:  # type: ignore[no-redef]
        def __init__(self, model):
            self.model = model
            self.random = model.random
            model.agents.append(self)


MODELS = {
    "pandemic": "SEIR people on a small-world contact network",
    "drones": "Drone fleet with batteries, links and coverage tasks",
    "traffic": "Vehicles at signalized junctions with violations",
    "market": "Noise, momentum and market-maker trader agents",
    "fraud": "Accounts, devices and coordinated mule transfers",
}
# Which worlds get which population model.
ASSIGNMENT = {
    "pandemic_command": "pandemic",
    "hospital_twin": "pandemic",
    "hospital_emergency": "pandemic",
    "drone_mission": "drones",
    "drone_swarm": "drones",
    "drone_inspection": "drones",
    "autonomous_fleet": "drones",
    "traffic_violations": "traffic",
    "traffic_crisis": "traffic",
    "open_world_city": "traffic",
    "financial_market": "market",
    "fraud_ring": "fraud",
    "mmorpg_economy": "fraud",
    "aml_network": "fraud",
}


class Base(Model):
    def __init__(self, seed, shock_at, severity, mitigated_at):
        super().__init__(rng=seed)
        self.t = 0
        self.shock_at, self.severity, self.mitigated_at = shock_at, severity, mitigated_at
        self.events = []

    @property
    def shocked(self):
        return self.t >= self.shock_at and (self.mitigated_at is None or self.t < self.mitigated_at)

    def log(self, message, agent=None):
        self.events.append(dict(t=self.t, agent=agent, message=message))


# ---------------------------------------------------------------- pandemic (SEIR)
class Person(Agent):
    def __init__(self, model, node):
        super().__init__(model)
        self.node, self.state, self.days = node, "S", 0
        self.risk = self.random.random()

    def step(self):
        m = self.model
        if self.state == "I":
            contacts = list(m.graph.neighbors(self.node))
            beta = 0.06 * (1 + 1.6 * m.severity if m.t >= m.shock_at else 1)
            if m.mitigated_at is not None and m.t >= m.mitigated_at:
                beta *= 0.45
            for c in contacts:
                other = m.people[c]
                if other.state == "S" and self.random.random() < beta:
                    other.state, other.days = "E", 0
            self.days += 1
            if self.days > 6:
                self.state = "H" if self.risk > 0.93 else "R"
                self.days = 0
                if self.state == "H":
                    m.log("Person hospitalised", self.unique_id if hasattr(self, "unique_id") else None)
        elif self.state == "E":
            self.days += 1
            if self.days > 2:
                self.state, self.days = "I", 0
        elif self.state == "H":
            self.days += 1
            if self.days > 8:
                self.state = "R"


class Pandemic(Base):
    def __init__(self, seed, n, shock_at, severity, mitigated_at):
        super().__init__(seed, shock_at, severity, mitigated_at)
        self.graph = nx.watts_strogatz_graph(n, 6, 0.08, seed=seed)
        self.people = [Person(self, i) for i in range(n)]
        for p in self.random.sample(self.people, max(2, n // 150)):
            p.state = "I"

    def step(self):
        if self.t == self.shock_at:
            seeds = [p for p in self.people if p.state == "S"]
            for p in self.random.sample(seeds, min(len(seeds), max(3, int(len(seeds) * 0.01 * (1 + self.severity))))):
                p.state = "E"
            self.log("New variant introduced at a transport hub")
        self.agents.shuffle_do("step")
        self.t += 1

    def observe(self):
        counts = {s: 0 for s in "SEIHR"}
        for p in self.people:
            counts[p.state] += 1
        return dict(t=self.t, susceptible=counts["S"], exposed=counts["E"], infectious=counts["I"], hospitalised=counts["H"], recovered=counts["R"])


# ---------------------------------------------------------------- drone fleet
class Drone(Agent):
    def __init__(self, model, index):
        super().__init__(model)
        self.index, self.battery, self.state = index, 100.0, "flying"
        self.weak = index % 5 == 0
        self.x, self.y = self.random.uniform(0, 100), self.random.uniform(0, 100)

    def step(self):
        m = self.model
        if self.state == "landed":
            return
        drain = 1.4 + (2.6 * m.severity if self.weak and m.shocked else 0)
        if self.state == "charging":
            self.battery = min(100, self.battery + 8)
            if self.battery >= 95:
                self.state = "flying"
            return
        self.battery -= drain
        self.x = (self.x + self.random.uniform(-4, 6)) % 100
        self.y = (self.y + self.random.uniform(-4, 6)) % 100
        link_lost = m.shocked and self.random.random() < 0.04 * m.severity
        if self.battery < 8:
            self.state = "landed"
            m.log(f"Drone D-{self.index:02d} forced landing (battery {self.battery:.0f}%)", self.index)
        elif self.battery < 25 or link_lost:
            self.state = "charging"
            if link_lost:
                m.log(f"Drone D-{self.index:02d} lost link; returning to launch", self.index)


class Fleet(Base):
    def __init__(self, seed, n, shock_at, severity, mitigated_at):
        super().__init__(seed, shock_at, severity, mitigated_at)
        self.drones = [Drone(self, i) for i in range(min(n, 60))]
        self.covered = {}

    def step(self):
        if self.mitigated_at is not None and self.t == self.mitigated_at:
            for d in self.drones:
                d.weak = False
                if d.state == "landed":
                    d.state, d.battery = "charging", 30
            self.log("Weak battery packs swapped; landed drones recovered")
        self.agents.shuffle_do("step")
        for d in self.drones:
            if d.state == "flying":
                self.covered[(int(d.x // 10), int(d.y // 10))] = self.t
        self.t += 1

    def observe(self):
        states = [d.state for d in self.drones]
        return dict(t=self.t, flying=states.count("flying"), charging=states.count("charging"), landed=states.count("landed"), coverage_pct=sum(1 for v in self.covered.values() if v >= self.t - 5))


# ---------------------------------------------------------------- traffic junctions
class Vehicle(Agent):
    def __init__(self, model, index):
        super().__init__(model)
        self.index = index
        self.aggressive = self.random.random() < 0.12

    def step(self):
        m = self.model
        amber = 3.5 if not m.shocked else 3.5 - 1.4 * m.severity
        arriving_on_red = self.random.random() < 0.18
        if arriving_on_red:
            run_chance = (0.02 + (0.25 if self.aggressive else 0.0)) * (3.5 / amber) ** 3
            if self.random.random() < run_chance:
                m.violations += 1
                if len(m.events) < 60:
                    m.log(f"Vehicle V-{self.index:04d} red-light violation", self.index)
            else:
                m.queue += 1


class Junctions(Base):
    def __init__(self, seed, n, shock_at, severity, mitigated_at):
        super().__init__(seed, shock_at, severity, mitigated_at)
        self.vehicles = [Vehicle(self, i) for i in range(min(n, 800))]
        self.violations = self.queue = 0

    def step(self):
        self.violations = self.queue = 0
        self.agents.shuffle_do("step")
        self.t += 1

    def observe(self):
        return dict(t=self.t, violations=self.violations, queued=self.queue, collisions_risk=round(self.violations * 0.08, 2))


# ---------------------------------------------------------------- market
class Trader(Agent):
    def __init__(self, model, style):
        super().__init__(model)
        self.style = style

    def step(self):
        m = self.model
        if self.style == "maker":
            # During the shock most market makers stop quoting.
            if not m.shocked or self.random.random() < 0.2:
                m.depth += 1
        elif self.style == "value":
            m.orders += 1 if m.price < 97 else -1 if m.price > 103 else 0
        elif self.style == "momentum":
            follow = self.random.random() < 0.6
            direction = (1 if m.momentum > 0 else -1) if follow else self.random.choice([-1, 1])
            m.orders += direction
        else:
            m.orders += self.random.choice([-1, 1])


class Market(Base):
    def __init__(self, seed, n, shock_at, severity, mitigated_at):
        super().__init__(seed, shock_at, severity, mitigated_at)
        count = min(n, 600)
        styles = ["maker", "value", "momentum", "noise", "noise", "value"]
        for i in range(count):
            Trader(self, styles[i % len(styles)])
        self.price, self.momentum, self.spread = 100.0, 0.0, 0.02

    def step(self):
        self.orders, self.depth = 0, 0
        self.agents.shuffle_do("step")
        depth = max(1, self.depth)
        impact = max(-5.0, min(5.0, self.orders / (depth * 1.5)))
        if self.t == self.shock_at:
            impact -= 4 * self.severity
            self.log("Market maker withdraws quotes; spreads widen")
        if self.mitigated_at is not None and self.t == self.mitigated_at:
            self.log("Designated liquidity providers re-engaged")
        self.price = max(1.0, self.price * (1 + impact / 100))
        self.momentum = impact
        self.spread = round(0.02 * (100 / (depth + 1)), 3)
        self.t += 1

    def observe(self):
        return dict(t=self.t, price=round(self.price, 2), spread=self.spread, order_imbalance=self.orders, liquidity=self.depth)


# ---------------------------------------------------------------- fraud ring
class Account(Agent):
    def __init__(self, model, index, mule):
        super().__init__(model)
        self.index, self.mule = index, mule
        self.device = f"DEV-{index % 40:02d}" if not mule else "DEV-RING"

    def step(self):
        m = self.model
        if self.random.random() < 0.05:
            target = self.random.randrange(len(m.accounts))
            m.transfers.append((self.index, target, round(self.random.uniform(5, 200), 2), False))
        if self.mule and m.shocked:
            target = m.random.choice(m.ring)
            if target != self.index:
                m.transfers.append((self.index, target, round(self.random.uniform(800, 4000), 2), True))


class FraudRing(Base):
    def __init__(self, seed, n, shock_at, severity, mitigated_at):
        super().__init__(seed, shock_at, severity, mitigated_at)
        count = min(n, 500)
        ring_size = max(6, int(count * 0.03 * (1 + severity)))
        self.ring = list(range(ring_size))
        self.accounts = [Account(self, i, i < ring_size) for i in range(count)]
        self.transfers = []

    def step(self):
        before = len(self.transfers)
        self.agents.shuffle_do("step")
        new = self.transfers[before:]
        self.last = dict(total=len(new), suspicious=sum(1 for t in new if t[3]), volume=round(sum(t[2] for t in new if t[3]), 2))
        if self.shocked and self.t == self.shock_at:
            self.log("Coordinated transfers begin between newly linked accounts")
        self.t += 1

    def observe(self):
        return dict(t=self.t, transfers=self.last["total"], suspicious=self.last["suspicious"], suspicious_volume=self.last["volume"])

    def graph(self):
        edges = {}
        for a, b, amount, flagged in self.transfers[-1500:]:
            if flagged or amount > 150:
                key = (f"ACC-{a:04d}", f"ACC-{b:04d}")
                edges[key] = edges.get(key, 0) + amount
        return [dict(source=a, target=b, amount=round(v, 2)) for (a, b), v in list(edges.items())[:160]]


CLASSES = dict(pandemic=Pandemic, drones=Fleet, traffic=Junctions, market=Market, fraud=FraudRing)


def snapshot(model, kind):
    """Agent positions and states for map/WebGL views (bounded to 1,500 points)."""
    import math

    if kind == "pandemic":
        n = len(model.people)
        pts = []
        for i, p in enumerate(model.people[:1500]):
            r = random.Random(i)
            angle = 2 * math.pi * i / n
            radius = 40 + r.uniform(-8, 8)
            pts.append(dict(x=round(50 + radius * math.cos(angle), 2), y=round(50 + radius * math.sin(angle), 2), state=p.state))
        return pts
    if kind == "drones":
        return [dict(x=round(d.x, 2), y=round(d.y, 2), state=d.state, battery=round(d.battery, 1)) for d in model.drones]
    if kind == "fraud":
        n = len(model.accounts)
        return [
            dict(id=f"ACC-{a.index:04d}", x=round(50 + 42 * math.cos(2 * math.pi * a.index / n), 2), y=round(50 + 42 * math.sin(2 * math.pi * a.index / n), 2), state="mule" if a.mule else "account")
            for a in model.accounts[:1500]
        ]
    return []


def run(kind, seed, agents, steps, shock_at, severity, mitigated_at=None):
    """Run a population model and return its time series, events and relationship edges."""
    model = CLASSES[kind](seed, agents, shock_at, severity, mitigated_at)
    series = []
    for _ in range(steps):
        model.step()
        series.append(model.observe())
    return dict(
        kind=kind,
        engine=ENGINE,
        description=MODELS[kind],
        agents=len(model.agents),
        series=series,
        events=model.events[:80],
        edges=model.graph() if kind == "fraud" else [],
        snapshot=snapshot(model, kind),
    )


def for_run(spec, seed, population, tick, decisions):
    """Population view for a world run; mitigation starts when the root cause is repaired."""
    kind = spec.get("population") or ASSIGNMENT.get(spec["key"])
    if not kind:
        return None
    root = spec["incident"]["node"]
    repairs = {a["id"] for a in spec["actions"] if a["target"] == root and a["effect"] == "repair"}
    mitigated = next((d["tick"] + 2 for d in decisions if d["action_id"] in repairs), None)
    return run(kind, seed, max(120, min(population * 2, 1500)), max(1, int(tick)), spec["incident"]["tick"], spec["incident"]["severity"], mitigated)
