# Istanbul Neural-Guided A* Route Planner

A multi-stop route optimization system for Istanbul's road network using a **neural network-guided, hierarchical, bidirectional A\*** algorithm. Users pin any waypoints on the map; the system finds the optimal route connecting them in the shortest travel time, incorporating real-time traffic data, and visualizes it on an interactive map.

---

## Table of Contents

- [Project Goal](#project-goal)
- [System Architecture](#system-architecture)
- [Modules & How They Work](#modules--how-they-work)
  - [1. Map Data: MapLoader](#1-map-data-maploader)
  - [2. Graph Processing: GraphProcessor](#2-graph-processing-graphprocessor)
  - [3. Route Engine: AStarEngine](#3-route-engine-astarengine)
  - [4. Neural Network Training: training/](#4-neural-network-training-training)
  - [5. Neural Heuristic: NeuralHeuristic](#5-neural-heuristic-neuralheuristic)
  - [6. Multi-Stop Routing: RingPlanner](#6-multi-stop-routing-ringplanner)
  - [7. Traffic Management: TrafficManager](#7-traffic-management-trafficmanager)
  - [8. Web Interface: app.py + Flask](#8-web-interface-apppy--flask)
  - [9. Visualization: MapRenderer](#9-visualization-maprenderer)
- [End-to-End Data Flow](#end-to-end-data-flow)
- [Algorithm Details](#algorithm-details)
  - [Bidirectional A*](#bidirectional-a)
  - [Hierarchical Graph Layering](#hierarchical-graph-layering)
  - [Neural Heuristic](#neural-heuristic)
  - [TSP Solution: Nearest Neighbor + 2-opt](#tsp-solution-nearest-neighbor--2-opt)
  - [Traffic Simulation](#traffic-simulation)
- [Feature Engineering](#feature-engineering)
- [Model Architecture: HeuristicNet](#model-architecture-heuristicnet)
- [Caching Strategy](#caching-strategy)
- [Setup & Running](#setup--running)
- [Command-Line Usage](#command-line-usage)
- [API Endpoints](#api-endpoints)
- [Project Directory Structure](#project-directory-structure)
- [Landmark Coordinates](#landmark-coordinates)

---

## Project Goal

To solve the scalability problem that classical navigation software faces in large, transcontinental, topologically complex cities like Istanbul. This project:

- Improves classical A\* with three distinct techniques (bidirectionality + hierarchy + neural heuristic) for a **10–50× speed-up**.
- Finds the **optimal visit order** among N user-selected waypoints using TSP-based algorithms.
- Produces traffic-aware routes by reflecting real-time or simulated **traffic congestion** into edge costs.
- Exposes all of this through a user-friendly **web interface** with a single click.

---

## System Architecture

```
OpenStreetMap (Overpass API)
         │
         ▼
   core/map_loader.py          ← Raw map data fetching
         │
         ▼
 core/graph_processor.py       ← Hierarchical layering + Haversine cache
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 Express    Arterial            ← Two separate search layers
  Graph      Graph
    │         │
    └────┬────┘
         │
         ▼
  core/astar_engine.py         ← Bidirectional Hierarchical A*
    ▲         ▲
    │         │
  Haversine  NeuralHeuristic   ← Pluggable heuristic function
  (fallback) (ONNX inference)
         │
         ▼
  core/ring_planner.py         ← TSP: Nearest Neighbor + 2-opt
         │
         ▼
  core/traffic_manager.py      ← Edge cost multipliers (traffic)
         │
         ▼
   app.py (Flask)              ← REST API server
         │
         ▼
  templates/index.html         ← Leaflet.js interactive map UI
```

---

## Modules & How They Work

### 1. Map Data: MapLoader

**File:** `core/map_loader.py`

**Purpose:** Fetches Istanbul's main road network from OpenStreetMap and prepares it for the pipeline.

**Steps:**

1. **Graph Fetching:** Queries the Overpass API via the OSMnx library. Only high-hierarchy roads are retrieved: `motorway`, `motorway_link`, `trunk`, `trunk_link`, `primary`, `primary_link`, `secondary`, `secondary_link`. Lower-hierarchy roads (residential, unclassified, tertiary) are intentionally excluded — this reduces data size and narrows the A\* search space.

2. **Graph Enrichment:** Additional attributes are added to the raw graph:
   - `speed_kph`: OSMnx's `add_edge_speeds()` estimates missing speed limits from road type.
   - `travel_time`: Edge traversal time in seconds computed as `length / speed_ms`. A\* uses this as the cost metric.
   - `highway_rank`: Road priority score (motorway=5 … secondary=1). Used in neural network feature engineering and layer selection.

3. **Saving:** The graph is written to disk as `.graphml` at `data/raw/istanbul_main_arteries.graphml`. On subsequent runs, the API is never re-queried; the graph is loaded directly with `load_from_disk()`.

**Why `.graphml`?** An XML-based format that fully preserves all node/edge attributes in NetworkX. Also compatible with tools like QGIS and Gephi.

---

### 2. Graph Processing: GraphProcessor

**File:** `core/graph_processor.py`

**Purpose:** Optimizes the raw graph for A\*: splits it into hierarchical layers and builds a Haversine cache.

**SCC Cleaning:** For graphs with more than 100 nodes, the largest Strongly Connected Component (SCC) is identified first. Dead-ends, one-way dead ends, and small disconnected fragments are removed. This makes the graph consistent and ensures every node is reachable from every other node.

**Hierarchical Layering (`build_hierarchy()`):**

The graph is split into two separate layers:

| Layer | Road Types | Usage |
|---|---|---|
| **Express** | motorway, motorway_link, trunk, trunk_link | Searches ≥ 5 km apart |
| **Arterial** | primary, primary_link, secondary, secondary_link | Searches < 5 km apart |
| **Full** | Express + Arterial combined | Fallback and visualization |

A **reversed graph** is also produced for each layer. Bidirectional A\* uses this reversed graph when searching backward from the target; the reversal cost at runtime is zero.

Because Istanbul is transcontinental, all connected components with more than 100 nodes are preserved when building layers (not just the largest). Without this, the European and Asian sides of the city could become disconnected.

**Haversine Cache (`build_heuristic_cache()`):**

The `HeuristicCache` object holds two things:
- `node_coords`: A `{osmid: (lat, lon)}` dictionary for all nodes — O(1) coordinate lookup.
- `distance_cache`: A `{(u, v): metres}` dictionary of previously computed Haversine distances — no recomputation.

`get_heuristic(cache, u, v)` is called on every step of A\*'s inner loop. If cached, it returns in O(1); otherwise it computes Haversine and stores the result. The cache is persisted to disk in `pickle` format so the server never recomputes from scratch on restart.

---

### 3. Route Engine: AStarEngine

**File:** `core/astar_engine.py`

**Purpose:** Finds the shortest route between two OSM nodes using Bidirectional Hierarchical A\*.

**Layer Selection (`_select_layer()`):**

As soon as `find_path()` is called, the straight-line distance between source and target is computed:
- **< 5 km:** Search on the Arterial layer. Smaller search space.
- **≥ 5 km:** Search on the Express layer. Motorway/trunk network only.
- **Fallback:** If no node is found in the chosen layer or no route can be built, the Full graph is used.

**Bidirectional A\* Core (`_bidirectional_astar()`):**

Two separate search states (`_SearchState`) are maintained:
- **Forward:** From source toward target.
- **Backward:** From target toward source (on the reversed graph).

At each step, the `f_score` at the top of both min-heaps is compared; a node is expanded in the direction with the smaller value. This ensures both directions advance in balance.

**Meeting Point & Stopping Condition (Pohl, 1971):**
- When a node is expanded, the algorithm checks whether that node exists in the opposite direction's `g_score` dictionary.
- If it does, it is a meeting candidate: `μ = g_fwd[m] + g_bwd[m]` is computed.
- **Stop:** When `f_fwd_top + f_bwd_top >= μ`, the search halts with a provably optimal result.

**Lazy Deletion:**

Python's `heapq` does not support `decrease-key`. Instead, an updated node is re-pushed onto the heap. The stale copy is immediately discarded via the closed-set check. This trades a small amount of extra memory for an O(log n) push guarantee on every step.

**Edge Cost (`_get_edge_cost()`):**

In a MultiDiGraph, multiple parallel edges may exist between the same two nodes (different lanes, bridges). The one with the lowest cost is always selected. If traffic mode is active, the result is multiplied by `TrafficManager.get_edge_multiplier()`. If `travel_time` is missing, `length / 13.888` (50 km/h fallback) is used.

**Heuristic Function (`_default_heuristic()`):**

The default heuristic converts Haversine distance to seconds by dividing by `22.22 m/s` (80 km/h). This is admissible — it never overestimates actual travel time (straight-line distance / motorway speed is a lower bound on real travel time). When a `heuristic_fn` is injected from outside, the ONNX neural network replaces this function.

---

### 4. Neural Network Training: training/

The modules in this folder form the training pipeline for the neural network that learns the A\* heuristic function.

#### dataset_builder.py — Training Data Generation

Labeled data is produced by running real A\*:
- Random (source, target) pairs are selected on the graph.
- For each pair, the **true cost** (in seconds) is computed with A\*.
- An 8-dimensional feature vector is extracted using `FeatureExtractor.extract()`.
- The (feature vector, true cost) pair becomes a training example.

Sampling is done across distance bands (0–1 km, 1–5 km, 5–15 km, 15+ km), so the model learns each distance range in a balanced way.

#### model_arch.py — Model Definition

The `HeuristicNet` and `FeatureExtractor` classes are defined here (details in the [Model Architecture](#model-architecture-heuristicnet) section).

#### trainer.py — Training Loop

- **Optimizer:** AdamW (`lr=1e-3`, `weight_decay=1e-4`) — Adam with decoupled weight decay.
- **Loss Function:** Huber Loss (SmoothL1, `β=1.0`) — more robust to outliers than MSE; ideal for the wide range of travel times (10s–7200s).
- **LR Scheduling:** `CosineAnnealingLR` — avoids sharp minima compared to a fixed LR; LR approaches 0 by the end of training.
- **Early Stopping:** Training halts if validation loss does not improve for `patience=10` epochs.
- **Gradient Clipping:** `max_norm=1.0` — prevents exploding gradients.
- **Normalization:** Labels are compressed with `log1p(seconds)` (10s → 2.4, 3600s → 8.2). Reversed with `expm1` at inference.
- **Training Device:** Automatically selected in priority order: Apple Silicon MPS > CUDA > CPU.
- **Best model** is saved after every epoch as `models/checkpoints/best_heuristic_net.pt`.

#### export_onnx.py — ONNX Export & Benchmark

The trained PyTorch model is exported to ONNX format:
- **Standard model:** `models/onnx/heuristic_net.onnx`
- **INT8 quantized model:** `models/onnx/heuristic_net_int8.onnx` (faster, minor accuracy loss)

A 5,000-run benchmark compares PyTorch and ONNX Runtime latency. ONNX Runtime delivers ~10–15× lower inference overhead than PyTorch on CPU.

---

### 5. Neural Heuristic: NeuralHeuristic

**File:** `core/neural_heuristic.py`

**Purpose:** The heuristic function interface that connects the trained ONNX model to the A\* engine.

**Initialization:**

When the class is instantiated, it first looks for the quantized (`int8`) model; if not found, it falls back to the standard model. An ONNX Runtime `InferenceSession` is started on CPU.

**`__call__(u, v)` — Single Prediction:**

A\* calls `h(neighbor, target)` on every step. This function:
1. Looks up the `(u, v)` pair in a Python `dict` cache → returns in O(1) if found.
2. Otherwise, extracts an 8-dimensional feature vector with `FeatureExtractor.extract(u, v)`.
3. Passes the vector to ONNX Runtime → receives a `float32` prediction.
4. Converts from log scale to seconds with `expm1(pred)`.
5. Guarantees admissibility with `max(0.0, ...)` (negative cost is impossible).
6. Writes the result to cache.

**`predict_batch(pairs)` — Batch Prediction:**

When `RingPlanner` computes the cost matrix, it processes N×N pairs in a single ONNX call. Vectorized feature extraction is done with `FeatureExtractor.extract_batch()`, leveraging ONNX Runtime's parallel processing capability.

---

### 6. Multi-Stop Routing: RingPlanner

**File:** `core/ring_planner.py`

**Purpose:** Finds the **optimal visit order** among N user-selected waypoints and produces a closed (ring) or open route.

**Problem:** This is a Travelling Salesman Problem (TSP) instance. Since the exact solution is NP-hard, a two-phase approach is applied:

**Phase 1 — Cost Matrix:**

An N×N asymmetric cost matrix is built. For each `(i, j)` pair, the estimated cost is computed with `NeuralHeuristic.predict_batch()`. All N×(N−1) pairs are processed in a single ONNX batch call.

**Phase 2 — Nearest Neighbor Heuristic:**

Produces a greedy initial ordering: starting from the origin, at each step go to the nearest unvisited point. O(N²) complexity. Produces a starting point that is ~20–25% from optimal, but fast.

**Phase 3 — 2-opt Local Search:**

Iteratively improves the Nearest Neighbor output. All `(i, k)` edge-pair combinations are tried; if reversing the `order[i+1..k]` segment reduces cost, it is accepted. Repeats until no improvement is found or `max_2opt_iter` (default 100) is reached. Typically converges within ~5% of optimal.

**Open TSP (Fixed Start & End):** For open-route requests with a fixed start and end coming from the web UI, brute-force (exact optimal) is used for ≤ 6 intermediate stops; Nearest Neighbor + 2-opt is used for more (`app.py/solve_open_tsp()`).

**Phase 4 — A\* Segment Computation:**

`AStarEngine.find_path()` is called for each consecutive waypoint pair in the optimized order. This produces the **real road route**, not an estimated cost.

**Phase 5 — Segment Merging:**

Duplicate nodes at segment boundaries are dropped, and all segments are merged into a single continuous route list.

---

### 7. Traffic Management: TrafficManager

**File:** `core/traffic_manager.py`

**Purpose:** Produces a `travel_time` multiplier for each edge. A\* applies this multiplier to edge costs; congested roads become more expensive, and the algorithm prefers alternative routes.

**Three-Layer Traffic Model:**

**1. Hourly Simulation (`_simulate_base_traffic()`):**

An Istanbul-specific traffic profile is applied based on the current hour:
- **Morning peak (07:30–09:30):** Max multiplier 3.5 (peak at 08:30).
- **Evening peak (17:30–20:00):** Max multiplier 4.2 (peak at 18:30).
- **Midday congestion (12:00–14:00):** Fixed 1.6 multiplier.
- **Off-peak / night:** 1.0–1.3 multiplier.

Sensitivity by road type: motorways are 90% sensitive to traffic fluctuation, primary roads 70%, secondary 50%, local roads 20%.

**Bosphorus Bridges & Tunnels:** Cross-continental transitions (< 29.01° ↔ > 29.01° longitude) are detected. Multipliers reach 4.8–5.2 in the Asia→Europe direction during mornings and Europe→Asia during evenings. Backward congestion propagation: neighbors approaching the affected edge are impacted at 60%.

**2. Random Incident Simulation (`_generate_simulated_incidents()`):**

On each update, 2–4 random edges from motorway/trunk/primary roads are selected:
- **Accident:** 5.5–8.5 multiplier — A\* almost entirely avoids this road.
- **Roadwork:** 4.0–6.0 multiplier.

Old incidents are cleared and new ones generated with 30% probability.

**3. TomTom Traffic Flow API (Optional):**

If an API key is set via `configs/settings.yaml` or the `TOMTOM_API_KEY` environment variable, live mode is activated. Five critical Istanbul points are queried (15 Temmuz Bridge, FSM Bridge, Mecidiyeköy, Kadıköy E-5, Haliç Bridge). The `freeFlowSpeed / currentSpeed` ratio is computed as the multiplier and applied to motorway/primary edges within a 500-metre radius.

---

### 8. Web Interface: app.py + Flask

**File:** `app.py`

**Purpose:** A REST API server and web interface that ties all components together.

**On Server Startup:**

A one-time initialization happens when the server starts:
1. `MapLoader` → Graph is loaded from disk.
2. `GraphProcessor` → Hierarchy and Haversine cache are built.
3. `TrafficManager` → Traffic multipliers are computed for the first time.
4. Two separate planners are prepared:
   - **Neural:** `NeuralHeuristic` + `AStarEngine` + `RingPlanner`
   - **Haversine:** Fallback `NeuralHeuristic` (Haversine-based) + `AStarEngine` + `RingPlanner`

**API Endpoints:**

| Endpoint | Method | Description |
|---|---|---|
| `GET /` | GET | Interactive Leaflet.js map |
| `GET /api/landmarks` | GET | List of 10 predefined Istanbul points |
| `GET /api/traffic` | GET | Current traffic segments and incident data |
| `POST /api/route` | POST | Route computation (waypoint list + options) |

The `POST /api/route` request accepts the following parameters:
- `waypoints`: `[{lat, lng, name}]` list (minimum 2 points)
- `use_haversine`: if `true`, uses Haversine heuristic instead of Neural
- `is_loop`: if `true`, closed ring route; if `false`, open route
- `start_index` / `end_index`: start/end index for open routes
- `use_traffic`: if `true`, traffic multipliers are applied to edge costs

---

### 9. Visualization: MapRenderer

**File:** `visualization/map_renderer.py`

**Purpose:** Converts the computed ring route into an interactive HTML map using Folium.

Supports waypoint markers, route segments, and an optional traffic heat map layer. In CLI mode, the output is saved as `output/istanbul_ring.html`.

---

## End-to-End Data Flow

```
1. User pins points on the map
        │
        ▼
2. POST /api/route → [{lat, lng, name}, ...]
        │
        ▼
3. Each coordinate is mapped to the nearest OSM node
   ox.distance.nearest_nodes(full_graph, X=lon, Y=lat)
        │
        ▼
4. RingPlanner.plan(waypoint_nodes)
   ├── NeuralHeuristic.predict_batch(N×N pairs) → cost matrix
   ├── Nearest Neighbor → initial ordering
   └── 2-opt iterations → optimized ordering
        │
        ▼
5. AStarEngine.find_path(src, tgt) × N segments
   ├── Layer selection (express/arterial based on distance)
   ├── Bidirectional A* (NeuralHeuristic heuristic)
   │   ├── Forward heap: source → target
   │   └── Backward heap: target → source (reversed graph)
   ├── Pohl stopping condition → meeting node
   └── _reconstruct_path() → OSM node list
        │
        ▼
6. Segment coordinates returned in JSON
        │
        ▼
7. Leaflet.js draws polyline on the map
```

---

## Algorithm Details

### Bidirectional A\*

Classical A\* expands O(b^d) nodes (b: average branching factor, d: depth). The bidirectional version expands O(b^(d/2)) in each direction; total O(2·b^(d/2)) ≈ quadratic improvement.

On Istanbul's graph (approximately 8,000 nodes), this translates to a 10–50× speed difference.

Heap entries are `(f_score, counter, node_id)` triples. `counter` provides deterministic FIFO ordering for nodes with equal f_score.

### Hierarchical Graph Layering

The 5 km threshold is the natural boundary between intra-city short-distance searches (arterial) and transcontinental long-distance searches (express). The Express layer offers on average ~60% smaller search space.

### Neural Heuristic

The neural network, which replaces the classical Haversine heuristic, preserves the same admissibility guarantee while additionally learning:
- The road hierarchy position (highway_rank) of source and target nodes
- Junction density (degree information)
- Bearing — especially meaningful for east-west routes like Bosphorus crossings
- Istanbul-specific topology, since it is trained on real A\* costs

This allows A\* to expand more accurate nodes first and reduces the total number of nodes explored.

### TSP Solution: Nearest Neighbor + 2-opt

| Option | Usage | Complexity | Quality |
|---|---|---|---|
| Brute-force | ≤ 6 intermediate stops | O(n!) | Exact optimal |
| Nearest Neighbor | > 6 intermediate stops | O(n²) | ~20–25% from optimal |
| 2-opt improvement | Always applied | O(n²·iter) | Within ~5% of optimal |

### Traffic Simulation

Traffic multipliers are multiplied by `travel_time`. Multiplier 1.0 = free flow, 5.0 = heavy congestion, 8.5 = accident/blockage. A\* incorporates these costs directly; congested roads are avoided in favor of alternative routes.

---

## Feature Engineering

`FeatureExtractor` produces an 8-dimensional vector for each (source, target) node pair:

| Index | Feature | Normalization | Description |
|---|---|---|---|
| [0] | Haversine distance | ÷ 80,000 m | Istanbul diameter ~80 km |
| [1] | Δlat | ÷ 2.0 | Latitude difference |
| [2] | Δlon | ÷ 2.0 | Longitude difference |
| [3] | Source node degree | ÷ 8 | Junction density |
| [4] | Target node degree | ÷ 8 | Junction density |
| [5] | Source avg highway_rank | ÷ 5.0 | Road hierarchy score |
| [6] | Target avg highway_rank | ÷ 5.0 | Road hierarchy score |
| [7] | Bearing angle (radians) | ÷ π | Directional info [-1, 1] |

Coordinates, degrees, and highway_ranks are cached on initialization; the graph is not traversed on every extraction.

---

## Model Architecture: HeuristicNet

```
Input(8)
   │
   ▼
InputProjection: Linear(8→128) + LayerNorm + GELU
   │
   ▼
ResidualBlock × 3:
   ┌─────────────────────────┐
   │ Linear(128→128)         │
   │ LayerNorm               │
   │ GELU                    │
   │ Dropout(0.1)            │
   │ Linear(128→128)         │
   │ LayerNorm               │
   └─────────────────────────┘
   x → x + F(x) → GELU   (skip connection)
   │
   ▼
OutputHead: Linear(128→64) + GELU + Linear(64→1) + Softplus
   │
   ▼
Output: estimated cost (log1p-normalized seconds)
```

**Design Decisions:**
- **MLP (Multilayer Perceptron):** Unlike a GNN alternative, requires no extra dependencies for ONNX export and delivers ~0.1 ms inference latency inside A\*'s inner loop (roughly 50× faster than a GNN).
- **ResidualBlock:** Skip connections stabilize gradient flow. LayerNorm eliminates the statistics issues BatchNorm suffers from with small batches. GELU is preferred over ReLU for its smooth transition in the negative region.
- **Softplus output activation:** `log(1 + e^x)` — always positive output guarantee. Cost cannot be negative; avoids the zero-gradient region of ReLU.
- **Xavier initialization:** More stable initial weights than Kaiming for GELU activations.
- **Total parameters:** ~100K (lightweight, optimized for fast inference).

---

## Caching Strategy

The system uses three-layer caching:

| Layer | Class | Purpose | Persistence |
|---|---|---|---|
| **Coordinate cache** | `HeuristicCache.node_coords` | O(1) coordinate access for Haversine | Pickle (disk) |
| **Haversine cache** | `HeuristicCache.distance_cache` | No recomputation for the same node pair | Pickle (disk) |
| **Neural prediction cache** | `NeuralHeuristic._pred_cache` | No repeated ONNX calls for the same (u,v) | In-memory (volatile) |

Cache hit rate (`hit_rate`) can be monitored with `NeuralHeuristic.get_stats()`.

---

## Setup & Running

### Automated Setup (Recommended)

The easiest way to get started. No manual environment setup needed.

#### macOS
```bash
# Double-click Launch_macOS.command in Finder
# OR from terminal:
bash Launch_macOS.command
```

#### Linux
```bash
bash Launch_Linux.sh
```

#### Windows
```
Double-click Launch_Windows.bat
```

**What happens automatically:**
1. Checks if Python 3.10+ is installed on the system
2. Creates a `.venv` virtual environment if it doesn't exist
3. Checks every required library — installs missing ones via `pip`
4. Downloads model weights from GitHub Releases (~2 MB)
5. Fetches Istanbul map data from OpenStreetMap (~5–15 min, first run only)
6. Starts the Flask server and opens the browser

> **Note:** On the very first run, the automated setup may take **5–20 minutes** depending on your internet connection. Subsequent launches are instant — already-installed libraries and downloaded data are detected and skipped.

---

#### Manual Setup (Alternative)

If you prefer full control over the environment:

```bash
# 1. Clone the repository
git clone https://github.com/MrOzbir/istanbul-route-optimizer.git
cd istanbul-route-optimizer

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download data and model files
python setup_data.py

# 5. Start the server
python app.py
```

---

#### setup_env.py — Standalone Environment Script

You can also run the environment setup script independently:

```bash
python setup_env.py              # Full setup (venv + libraries + data download)
python setup_env.py --skip-data  # Only install libraries, skip map/model download
```

`setup_env.py` does the following:
- **Python check:** Verifies Python >= 3.10
- **Virtual env:** Creates `.venv` if it doesn't exist
- **Library audit:** Tests each package with `import` — only installs what's missing
- **Data setup:** Optionally calls `setup_data.py` to download map and model files

> **Note:** `setup_data.py` also contains an early dependency check. If it detects missing libraries, it will print a clear error message and direct you to run `setup_env.py` first.

> **Note:** `setup_data.py` requires an internet connection on the first run.
> On subsequent runs, existing files are detected and skipped automatically.

### Requirements

```
Python >= 3.10
```

### Dependencies

```
# Map & Graph
osmnx>=1.9.0
networkx>=3.3
shapely>=2.0
geopandas>=0.14
rtree>=1.2

# AI
torch>=2.3          # Apple Silicon MPS support
onnxruntime>=1.18
onnx>=1.16

# Web Server
flask
flask-cors

# Visualization
folium>=0.17

# Development
pytest>=8.0
pyyaml>=6.0
```

### Step-by-Step Installation

```bash
# 1. Clone the repository
git clone https://github.com/MrOzbir/istanbul-route-optimizer.git
cd istanbul-route-optimizer

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install osmnx networkx shapely geopandas rtree \
            torch onnxruntime onnx \
            flask flask-cors folium pyyaml pytest

# 4. Automatically set up data and model files
#    → Model weights are downloaded from GitHub Releases  (~2 MB)
#    → Map data is generated from OpenStreetMap            (~5–15 min)
python setup_data.py

# 5. Start the web server
python app.py
```

> **Note:** `setup_data.py` requires an internet connection on the first run.
> On subsequent runs, existing files are detected and skipped automatically.

#### Optional: Train the Model from Scratch

If you want to train your own model instead of using the pre-trained weights:

```bash
# Download only map data (skip model download)
python setup_data.py --skip-model

# Train the model (~10–30 minutes)
python main.py --mode train --epochs 100 --samples 800

# Export model to ONNX
python main.py --mode export --quantize

# Start the application
python app.py
```

### TomTom Live Traffic (Optional)

```bash
# Set as an environment variable
export TOMTOM_API_KEY="your_api_key_here"
python app.py
```

Or add to `configs/settings.yaml`:
```yaml
tomtom_api_key: "your_api_key_here"
```

---

## Command-Line Usage

```bash
# Fetch map data from OSMnx
python main.py --mode fetch

# Train the model (custom parameters)
python main.py --mode train --epochs 80 --samples 600

# ONNX export + INT8 quantization + benchmark
python main.py --mode export --quantize

# Compute a route and render to an HTML map
python main.py --mode route --waypoints "Taksim,Kadıköy,Beşiktaş,Üsküdar"

# Route with classical Haversine (no neural heuristic)
python main.py --mode route --haversine --waypoints "Taksim,Sarıyer"

# Start the web interface on a custom port
python main.py --mode server --port 8080

# Run all steps in sequence
python main.py --mode all
```

---

## API Endpoints

### GET /api/landmarks

Returns 10 predefined Istanbul points.

```json
{
  "success": true,
  "landmarks": [
    {"name": "Taksim", "lat": 41.0369, "lng": 28.9784},
    ...
  ]
}
```

### GET /api/traffic

Returns the current traffic state.

```json
{
  "success": true,
  "segments": [
    {
      "u": 12345, "v": 67890,
      "highway": "motorway",
      "multiplier": 3.2,
      "status": "heavy",
      "color": "#dc2626",
      "coords": [[41.05, 29.01], ...]
    }
  ],
  "incidents": [
    {"id": 1, "lat": 41.04, "lng": 28.98, "type": "accident", "name": "Traffic Accident 💥", "multiplier": 7.2}
  ]
}
```

### POST /api/route

```json
// Request
{
  "waypoints": [
    {"lat": 41.0369, "lng": 28.9784, "name": "Taksim"},
    {"lat": 40.9906, "lng": 29.0264, "name": "Kadıköy"}
  ],
  "use_haversine": false,
  "is_loop": true,
  "use_traffic": true
}

// Response
{
  "success": true,
  "total_length_km": 18.4,
  "total_time_min": 32.0,
  "elapsed_ms": 245.3,
  "waypoints_ordered": [...],
  "segments": [
    {
      "segment_index": 0,
      "found": true,
      "path_coords": [[41.03, 28.97], ...],
      "total_length_m": 9200.0,
      "total_time_s": 960.0,
      "nodes_explored": 412,
      "elapsed_ms": 120.1
    }
  ],
  "optimization_log": ["Nearest Neighbor initial cost: 1842.3", "2-opt done. 4 iterations | final: 1788.1"]
}
```

---

## Project Directory Structure

```
istanbul-route-optimizer/
│
├── main.py                     # CLI entry point
├── app.py                      # Flask web server
├── setup_data.py               # Automated data & model setup
├── setup_env.py                # Automated environment & library setup
├── requirements.txt            # Python dependencies
├── Launch_macOS.command        # macOS double-click launcher (auto-setup)
├── Launch_Linux.sh             # Linux launcher (auto-setup)
├── Launch_Windows.bat          # Windows launcher (auto-setup)
│
├── core/
│   ├── map_loader.py           # OSMnx map data fetcher
│   ├── graph_processor.py      # Hierarchical layering + cache
│   ├── astar_engine.py         # Bidirectional Hierarchical A*
│   ├── neural_heuristic.py     # ONNX heuristic integration
│   ├── ring_planner.py         # TSP: Nearest Neighbor + 2-opt
│   └── traffic_manager.py      # Traffic simulation + TomTom API
│
├── training/
│   ├── model_arch.py           # HeuristicNet + FeatureExtractor
│   ├── dataset_builder.py      # Labeled data generation via A*
│   ├── trainer.py              # PyTorch training loop
│   └── export_onnx.py          # ONNX export + benchmark
│
├── visualization/
│   └── map_renderer.py         # Folium HTML map renderer
│
├── templates/
│   └── index.html              # Leaflet.js interactive UI
│
├── static/
│   ├── css/                    # UI styles
│   └── js/                     # UI JavaScript logic
│
├── tests/
│   ├── test_astar_engine.py
│   ├── test_map_loader.py
│   ├── test_neural_heuristic.py
│   └── test_traffic_manager.py
│
├── configs/
│   └── settings.yaml           # API keys and settings
│
├── data/
│   ├── raw/                    # istanbul_main_arteries.graphml
│   └── processed/              # Layer graphs + Haversine cache
│
├── models/
│   ├── checkpoints/            # best_heuristic_net.pt
│   └── onnx/                   # heuristic_net.onnx + int8
│
├── scripts/
│   └── create_release.sh       # GitHub Releases upload script
│
├── logs/                       # run.log
├── notebooks/                  # Exploratory notebooks
├── .gitignore
└── README.md
```

---

## Landmark Coordinates

| Name | Latitude | Longitude |
|---|---|---|
| Taksim | 41.0369 | 28.9784 |
| Kadıköy | 40.9906 | 29.0264 |
| Beşiktaş | 41.0430 | 29.0058 |
| Üsküdar | 41.0267 | 29.0184 |
| Fatih | 41.0193 | 28.9397 |
| Bakırköy | 40.9819 | 28.8772 |
| Şişli | 41.0602 | 28.9877 |
| Ataşehir | 40.9923 | 29.1244 |
| Sarıyer | 41.1657 | 29.0518 |
| Bağcılar | 41.0390 | 28.8560 |
