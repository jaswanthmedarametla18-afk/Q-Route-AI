"""
QRoute-AI Backend
==================
FastAPI service that:
  1. Generates a mock city road network (NetworkX graph) with randomized
     distance + live-traffic-congestion edge weights.
  2. Optimizes a start->end route using a simplified Quantum Particle Swarm
     Optimization (QPSO) algorithm operating directly over the graph
     (NOT Dijkstra / A* / any classical shortest-path routine).
  3. Exposes REST endpoints for a React/Leaflet frontend to consume.

Run with:  uvicorn main:app --reload --port 8000
"""

import math
import os
import random
from typing import List, Optional, Tuple

import networkx as nx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field



app = FastAPI(title="QRoute-AI", description="Quantum-Inspired Traffic Route Optimizer")

_cors_env = os.getenv("CORS_ORIGINS", "*")
_allow_origins = ["*"] if _cors_env.strip() == "*" else [o.strip() for o in _cors_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


NUM_NODES = 26                
CITY_CENTER = (12.9716, 77.5946)  
SPREAD_DEG = 0.045              

_graph: Optional[nx.Graph] = None  

def _random_coord(center: Tuple[float, float], spread: float) -> Tuple[float, float]:
    lat = center[0] + random.uniform(-spread, spread)
    lon = center[1] + random.uniform(-spread, spread)
    return round(lat, 6), round(lon, 6)


def _haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance between two (lat, lon) points, in kilometers."""
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def generate_city_graph(seed: Optional[int] = 42) -> nx.Graph:
    """
    Builds a mock city road network:
      - Nodes = intersections, each with a lat/lon coordinate.
      - Edges = road segments connecting geographically nearby intersections
        (so the graph resembles a real, navigable street grid instead of
        random long-range shortcuts).
      - Each edge carries:
          distance_km   -> static road length
          congestion    -> live traffic factor in [0.05, 1.0], 1.0 = gridlock
          weight        -> effective travel cost = distance * (1 + congestion)
    """
    if seed is not None:
        random.seed(seed)

    G = nx.Graph()
    coords = {}
    for node_id in range(NUM_NODES):
        coords[node_id] = _random_coord(CITY_CENTER, SPREAD_DEG)
        G.add_node(node_id, lat=coords[node_id][0], lon=coords[node_id][1])

    K_NEAREST = 3
    for node_id in range(NUM_NODES):
        dists = sorted(
            ((other, _haversine_km(coords[node_id], coords[other]))
             for other in range(NUM_NODES) if other != node_id),
            key=lambda t: t[1],
        )
        for other, dist_km in dists[:K_NEAREST]:
            if G.has_edge(node_id, other):
                continue
            congestion = round(random.uniform(0.05, 1.0), 2)  
            weight = round(dist_km * (1 + congestion), 4)
            G.add_edge(node_id, other, distance_km=round(dist_km, 3),
                       congestion=congestion, weight=weight)

   
    if not nx.is_connected(G):
        components = list(nx.connected_components(G))
        for i in range(len(components) - 1):
            a = next(iter(components[i]))
            b = next(iter(components[i + 1]))
            dist_km = _haversine_km(coords[a], coords[b])
            congestion = round(random.uniform(0.05, 1.0), 2)
            weight = round(dist_km * (1 + congestion), 4)
            G.add_edge(a, b, distance_km=round(dist_km, 3), congestion=congestion, weight=weight)

    return G


def get_graph() -> nx.Graph:
    global _graph
    if _graph is None:
        _graph = generate_city_graph()
    return _graph




class QPSORouteOptimizer:
    def __init__(
        self,
        graph: nx.Graph,
        start: int,
        end: int,
        swarm_size: int = 24,
        iterations: int = 60,
        max_path_steps: int = 40,
    ):
        self.graph = graph
        self.start = start
        self.end = end
        self.swarm_size = swarm_size
        self.iterations = iterations
        self.max_path_steps = max_path_steps
        self.n_nodes = graph.number_of_nodes()
        self.node_list = list(graph.nodes())
        self.node_index = {node: i for i, node in enumerate(self.node_list)}

        self._edge_weight = {}
        for u, v, data in graph.edges(data=True):
            self._edge_weight[(u, v)] = data["weight"]
            self._edge_weight[(v, u)] = data["weight"]

        weights = list(self._edge_weight.values())
        self._max_weight = max(weights) if weights else 1.0



    def _decode_path(self, attractiveness: List[float], stochastic: bool = True):
        """
        Walks the graph from start to end using a softmax-weighted choice
        over each neighbour's (attractiveness - normalized edge cost) score.
        `stochastic=False` makes the walk greedy/deterministic (used once at
        the very end to render the final chosen route).
        Returns (path_node_list, total_cost) or (None, inf) if it fails to
        reach `end` within max_path_steps or gets stuck at a dead end.
        """
        current = self.start
        path = [current]
        visited = {current}
        total_cost = 0.0

        for _ in range(self.max_path_steps):
            if current == self.end:
                return path, total_cost

            neighbours = [nb for nb in self.graph.neighbors(current) if nb not in visited]
            if not neighbours:
                return None, math.inf  # dead end -> invalid candidate

            scores = []
            for nb in neighbours:
                edge_cost = self._edge_weight[(current, nb)] / self._max_weight  
                attract = attractiveness[self.node_index[nb]]
                
                score = attract - 0.9 * edge_cost
                scores.append(score)

            if stochastic:
                
                exp_scores = [math.exp(3.0 * s) for s in scores]
                total = sum(exp_scores)
                probs = [e / total for e in exp_scores]
                chosen = random.choices(neighbours, weights=probs, k=1)[0]
            else:
                chosen = neighbours[scores.index(max(scores))]

            total_cost += self._edge_weight[(current, chosen)]
            path.append(chosen)
            visited.add(chosen)
            current = chosen

        return None, math.inf  

    def _fitness(self, attractiveness: List[float], trials: int = 3):
        """Best-of-`trials` stochastic decodes (paths are sampled, so a
        single decode is noisy). Returns (best_cost, best_path) so the
        swarm can remember the *actual path* behind its best score, not
        just the vector that produced it -- re-decoding a vector later
        (even greedily) is not guaranteed to reproduce the same path."""
        best_cost = math.inf
        best_path = None
        for _ in range(trials):
            path, cost = self._decode_path(attractiveness, stochastic=True)
            if cost < best_cost:
                best_cost, best_path = cost, path
        return best_cost, best_path



    def optimize(self):
        N = self.n_nodes

        
        positions = [[random.random() for _ in range(N)] for _ in range(self.swarm_size)]
        pbest = [list(p) for p in positions]
        pbest_eval = [self._fitness(p) for p in positions]          
        pbest_fitness = [c for c, _ in pbest_eval]

        gbest_idx = min(range(self.swarm_size), key=lambda i: pbest_fitness[i])
        gbest = list(pbest[gbest_idx])
        gbest_fitness = pbest_fitness[gbest_idx]
        gbest_path = pbest_eval[gbest_idx][1]  
                                                

        convergence_history = [gbest_fitness]

        for it in range(self.iterations):
            beta = 1.0 - 0.6 * (it / max(1, self.iterations - 1))

            mbest = [sum(pbest[p][d] for p in range(self.swarm_size)) / self.swarm_size
                     for d in range(N)]

            for i in range(self.swarm_size):
                new_pos = [0.0] * N
                for d in range(N):
                    phi = random.random()
                    p = phi * pbest[i][d] + (1 - phi) * gbest[d]

                    u = random.uniform(1e-6, 1.0)  
                    direction = 1 if random.random() > 0.5 else -1

                    
                    new_val = p + direction * beta * abs(mbest[d] - positions[i][d]) * math.log(1.0 / u)
                    new_pos[d] = min(1.0, max(0.0, new_val))  

                positions[i] = new_pos
                fitness, path = self._fitness(new_pos)

                if fitness < pbest_fitness[i]:
                    pbest[i] = new_pos
                    pbest_fitness[i] = fitness
                    if fitness < gbest_fitness:
                        gbest = list(new_pos)
                        gbest_fitness = fitness
                        gbest_path = path

            convergence_history.append(gbest_fitness)

        greedy_path, greedy_cost = self._decode_path(gbest, stochastic=False)
        if greedy_path is not None and greedy_cost < gbest_fitness:
            gbest_path, gbest_fitness = greedy_path, greedy_cost

        return {
            "path": gbest_path,
            "total_cost": gbest_fitness,
            "gbest_fitness_trace": convergence_history,
            "iterations": self.iterations,
            "swarm_size": self.swarm_size,
        }



class RouteRequest(BaseModel):
    start: int = Field(..., description="Start node id")
    end: int = Field(..., description="End node id")
    swarm_size: int = Field(24, ge=4, le=100)
    iterations: int = Field(60, ge=5, le=300)


class RouteResponse(BaseModel):
    path: List[int]
    coordinates: List[Tuple[float, float]]
    total_cost: float
    total_distance_km: float
    avg_congestion: float
    iterations: int
    swarm_size: int
    algorithm: str = "Quantum Particle Swarm Optimization (QPSO)"



@app.get("/")
def root():
    return {"service": "QRoute-AI", "status": "online"}


@app.get("/network")
def get_network():
    """Returns the full mock city graph (nodes + edges) for map rendering."""
    G = get_graph()
    nodes = [{"id": n, "lat": d["lat"], "lon": d["lon"]} for n, d in G.nodes(data=True)]
    edges = [
        {
            "source": u,
            "target": v,
            "distance_km": d["distance_km"],
            "congestion": d["congestion"],
            "weight": d["weight"],
        }
        for u, v, d in G.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}


@app.post("/regenerate-network")
def regenerate_network(seed: Optional[int] = None):
    """Regenerates the mock city graph (new random layout / traffic)."""
    global _graph
    _graph = generate_city_graph(seed=seed if seed is not None else random.randint(0, 999999))
    return {"message": "network regenerated", "num_nodes": _graph.number_of_nodes(),
            "num_edges": _graph.number_of_edges()}


@app.post("/optimize-route", response_model=RouteResponse)
def optimize_route(req: RouteRequest):
    G = get_graph()

    if req.start not in G.nodes or req.end not in G.nodes:
        raise HTTPException(status_code=400, detail="start/end must be valid node ids (see /network)")
    if req.start == req.end:
        raise HTTPException(status_code=400, detail="start and end must differ")

    optimizer = QPSORouteOptimizer(
        graph=G,
        start=req.start,
        end=req.end,
        swarm_size=req.swarm_size,
        iterations=req.iterations,
    )
    result = optimizer.optimize()

    if result["path"] is None:
        raise HTTPException(status_code=500, detail="QPSO failed to converge on a valid path, try again")

    path = result["path"]
    coordinates = [(G.nodes[n]["lat"], G.nodes[n]["lon"]) for n in path]

    total_distance = sum(G.edges[path[i], path[i + 1]]["distance_km"] for i in range(len(path) - 1))
    avg_congestion = sum(G.edges[path[i], path[i + 1]]["congestion"] for i in range(len(path) - 1)) / (len(path) - 1)

    return RouteResponse(
        path=path,
        coordinates=coordinates,
        total_cost=round(result["total_cost"], 4),
        total_distance_km=round(total_distance, 3),
        avg_congestion=round(avg_congestion, 3),
        iterations=result["iterations"],
        swarm_size=result["swarm_size"],
    )


if __name__ == "__main__":
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
