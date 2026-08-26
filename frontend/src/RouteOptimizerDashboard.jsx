import React, { useEffect, useMemo, useState, useCallback } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Polyline,
  Tooltip,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "./dashboard.css";

const API_BASE = "http://localhost:8000";

function FitToNodes({ nodes }) {
  const map = useMap();
  useEffect(() => {
    if (!nodes || nodes.length === 0) return;
    const bounds = nodes.map((n) => [n.lat, n.lon]);
    map.fitBounds(bounds, { padding: [40, 40] });
  }, [nodes, map]);
  return null;
}

function congestionColor(congestion) {
  const hue = 120 - Math.min(1, Math.max(0, congestion)) * 120; 
  return `hsl(${hue}, 75%, 45%)`;
}

export default function RouteOptimizerDashboard() {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [startNode, setStartNode] = useState(null);
  const [endNode, setEndNode] = useState(null);
  const [route, setRoute] = useState(null); 
  const [loadingNetwork, setLoadingNetwork] = useState(true);
  const [optimizing, setOptimizing] = useState(false);
  const [error, setError] = useState(null);
  const [swarmSize, setSwarmSize] = useState(24);
  const [iterations, setIterations] = useState(60);

  const loadNetwork = useCallback(async () => {
    setLoadingNetwork(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/network`);
      if (!res.ok) throw new Error(`Network fetch failed (${res.status})`);
      const data = await res.json();
      setNodes(data.nodes);
      setEdges(data.edges);
      if (data.nodes.length >= 2) {
        setStartNode(data.nodes[0].id);
        setEndNode(data.nodes[data.nodes.length - 1].id);
      }
      setRoute(null);
    } catch (err) {
      setError(err.message || "Failed to load network");
    } finally {
      setLoadingNetwork(false);
    }
  }, []);

  useEffect(() => {
    loadNetwork();
  }, [loadNetwork]);

  const regenerateNetwork = async () => {
    setError(null);
    try {
      await fetch(`${API_BASE}/regenerate-network`, { method: "POST" });
      await loadNetwork();
    } catch (err) {
      setError(err.message || "Failed to regenerate network");
    }
  };

  const optimizeRoute = async () => {
    if (startNode === null || endNode === null || startNode === endNode) {
      setError("Pick two different intersections for start and end.");
      return;
    }
    setOptimizing(true);
    setError(null);
    setRoute(null);
    try {
      const res = await fetch(`${API_BASE}/optimize-route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start: startNode,
          end: endNode,
          swarm_size: swarmSize,
          iterations: iterations,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `Optimization failed (${res.status})`);
      }
      const data = await res.json();
      setRoute(data);
    } catch (err) {
      setError(err.message || "Failed to optimize route");
    } finally {
      setOptimizing(false);
    }
  };

  const routeNodeSet = useMemo(
    () => new Set(route ? route.path : []),
    [route]
  );

  const mapCenter = nodes.length > 0 ? [nodes[0].lat, nodes[0].lon] : [12.9716, 77.5946];

  return (
    <div className="qroute-shell">
      <header className="qroute-header">
        <div className="qroute-title">
          <span className="qroute-badge">QRoute&nbsp;AI</span>
          <h1>Quantum-Inspired Traffic Route Optimizer</h1>
        </div>
        <p className="qroute-subtitle">
          A Quantum Particle Swarm Optimization (QPSO) swarm searches a live mock
          city graph for a low-cost path — not a shortest-path lookup.
        </p>
      </header>

      <div className="qroute-body">
        <aside className="qroute-panel">
          <section className="panel-block">
            <h2>Route Controls</h2>

            <label className="field-label" htmlFor="start-select">Start intersection</label>
            <select
              id="start-select"
              value={startNode ?? ""}
              onChange={(e) => setStartNode(Number(e.target.value))}
              disabled={loadingNetwork}
            >
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  Node {n.id}
                </option>
              ))}
            </select>

            <label className="field-label" htmlFor="end-select">End intersection</label>
            <select
              id="end-select"
              value={endNode ?? ""}
              onChange={(e) => setEndNode(Number(e.target.value))}
              disabled={loadingNetwork}
            >
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  Node {n.id}
                </option>
              ))}
            </select>

            <div className="field-row">
              <div>
                <label className="field-label" htmlFor="swarm-size">Swarm size</label>
                <input
                  id="swarm-size"
                  type="number"
                  min={4}
                  max={100}
                  value={swarmSize}
                  onChange={(e) => setSwarmSize(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="field-label" htmlFor="iterations">Iterations</label>
                <input
                  id="iterations"
                  type="number"
                  min={5}
                  max={300}
                  value={iterations}
                  onChange={(e) => setIterations(Number(e.target.value))}
                />
              </div>
            </div>

            <button
              className="btn-primary"
              onClick={optimizeRoute}
              disabled={optimizing || loadingNetwork}
            >
              {optimizing ? "Running QPSO swarm..." : "Optimize Route"}
            </button>

            <button
              className="btn-secondary"
              onClick={regenerateNetwork}
              disabled={loadingNetwork || optimizing}
            >
              Regenerate City Network
            </button>

            {error && <p className="qroute-error">{error}</p>}
          </section>

          {route && (
            <section className="panel-block">
              <h2>Optimized Route</h2>
              <ul className="stat-list">
                <li><span>Total cost</span><strong>{route.total_cost}</strong></li>
                <li><span>Distance</span><strong>{route.total_distance_km} km</strong></li>
                <li><span>Avg. congestion</span><strong>{(route.avg_congestion * 100).toFixed(0)}%</strong></li>
                <li><span>Swarm size</span><strong>{route.swarm_size}</strong></li>
                <li><span>Iterations</span><strong>{route.iterations}</strong></li>
              </ul>
              <p className="route-path">
                Path: {route.path.join(" → ")}
              </p>
            </section>
          )}
        </aside>

        <main className="qroute-map-wrap">
          {loadingNetwork ? (
            <div className="qroute-loading">Loading city network...</div>
          ) : (
            <MapContainer center={mapCenter} zoom={14} className="qroute-map">
              <TileLayer
                attribution='&copy; OpenStreetMap contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <FitToNodes nodes={nodes} />

              {/* Base road network, colored by live congestion */}
              {edges.map((e, idx) => {
                const a = nodes.find((n) => n.id === e.source);
                const b = nodes.find((n) => n.id === e.target);
                if (!a || !b) return null;
                return (
                  <Polyline
                    key={`edge-${idx}`}
                    positions={[[a.lat, a.lon], [b.lat, b.lon]]}
                    pathOptions={{ color: congestionColor(e.congestion), weight: 2, opacity: 0.5 }}
                  />
                );
              })}

              {/* Highlighted QPSO-optimized route */}
              {route && (
                <Polyline
                  positions={route.coordinates}
                  pathOptions={{ color: "#7c3aed", weight: 6, opacity: 0.9 }}
                />
              )}

              {/* Intersections */}
              {nodes.map((n) => {
                const isRouteNode = routeNodeSet.has(n.id);
                const isEndpoint = n.id === startNode || n.id === endNode;
                return (
                  <CircleMarker
                    key={n.id}
                    center={[n.lat, n.lon]}
                    radius={isEndpoint ? 9 : isRouteNode ? 7 : 5}
                    pathOptions={{
                      color: isEndpoint ? "#f59e0b" : isRouteNode ? "#7c3aed" : "#334155",
                      fillColor: isEndpoint ? "#f59e0b" : isRouteNode ? "#a78bfa" : "#94a3b8",
                      fillOpacity: 0.9,
                      weight: 2,
                    }}
                  >
                    <Tooltip direction="top" offset={[0, -6]}>
                      Node {n.id}
                      {n.id === startNode ? " (start)" : ""}
                      {n.id === endNode ? " (end)" : ""}
                    </Tooltip>
                  </CircleMarker>
                );
              })}
            </MapContainer>
          )}
        </main>
      </div>
    </div>
  );
}
