

# QRoute-AI: Quantum-Inspired Traffic Optimizer


**Smart India Hackathon | Problem Statement 26137**

A full-stack, quantum-inspired metaheuristic routing engine designed to solve dynamic, large-scale Vehicle Routing Problems (VRP). QRoute-AI leverages Quantum Particle Swarm Optimization (QPSO) to avoid local minima and dynamically calculate near-optimal fleet paths across real-world city grids.

## System Architecture & Stack
* **Backend Math Engine:** FastAPI, Python, NumPy, NetworkX
* **Frontend Dashboard:** React, Vite, React-Leaflet
* **Containerization:** Docker, Docker Compose, Nginx
* **Benchmarking Suite:** Integrated validation against classical exact solvers.
* **Data Ingestion:** Public OpenStreetMap datasets for spatial graph modeling.

## Local Deployment Guide
1. Clone this repository and navigate into the root directory.
2. Verify Docker Desktop is active on your host machine.
3. Execute `docker-compose up --build -d` to build the microservices.
4. Access the interactive map at `http://localhost:3000` and the API documentation at `http://localhost:8000/docs`.

> **Scaling Roadmap:** This MVP currently utilizes NetworkX for rapid in-memory spatial graph partitioning. The production architecture will migrate to **PostgreSQL + PostGIS** for persistent, city-scale geometric routing.