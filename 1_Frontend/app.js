// AgriConnect AI - Frontend Application Core

const API_BASE = window.location.origin.includes(":8000") 
    ? window.location.origin 
    : "http://127.0.0.1:8000";

let state = {
    products: [],
    currentMatching: null,
    currentForecast: null,
    currentPriceInsight: null,
    currentRoute: null,
    miniMap: null,
    fullMap: null,
    miniMapLayers: [],
    fullMapLayers: [],
    forecastChart: null
};

// Buyer Hub coordinates resolution (Kolkata Wholesale Hub or Howrah Cold Chain)
function getBuyerHub() {
    const locSelect = document.getElementById("buyerLocationSelect");
    const val = locSelect ? locSelect.value : "kolkata";
    if (val === "howrah") {
        return {
            name: "Howrah Cold Chain Depot",
            lat: 22.5892,
            lon: 88.3103
        };
    }
    return {
        name: "Kolkata Central Wholesale Hub",
        lat: 22.5726,
        lon: 88.3639
    };
}

let BUYER_HUB = getBuyerHub();

// Initialize on DOM Ready
document.addEventListener("DOMContentLoaded", async () => {
    await checkBackendStatus();
    await loadProducts();
    initMaps();
    // Run initial analysis with default parameters
    runCompleteAnalysis();
    // Preload order history for Orders & Tracking tab
    loadOrderHistory();
});

// 1. Health Check
async function checkBackendStatus() {
    const statusText = document.getElementById("statusText");
    const statusPulse = document.querySelector(".status-pulse");
    try {
        const res = await fetch(`${API_BASE}/health`);
        const data = await res.json();
        if (data.status === "healthy") {
            statusText.textContent = `Backend Connected (v${data.version || "2.0"})`;
            statusPulse.style.background = "#22c55e";
        }
    } catch (err) {
        console.warn("Backend not yet reachable on 8000:", err);
        statusText.textContent = "Backend Offline";
        statusPulse.style.background = "#ef4444";
    }
}

// 2. Load Products dynamically
async function loadProducts() {
    try {
        const res = await fetch(`${API_BASE}/api/products`);
        const products = await res.json();
        state.products = products;
        const select = document.getElementById("productSelect");
        if (products.length > 0) {
            select.innerHTML = products.map(p => 
                `<option value="${p.id}">${p.name} (Mandi: ₹${p.mandi_benchmark_price}/kg)</option>`
            ).join("");
        }
    } catch (err) {
        console.error("Error loading products:", err);
    }
}

// 3. Tab Navigation
function switchTab(tabId) {
    document.querySelectorAll(".nav-tab").forEach(tab => tab.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach(pane => pane.classList.remove("active"));

    const clickedBtn = Array.from(document.querySelectorAll(".nav-tab")).find(b => 
        b.getAttribute("onclick")?.includes(tabId)
    );
    if (clickedBtn) clickedBtn.classList.add("active");

    const targetPane = document.getElementById(`tab-${tabId}`);
    if (targetPane) {
        targetPane.classList.add("active");
    }

    // Refresh Leaflet maps when switching to map or dashboard tabs
    setTimeout(() => {
        if (state.miniMap) state.miniMap.invalidateSize();
        if (state.fullMap) state.fullMap.invalidateSize();
    }, 150);

    if (tabId === "contracts") {
        loadOrderHistory();
    }
}

// 4. Initialize Leaflet Maps
function initMaps() {
    if (typeof L === "undefined") {
        console.warn("Leaflet library not loaded");
        return;
    }

    // Mini Map
    const miniContainer = document.getElementById("miniMap");
    if (miniContainer && !state.miniMap) {
        state.miniMap = L.map('miniMap').setView([BUYER_HUB.lat, BUYER_HUB.lon], 9);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 18
        }).addTo(state.miniMap);
    }

    // Full Map
    const fullContainer = document.getElementById("fullMap");
    if (fullContainer && !state.fullMap) {
        state.fullMap = L.map('fullMap').setView([BUYER_HUB.lat, BUYER_HUB.lon], 9);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 18
        }).addTo(state.fullMap);
    }
}

// Custom Leaflet Icons
function createCustomIcon(isDepot, label) {
    const bg = isDepot ? "#2563eb" : "#16a34a";
    const symbol = isDepot ? "🏢" : "🌾";
    return L.divIcon({
        className: 'custom-map-marker',
        html: `<div style="background:${bg}; color:white; width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:16px; border:2px solid white; box-shadow:0 3px 8px rgba(0,0,0,0.3); cursor:pointer;">${symbol}</div>`,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
        popupAnchor: [0, -20]
    });
}

let demandParamsTimeout = null;
function onDemandParamsChange() {
    clearTimeout(demandParamsTimeout);
    demandParamsTimeout = setTimeout(() => {
        BUYER_HUB = getBuyerHub();
        runCompleteAnalysis();
    }, 250);
}

function onProductChange() {
    clearTimeout(demandParamsTimeout);
    demandParamsTimeout = setTimeout(() => {
        BUYER_HUB = getBuyerHub();
        runCompleteAnalysis();
    }, 200);
}

// 5. Run Complete Supply Intelligence Cycle
async function runCompleteAnalysis() {
    if (state.isAnalyzing) return;

    BUYER_HUB = getBuyerHub();

    const analyzeBtn = document.getElementById("analyzeBtn");
    const productId = parseInt(document.getElementById("productSelect").value, 10);
    const quantity = parseFloat(document.getElementById("quantityInput").value);
    const strategy = document.getElementById("strategySelect").value;

    if (!quantity || quantity <= 0) {
        alert("Please enter a valid procurement quantity in kg (must be greater than 0).");
        return;
    }

    state.isAnalyzing = true;
    if (analyzeBtn) {
        analyzeBtn.disabled = true;
        analyzeBtn.classList.add("loading");
        analyzeBtn.innerHTML = `<span>⏳ Analyzing Supply...</span>`;
    }

    try {
        // Run core intelligence API calls in parallel
        const [matchingRes, forecastRes, priceRes] = await Promise.all([
            fetch(`${API_BASE}/api/matching/analyze`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    product_id: productId,
                    required_quantity: quantity,
                    buyer_lat: BUYER_HUB.lat,
                    buyer_lon: BUYER_HUB.lon,
                    strategy: strategy
                })
            }),
            fetch(`${API_BASE}/api/demand/forecast`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    product_id: productId,
                    days_ahead: 7,
                    region: "Kolkata Metro Hub"
                })
            }),
            fetch(`${API_BASE}/api/pricing/insight?product_id=${productId}&required_quantity=${quantity}`)
        ]);

        if (!matchingRes.ok) {
            const errData = await matchingRes.json().catch(() => ({}));
            throw new Error(errData.detail || `Matching error (HTTP ${matchingRes.status})`);
        }
        if (!forecastRes.ok) {
            const errData = await forecastRes.json().catch(() => ({}));
            throw new Error(errData.detail || `Forecast error (HTTP ${forecastRes.status})`);
        }
        if (!priceRes.ok) {
            const errData = await priceRes.json().catch(() => ({}));
            throw new Error(errData.detail || `Price intelligence error (HTTP ${priceRes.status})`);
        }

        const matching = await matchingRes.json();
        const forecast = await forecastRes.json();
        const priceInsight = await priceRes.json();

        state.currentMatching = matching;
        state.currentForecast = forecast;
        state.currentPriceInsight = priceInsight;

        // Fetch Route Optimization for matched farmers
        let routeData = null;
        if (matching.farmers && matching.farmers.length > 0) {
            const farmerIds = matching.farmers.map(f => f.farmer_id);
            const farmerQuantities = {};
            matching.farmers.forEach(f => {
                farmerQuantities[f.farmer_id] = f.matched_quantity;
            });

            try {
                const routeRes = await fetch(`${API_BASE}/api/logistics/optimize-route`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        farmer_ids: farmerIds,
                        farmer_quantities: farmerQuantities,
                        product_id: productId,
                        buyer_name: BUYER_HUB.name,
                        buyer_lat: BUYER_HUB.lat,
                        buyer_lon: BUYER_HUB.lon
                    })
                });
                if (routeRes.ok) {
                    routeData = await routeRes.json();
                    state.currentRoute = routeData;
                } else {
                    console.warn("Route optimization endpoint returned:", routeRes.status);
                }
            } catch (routeErr) {
                console.warn("Route optimization request error:", routeErr);
            }
        }

        // Update UI components safely
        updateKPIs(matching, priceInsight, routeData);
        renderFarmerMatchTable(matching);
        renderForecastChart(forecast);
        renderPriceIntelligence(priceInsight);
        if (routeData) {
            renderRouteAndMaps(routeData, matching);
        } else {
            clearRouteAndMaps();
        }

        // Enable or disable contract creation
        const contractBtn = document.getElementById("generateContractBtn");
        if (contractBtn) {
            contractBtn.disabled = !matching.farmers || matching.farmers.length === 0 || matching.matched_quantity <= 0;
        }

    } catch (err) {
        console.error("Error during intelligence cycle execution:", err);
        alert(err.message || "Could not complete supply intelligence analysis. Please check input parameters.");
    } finally {
        state.isAnalyzing = false;
        if (analyzeBtn) {
            analyzeBtn.disabled = false;
            analyzeBtn.classList.remove("loading");
            analyzeBtn.innerHTML = `<span>⚡ Run Intelligence Cycle</span>`;
        }
    }
}

// 6. Update KPIs
function updateKPIs(matching, priceInsight, route) {
    document.getElementById("kpiMatched").textContent = `${matching.matched_quantity.toLocaleString()} kg`;
    document.getElementById("kpiFulfillmentPct").textContent = `${matching.fulfillment_percentage}% of ${matching.required_quantity.toLocaleString()} kg target`;

    const shortageEl = document.getElementById("kpiShortage");
    const shortageCard = document.getElementById("shortageCard");
    if (matching.shortage > 0) {
        shortageEl.textContent = `${matching.shortage.toLocaleString()} kg`;
        shortageEl.classList.add("text-danger");
        if (matching.matched_quantity === 0) {
            document.getElementById("kpiShortageSub").textContent = "⚠️ 0 kg available (Depleted - Restock)";
        } else {
            document.getElementById("kpiShortageSub").textContent = "⚠️ Supply deficit detected";
        }
    } else {
        shortageEl.textContent = "0 kg (Fulfilled)";
        shortageEl.classList.remove("text-danger");
        document.getElementById("kpiShortageSub").textContent = "✅ 100% Demand satisfied";
    }

    document.getElementById("kpiPrice").textContent = `₹${matching.blended_price_per_kg.toFixed(2)} / kg`;
    document.getElementById("kpiMandiBenchmark").textContent = `Govt Mandi: ₹${priceInsight.mandi_benchmark_price.toFixed(2)}`;

    if (route) {
        document.getElementById("kpiDistance").textContent = `${route.total_distance_km} km`;
        document.getElementById("kpiDistanceSaved").textContent = `Saves ${route.distance_saved_km} km vs single trips`;

        document.getElementById("kpiCarbon").textContent = `${route.carbon_reduction_kg} kg CO2`;
        document.getElementById("kpiFuelSaved").textContent = `Est. fuel: ₹${route.estimated_fuel_cost_inr.toLocaleString()}`;
    } else {
        document.getElementById("kpiDistance").textContent = "—";
        document.getElementById("kpiDistanceSaved").textContent = "Multi-farm collection TSP";
        document.getElementById("kpiCarbon").textContent = "—";
        document.getElementById("kpiFuelSaved").textContent = "vs individual farmer trips";
    }
}

// 7. Render Matched Farmers Table
function renderFarmerMatchTable(matching) {
    const tbody = document.getElementById("farmerTableBody");
    const badge = document.getElementById("fulfillmentBadge");

    if (matching.status === "FULLY_MATCHED") {
        badge.className = "badge badge-success";
        badge.textContent = "✅ Fully Satisfied";
    } else if (matching.status === "PARTIAL_SHORTAGE") {
        badge.className = "badge badge-warning";
        badge.textContent = `⚠️ Partial (${matching.fulfillment_percentage}%)`;
    } else {
        badge.className = "badge badge-danger";
        badge.textContent = "🚨 Critical Shortage";
    }

    if (!matching.farmers || matching.farmers.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center py-4">
                    <div style="color:#dc2626; font-weight:700; font-size:15px; margin-bottom:6px;">
                        🚨 No Available Farmer Inventory for this Commodity
                    </div>
                    <p class="text-muted" style="font-size:13px; max-width:480px; margin:0 auto 12px; line-height:1.4;">
                        Local farmer stock for <strong>${matching.product_name || "this commodity"}</strong> has been depleted by recent order fulfillment or exceeds current network harvest.
                    </p>
                    <button class="btn-sm btn-success" style="padding:7px 16px; font-size:13px;" onclick="restockSupplies(${matching.product_id})">
                        🔄 Restock ${matching.product_name || "Produce"} (Fresh Harvest)
                    </button>
                </td>
            </tr>
        `;
        document.getElementById("summaryTotalCost").textContent = `₹0.00`;
        document.getElementById("summaryFarmerCount").textContent = `0 Local Farmers`;
        return;
    }

    tbody.innerHTML = matching.farmers.map(f => `
        <tr>
            <td>
                <strong>${f.farmer_name}</strong>
                <div class="text-muted" style="font-size:11.5px;">⭐ ${f.rating} • ${f.contact || "Verified"}</div>
            </td>
            <td>${f.location}</td>
            <td><span class="badge" style="background:#f1f5f9;">${f.quality_grade}</span></td>
            <td>
                <strong>${f.matched_quantity.toLocaleString()} kg</strong>
                <div class="text-muted" style="font-size:11px;">of ${f.available_quantity.toLocaleString()} kg avail</div>
            </td>
            <td>₹${f.expected_price.toFixed(2)} / kg</td>
            <td>${f.distance_km} km</td>
            <td><strong>₹${f.subtotal.toLocaleString()}</strong></td>
        </tr>
    `).join("");

    document.getElementById("summaryTotalCost").textContent = `₹${matching.total_estimated_cost.toLocaleString()}`;
    document.getElementById("summaryFarmerCount").textContent = `${matching.farmers.length} Local Farmers`;
}

// 8. Render ML Demand Forecast Chart (Chart.js)
function renderForecastChart(forecast) {
    const ctx = document.getElementById('forecastChart');
    if (!ctx || typeof Chart === "undefined") return;

    // Destroy existing chart if present
    if (state.forecastChart) {
        state.forecastChart.destroy();
    }

    const histLabels = forecast.historical_data.map(d => d.date.slice(5));
    const histValues = forecast.historical_data.map(d => d.quantity_demanded);

    const foreLabels = forecast.forecast.map(d => d.date.slice(5));
    const foreValues = forecast.forecast.map(d => d.predicted_demand_kg);
    const upperBounds = forecast.forecast.map(d => d.upper_bound_kg);
    const lowerBounds = forecast.forecast.map(d => d.lower_bound_kg);

    // Combine labels
    const allLabels = [...histLabels, ...foreLabels];
    
    // Align datasets
    const histDataExtended = [...histValues, ...Array(foreLabels.length).fill(null)];
    
    // Connect the prediction line smoothly from the last historical point
    const foreDataExtended = [
        ...Array(histLabels.length - 1).fill(null),
        histValues[histValues.length - 1],
        ...foreValues
    ];
    
    const upperExtended = [
        ...Array(histLabels.length - 1).fill(null),
        histValues[histValues.length - 1],
        ...upperBounds
    ];
    
    const lowerExtended = [
        ...Array(histLabels.length - 1).fill(null),
        histValues[histValues.length - 1],
        ...lowerBounds
    ];

    state.forecastChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: allLabels,
            datasets: [
                {
                    label: 'Historical Demand (kg/day)',
                    data: histDataExtended,
                    borderColor: '#64748b',
                    backgroundColor: 'rgba(100, 116, 139, 0.1)',
                    borderWidth: 2,
                    pointRadius: 3,
                    tension: 0.3
                },
                {
                    label: 'Predicted Demand (ML Linear Regression)',
                    data: foreDataExtended,
                    borderColor: '#16a34a',
                    backgroundColor: 'rgba(22, 163, 74, 0.1)',
                    borderWidth: 3,
                    pointRadius: 4,
                    pointBackgroundColor: '#16a34a',
                    borderDash: [5, 5],
                    tension: 0.3
                },
                {
                    label: 'Upper Confidence (95%)',
                    data: upperExtended,
                    borderColor: 'rgba(34, 197, 94, 0.3)',
                    borderDash: [2, 2],
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: '+1',
                    backgroundColor: 'rgba(34, 197, 94, 0.08)'
                },
                {
                    label: 'Lower Confidence (95%)',
                    data: lowerExtended,
                    borderColor: 'rgba(34, 197, 94, 0.3)',
                    borderDash: [2, 2],
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            if (context.raw !== null) {
                                return `${context.dataset.label}: ${context.raw.toLocaleString()} kg`;
                            }
                            return null;
                        }
                    }
                },
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 12,
                        font: { family: 'Inter', size: 12 }
                    }
                }
            },
            scales: {
                y: {
                    title: { display: true, text: 'Demand Volume (kg)' },
                    grid: { color: '#f1f5f9' }
                },
                x: {
                    grid: { color: '#f8fafc' }
                }
            }
        }
    });

    // Update Trend Badge and Insights
    const trendBadge = document.getElementById("trendBadge");
    trendBadge.textContent = forecast.trend_direction;
    if (forecast.growth_percentage > 5) {
        trendBadge.className = "badge badge-danger";
    } else if (forecast.growth_percentage < -5) {
        trendBadge.className = "badge badge-warning";
    } else {
        trendBadge.className = "badge badge-success";
    }

    const insightsList = document.getElementById("forecastInsightsList");
    insightsList.innerHTML = forecast.insights.map(item => `<li>${item}</li>`).join("");
}

// 9. Render Price Intelligence
function renderPriceIntelligence(price) {
    document.getElementById("priceMandiVal").textContent = `₹${price.mandi_benchmark_price.toFixed(2)} / kg`;
    document.getElementById("priceLowestVal").textContent = `₹${price.lowest_farmer_price.toFixed(2)} / kg`;
    document.getElementById("priceAverageVal").textContent = `₹${price.average_farmer_price.toFixed(2)} / kg`;
    document.getElementById("priceHighestVal").textContent = `₹${price.highest_farmer_price.toFixed(2)} / kg`;

    document.getElementById("bandMin").textContent = `₹${price.fair_market_band_min.toFixed(2)}`;
    document.getElementById("bandMax").textContent = `₹${price.fair_market_band_max.toFixed(2)}`;
    document.getElementById("priceAdvisoryBox").textContent = price.recommendation;

    // Default target price input to counter-offer baseline
    const targetInput = document.getElementById("targetPriceInput");
    if (!targetInput.value || parseFloat(targetInput.value) <= 0) {
        targetInput.value = (price.average_farmer_price * 0.96).toFixed(2);
    }
}

// 10. Simulate Negotiation
async function simulateNegotiationOffer() {
    const productId = parseInt(document.getElementById("productSelect").value, 10);
    const quantity = parseFloat(document.getElementById("quantityInput").value);
    const targetPrice = parseFloat(document.getElementById("targetPriceInput").value);

    if (!targetPrice || targetPrice <= 0) {
        alert("Please enter a valid target price.");
        return;
    }

    const farmerIds = state.currentMatching && state.currentMatching.farmers
        ? state.currentMatching.farmers.map(f => f.farmer_id)
        : [1, 2, 3];

    try {
        const res = await fetch(`${API_BASE}/api/pricing/negotiate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                product_id: productId,
                required_quantity: quantity,
                target_price: targetPrice,
                matched_farmer_ids: farmerIds
            })
        });

        const neg = await res.json();
        const resBox = document.getElementById("negotiationResult");
        resBox.style.display = "block";

        const likelihoodEl = document.getElementById("negLikelihood");
        likelihoodEl.textContent = `${neg.farmer_acceptance_likelihood} (${neg.acceptance_score}%)`;
        if (neg.farmer_acceptance_likelihood === "HIGH") {
            likelihoodEl.className = "badge badge-success";
        } else if (neg.farmer_acceptance_likelihood === "MODERATE") {
            likelihoodEl.className = "badge badge-warning";
        } else {
            likelihoodEl.className = "badge badge-danger";
        }

        document.getElementById("negCounterOffer").textContent = `₹${neg.recommended_counter_offer.toFixed(2)}/kg`;
        document.getElementById("negStrategyText").innerHTML = `
            <strong>Strategy:</strong> ${neg.ai_negotiation_strategy}
            <div class="mt-2 text-muted" style="font-size:12px;">
                Est. Procurement Savings: <strong>₹${neg.potential_savings_total.toLocaleString()}</strong>
            </div>
        `;

        const quotesEl = document.getElementById("farmerQuotesList");
        quotesEl.innerHTML = neg.farmer_responses.map(q => `
            <div class="quote-bubble">
                <span class="quote-farmer">${q.farmer_name}</span> (${q.location})
                <span class="quote-badge ${q.response.includes('ACCEPTED') ? 'badge-success' : (q.response.includes('COUNTER') ? 'badge-warning' : 'badge-danger')}">
                    ${q.response}
                </span>
                <div class="mt-1" style="color:#475569;">"${q.message}"</div>
            </div>
        `).join("");

    } catch (err) {
        console.error("Error evaluating negotiation:", err);
    }
}

// 11. Render Route on Leaflet Maps
function renderRouteAndMaps(route, matching) {
    if (!state.miniMap || !state.fullMap) return;

    // Clear previous layers
    state.miniMapLayers.forEach(layer => state.miniMap.removeLayer(layer));
    state.fullMapLayers.forEach(layer => state.fullMap.removeLayer(layer));
    state.miniMapLayers = [];
    state.fullMapLayers = [];

    const polyCoordinates = route.polyline_coordinates;

    // Add Buyer Hub Marker
    const depotMarkerMini = L.marker([BUYER_HUB.lat, BUYER_HUB.lon], {
        icon: createCustomIcon(true)
    }).bindPopup(`<strong>${BUYER_HUB.name}</strong><br>Central Procurement & Aggregation Depot`);
    depotMarkerMini.addTo(state.miniMap);
    state.miniMapLayers.push(depotMarkerMini);

    const depotMarkerFull = L.marker([BUYER_HUB.lat, BUYER_HUB.lon], {
        icon: createCustomIcon(true)
    }).bindPopup(`<strong>${BUYER_HUB.name}</strong><br>Central Procurement & Aggregation Depot`);
    depotMarkerFull.addTo(state.fullMap);
    state.fullMapLayers.push(depotMarkerFull);

    // Add Farmer Markers
    matching.farmers.forEach(farmer => {
        const popupText = `
            <strong>🌾 ${farmer.farmer_name}</strong><br>
            Location: ${farmer.location}<br>
            Allotted Qty: <strong>${farmer.matched_quantity.toLocaleString()} kg</strong> (${farmer.quality_grade})<br>
            Rate: ₹${farmer.expected_price}/kg<br>
            Contact: ${farmer.contact || "Available"}
        `;

        const fMarkerMini = L.marker([farmer.latitude, farmer.longitude], {
            icon: createCustomIcon(false)
        }).bindPopup(popupText);
        fMarkerMini.addTo(state.miniMap);
        state.miniMapLayers.push(fMarkerMini);

        const fMarkerFull = L.marker([farmer.latitude, farmer.longitude], {
            icon: createCustomIcon(false)
        }).bindPopup(popupText);
        fMarkerFull.addTo(state.fullMap);
        state.fullMapLayers.push(fMarkerFull);
    });

    // Draw Polyline
    const polylineMini = L.polyline(polyCoordinates, {
        color: '#16a34a',
        weight: 4,
        opacity: 0.85,
        dashArray: '6, 6'
    }).addTo(state.miniMap);
    state.miniMapLayers.push(polylineMini);

    const polylineFull = L.polyline(polyCoordinates, {
        color: '#16a34a',
        weight: 5,
        opacity: 0.9
    }).addTo(state.fullMap);
    state.fullMapLayers.push(polylineFull);

    // Zoom bounds to fit route
    const bounds = L.latLngBounds(polyCoordinates);
    state.miniMap.fitBounds(bounds, { padding: [30, 30] });
    state.fullMap.fitBounds(bounds, { padding: [40, 40] });

    // Update Quick Legs Preview
    const legsPreview = document.getElementById("routeLegsPreview");
    legsPreview.innerHTML = route.route_legs.map(leg => `
        <div class="leg-item">
            <span>${leg.from_name} ➔ ${leg.to_name}</span>
            <strong>${leg.distance_km} km (${leg.estimated_time_mins} min)</strong>
        </div>
    `).join("");

    // Update Full Map Logistics Panel
    document.getElementById("fullMapDistanceBadge").textContent = `${route.total_distance_km} km Total Circuit`;
    document.getElementById("logTotalDist").textContent = `${route.total_distance_km} km`;
    document.getElementById("logUnoptDist").textContent = `${route.unoptimized_single_trip_distance_km} km`;
    
    const pctSaved = Math.round((route.distance_saved_km / (route.unoptimized_single_trip_distance_km || 1)) * 100);
    document.getElementById("logDistSaved").textContent = `${route.distance_saved_km} km (${pctSaved}%)`;
    
    document.getElementById("logTransitHours").textContent = `${route.estimated_transit_hours} hrs`;
    document.getElementById("logFuelCost").textContent = `₹${route.estimated_fuel_cost_inr.toLocaleString()}`;
    document.getElementById("logCarbonSaved").textContent = `${route.carbon_reduction_kg} kg CO2`;

    // Render Waypoints Schedule
    const waypointsEl = document.getElementById("routeStepsContainer");
    waypointsEl.innerHTML = route.collection_waypoints.map(wp => `
        <div class="waypoint-row ${wp.type === 'DEPOT' ? 'depot' : ''}">
            <div class="stop-circle ${wp.type === 'DEPOT' ? 'depot-circle' : ''}">${wp.stop_number}</div>
            <div>
                <strong>${wp.name}</strong>
                <div class="text-muted" style="font-size:11.5px;">${wp.location}</div>
            </div>
            <div>${wp.type === 'DEPOT' ? 'Hub Depot' : `Pickup: ${wp.quantity_to_collect_kg.toLocaleString()} kg`}</div>
            <div>${wp.distance_from_prev_km} km leg</div>
            <div><strong>${wp.cumulative_distance_km} km total</strong></div>
        </div>
    `).join("");
}

// 12. Generate Digital Procurement Contract
async function generateProcurementContract() {
    if (!state.currentMatching || !state.currentMatching.farmers) {
        alert("Please run supply intelligence analysis first.");
        return;
    }

    const productId = parseInt(document.getElementById("productSelect").value, 10);
    const quantity = state.currentMatching.matched_quantity;
    const agreedPrice = state.currentMatching.blended_price_per_kg;

    const payload = {
        buyer_name: BUYER_HUB.name,
        product_id: productId,
        total_quantity: quantity,
        agreed_price_per_kg: agreedPrice,
        farmer_allocations: state.currentMatching.farmers,
        route_summary: state.currentRoute
    };

    try {
        const res = await fetch(`${API_BASE}/api/orders/fulfill`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const order = await res.json();
        renderOrderContract(order);
        switchTab('contracts');
        loadOrderHistory();
        // Update supply analysis in the background so current stock updates
        setTimeout(() => {
            runCompleteAnalysis();
        }, 500);
    } catch (err) {
        console.error("Error creating procurement contract:", err);
        alert("Could not generate procurement contract. Check backend connection.");
    }
}

// 13. Render Order Contract
function renderOrderContract(order) {
    const area = document.getElementById("orderConfirmationArea");
    area.innerHTML = `
        <div class="order-contract-box">
            <div class="contract-header">
                <div>
                    <span class="badge badge-success">DIGITAL CONTRACT VERIFIED</span>
                    <h2 class="mt-2" style="font-family: var(--font-head); font-size:22px;">Order #${order.order_number}</h2>
                    <p class="text-muted">Generated on ${order.created_at} UTC • AgriConnect Automated Clearing Engine</p>
                </div>
                <div style="text-align:right;">
                    <span class="text-muted" style="font-size:12px;">Total Contract Value</span>
                    <div style="font-size:24px; font-weight:800; color:#15803d;">₹${order.grand_total.toLocaleString()}</div>
                    <span class="badge" style="background:#ecfdf5; color:#065f46;">Includes ₹${order.logistics_cost.toLocaleString()} Freight</span>
                </div>
            </div>

            <div class="pricing-metrics-grid mt-3">
                <div class="price-stat-box">
                    <span class="label">Buyer Entity</span>
                    <span class="val" style="font-size:16px;">${order.buyer_name}</span>
                </div>
                <div class="price-stat-box">
                    <span class="label">Commodity & Volume</span>
                    <span class="val green" style="font-size:16px;">${order.total_quantity.toLocaleString()} kg ${order.product_name}</span>
                </div>
                <div class="price-stat-box">
                    <span class="label">Blended Price</span>
                    <span class="val" style="font-size:16px;">₹${order.agreed_price_per_kg.toFixed(2)} / kg</span>
                </div>
                <div class="price-stat-box">
                    <span class="label">Participating Smallholders</span>
                    <span class="val" style="font-size:16px;">${order.farmers_involved} Local Farmers</span>
                </div>
            </div>

            <h4 class="mt-4 mb-3">Live Multi-Stage Dispatch & Collection Timeline:</h4>
            <div class="tracking-timeline">
                ${order.tracking_steps.map((step, idx) => `
                    <div class="timeline-step">
                        <div class="timeline-dot ${step.status === 'COMPLETED' ? 'completed' : (step.status === 'IN_PROGRESS' ? 'active' : '')}"></div>
                        <div style="display:flex; justify-content:space-between;">
                            <strong>${step.step}</strong>
                            <span class="text-muted" style="font-size:12px;">${step.timestamp}</span>
                        </div>
                        <span class="badge ${step.status === 'COMPLETED' ? 'badge-success' : (step.status === 'IN_PROGRESS' ? 'badge-warning' : '')}" style="font-size:10px; margin-top:4px;">
                            ${step.status}
                        </span>
                    </div>
                `).join("")}
            </div>

            <div class="mt-4 pt-3" style="border-top:1px solid #e2e8f0; display:flex; justify-content:space-between; align-items:center;">
                <span class="text-muted" style="font-size:12.5px;">🔒 Cryptographically Signed Procurement Manifest via AgriConnect Supply Intelligence</span>
                <button class="btn-sm" onclick="window.print()">🖨️ Print Dispatch Manifest</button>
            </div>
        </div>
    `;
}

// 14. Clear Route and Reset Maps when 0 farmers matched
function clearRouteAndMaps() {
    if (state.miniMap) {
        state.miniMapLayers.forEach(layer => state.miniMap.removeLayer(layer));
        state.miniMapLayers = [];
    }
    if (state.fullMap) {
        state.fullMapLayers.forEach(layer => state.fullMap.removeLayer(layer));
        state.fullMapLayers = [];
    }
    state.currentRoute = null;

    const legsPreview = document.getElementById("routeLegsPreview");
    if (legsPreview) {
        legsPreview.innerHTML = `<div class="text-muted text-center py-2">No active collection route. Restock supply or reduce required volume.</div>`;
    }

    const fullMapDist = document.getElementById("fullMapDistanceBadge");
    if (fullMapDist) fullMapDist.textContent = `— km Total Circuit`;

    const logTotal = document.getElementById("logTotalDist");
    if (logTotal) logTotal.textContent = `— km`;

    const logUnopt = document.getElementById("logUnoptDist");
    if (logUnopt) logUnopt.textContent = `— km`;

    const logSaved = document.getElementById("logDistSaved");
    if (logSaved) logSaved.textContent = `— km (—%)`;

    const logHours = document.getElementById("logTransitHours");
    if (logHours) logHours.textContent = `— hrs`;

    const logFuel = document.getElementById("logFuelCost");
    if (logFuel) logFuel.textContent = `₹—`;

    const logCarbon = document.getElementById("logCarbonSaved");
    if (logCarbon) logCarbon.textContent = `— kg CO2`;

    const waypointsEl = document.getElementById("routeStepsContainer");
    if (waypointsEl) {
        waypointsEl.innerHTML = `<div class="text-muted text-center py-3">No active waypoints. Run analysis with available supply.</div>`;
    }
}

// 15. Restock Farmer Produce Inventory
async function restockSupplies(productId = null) {
    const restockBtn = document.getElementById("restockBtn");
    if (restockBtn) {
        restockBtn.disabled = true;
        restockBtn.innerHTML = `<span>⏳ Restocking...</span>`;
    }

    try {
        const url = productId 
            ? `${API_BASE}/api/supplies/restock?product_id=${productId}`
            : `${API_BASE}/api/supplies/restock`;
        
        const res = await fetch(url, { method: "POST" });
        const data = await res.json();
        
        if (res.ok) {
            showNotification(data.message || "Farmer supplies successfully restocked to full harvest capacity!");
            await runCompleteAnalysis();
        } else {
            alert("Restock failed: " + (data.detail || "Server error"));
        }
    } catch (err) {
        console.error("Restock error:", err);
        alert("Could not reach backend to restock supplies.");
    } finally {
        if (restockBtn) {
            restockBtn.disabled = false;
            restockBtn.innerHTML = `<span>🔄 Restock</span>`;
        }
    }
}

// 16. Load Platform Order History
async function loadOrderHistory(btn = null) {
    const refreshBtn = btn || document.getElementById("refreshOrdersBtn");
    if (refreshBtn) {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = `<span>⏳ Refreshing...</span>`;
    }

    const tbody = document.getElementById("ordersHistoryTableBody");
    if (!tbody) {
        if (refreshBtn) {
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = `<span>🔄 Refresh History</span>`;
        }
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/orders`);
        if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load orders`);
        const orders = await res.json();

        if (!orders || orders.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No procurement orders placed yet.</td></tr>`;
            if (btn) showNotification("Order history is currently empty.");
            return;
        }

        tbody.innerHTML = orders.map(o => {
            const isCancelled = o.status === "CANCELLED";
            const statusBadge = isCancelled 
                ? `<span class="badge badge-danger">CANCELLED</span>`
                : `<span class="badge badge-success">${o.status || "CONFIRMED"}</span>`;
            
            const actionBtn = isCancelled
                ? `<span class="text-muted" style="font-size:12px;">Stock Returned</span>`
                : `<button class="btn-cancel-order" onclick="cancelOrder(${o.id}, '${o.order_number}')">Cancel & Return Stock</button>`;

            const qty = typeof o.total_quantity === "number" ? o.total_quantity.toLocaleString() : (o.total_quantity || 0);
            const rate = typeof o.agreed_price_per_kg === "number" ? o.agreed_price_per_kg.toFixed(2) : (o.agreed_price_per_kg || 0);
            const total = typeof o.grand_total === "number" ? o.grand_total.toLocaleString() : (o.grand_total || 0);

            return `
                <tr>
                    <td><strong>#${o.order_number}</strong></td>
                    <td class="text-muted" style="font-size:12px;">${o.created_at || "—"}</td>
                    <td><strong>${o.product_name || "Produce"}</strong></td>
                    <td><strong>${qty} kg</strong></td>
                    <td>₹${rate}/kg</td>
                    <td><strong style="color:#15803d;">₹${total}</strong></td>
                    <td>${statusBadge}</td>
                    <td>${actionBtn}</td>
                </tr>
            `;
        }).join("");

        if (btn) {
            showNotification(`Updated: ${orders.length} order(s) loaded!`);
        }
    } catch (err) {
        console.error("Error loading order history:", err);
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-4">⚠️ Could not load order history (${err.message}). Ensure backend is reachable.</td></tr>`;
        showNotification("Failed to load order history.");
    } finally {
        if (refreshBtn) {
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = `<span>🔄 Refresh History</span>`;
        }
    }
}

// 17. Cancel Order and Return Stock to Farmers
async function cancelOrder(orderId, orderNum) {
    if (!confirm(`Cancel order #${orderNum} and return produce back to farmers' inventory?`)) {
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/orders/${orderId}/cancel`, { method: "POST" });
        const data = await res.json();
        if (res.ok) {
            showNotification(data.message || `Order #${orderNum} cancelled successfully!`);
            await loadOrderHistory();
            await runCompleteAnalysis();
        } else {
            alert(data.detail || "Could not cancel order");
        }
    } catch (err) {
        console.error("Cancel order error:", err);
        alert("Failed to cancel order.");
    }
}

// 18. Toast Notification Helper
function showNotification(msg) {
    let toast = document.getElementById("appToast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "appToast";
        toast.className = "app-toast";
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => {
        toast.classList.remove("show");
    }, 3800);
}

// Explicit window scope bindings
window.loadOrderHistory = loadOrderHistory;
window.cancelOrder = cancelOrder;
window.restockSupplies = restockSupplies;
window.runCompleteAnalysis = runCompleteAnalysis;
window.onDemandParamsChange = onDemandParamsChange;
window.onProductChange = onProductChange;
window.switchTab = switchTab;
window.generateProcurementContract = generateProcurementContract;
window.simulateNegotiationOffer = simulateNegotiationOffer;