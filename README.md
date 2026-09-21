# FarmBuy AI: Farm-to-Buyer Supply Intelligence Platform

> **Core Philosophy:**  
> The platform doesn't just ask: *"Who wants to buy tomatoes?"*  
> It asks: *"Where will demand occur, how much will be needed, which farmers can supply it, at what price, and what is the most efficient way to move it there?"*

---

## 🏆 Key Differentiation Statement

### vs e-NAM:
> *"e-NAM primarily provides an electronic agricultural market and price discovery across physical integrated mandis. Our prototype focuses on predictive local supply-demand coordination: a buyer can specify a future requirement, the system aggregates supply from multiple nearby farmers, identifies supply gaps, forecasts upcoming demand, and then optimizes the collection route."*

### vs AgriBazaar:
> *"AgriBazaar already provides digital trading, negotiation and logistics, so we are not claiming those as our innovation. Our focus is the intelligence layer before fulfilment—forecasting future demand, identifying supply shortages, selecting the best combination of farmers to satisfy a requirement, and optimizing the resulting collection route."*

---

## 🔄 The 7-Stage End-to-End Pipeline

```
Buyer Demand ➔ Predict Future Demand ➔ Find & Aggregate Farmer Supply ➔ Identify Shortage ➔ Negotiate Price ➔ Optimize Collection Route ➔ Deliver
```

1. **Buyer Demand Specification**: Target commodity, required volume, destination depot.
2. **AI Predictive Demand Forecasting (ML)**: Scikit-Learn regression trained on regional mandi history with day-of-week seasonality to predict 7–14 days ahead.
3. **Multi-Farmer Supply Aggregation**: Intelligently bundles multiple smallholders to fulfill bulk orders using customizable strategies (`balanced`, `lowest_cost`, `nearest`).
4. **Supply Gap & Shortage Detection**: Instantly identifies local volume deficits to alert buyers.
5. **Price Intelligence & Negotiation**: Compares Government Mandi benchmarks with asking prices and provides AI counter-offer recommendations.
6. **Logistics & Multi-Stop Route Optimization (TSP)**: Nearest-Neighbor + 2-Opt local refinement to calculate optimal collection loop with coordinates for interactive Leaflet maps.
7. **Digital Procurement Contract & Fulfillment**: Generates binding digital purchase order manifest with status tracking from farm-gate to delivery.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+ (with virtual environment in `2_Backend/venv`)
- Modern web browser (Chrome, Edge, Firefox)

### 2. Seeding Database
To initialize the SQLite database with 5 commodities, 10 local farmers, and 60 days of historical demand data:
```powershell
cd 2_Backend
.\venv\Scripts\python.exe -m app.seed
```

### 3. Launching the Application
Run the backend server (FastAPI serves both the REST API and the Frontend dashboard):
```powershell
cd 2_Backend
.\venv\Scripts\python.exe run.py
```

- **Web Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Interactive OpenAPI Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🛠️ Architecture

- **Frontend**: HTML5, Modern CSS Grid & Flexbox, JavaScript (ES6+), Leaflet.js (OpenStreetMap), Chart.js
- **Backend**: FastAPI, Pydantic v2, SQLAlchemy ORM, Uvicorn
- **AI / ML Engine**: Scikit-Learn (Linear Regression, seasonal variance), NumPy
- **Logistics Engine**: TSP Nearest-Neighbor with 2-Opt refinement, Haversine road matrix
- **Database**: SQLite / PostgreSQL compatible schema
