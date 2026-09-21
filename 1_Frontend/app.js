// Dynamically resolve Backend API Base URL:
// - Cloud/Production (Render) or local uvicorn: use same origin (window.location.origin)
// - VS Code Live Server (port 5500) or file://: point to local backend (http://127.0.0.1:8000) or deployed backend
const API_BASE = (() => {
    if (window.location.protocol === "file:" || window.location.origin === "null" || !window.location.origin) {
        return "https://farmbuy-ai-backend.onrender.com";
    }
    if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
        return window.location.port === "8000" ? window.location.origin : "http://127.0.0.1:8000";
    }
    return window.location.origin;
})();

let state = {
    products: [],
    currentUser: null,
    currentMatching: null,
    currentForecast: null,
    currentPriceInsight: null,
    currentRoute: null,
    miniMap: null,
    fullMap: null,
    miniMapLayers: [],
    fullMapLayers: [],
    forecastChart: null,
    farmerForecastChart: null,
    currentFarmerForecast: null,
    negotiatedPrices: {},
    farmerNegotiatedPrices: {}
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
    initAuthState();
    // Preload order history for Orders & Tracking tab
    loadOrderHistory();
});

// ============================================================================
// TRI-LOGIN PORTAL & AUTHENTICATION (FARMER, BUYER, ADMIN/OWNER)
// ============================================================================

// Toggle active role tab in portal (Farmer vs Buyer vs Admin)
function setPortalRole(role) {
    const tabFarmer = document.getElementById("portalTabFarmer");
    const tabBuyer = document.getElementById("portalTabBuyer");
    const tabAdmin = document.getElementById("portalTabAdmin");
    const sectionFarmer = document.getElementById("portalFarmerSection");
    const sectionBuyer = document.getElementById("portalBuyerSection");
    const sectionAdmin = document.getElementById("portalAdminSection");

    [tabFarmer, tabBuyer, tabAdmin].forEach(t => t && t.classList.remove("active"));
    [sectionFarmer, sectionBuyer, sectionAdmin].forEach(s => {
        if (s) {
            s.style.display = "none";
            s.classList.remove("active");
        }
    });

    if (role === "farmer") {
        if (tabFarmer) tabFarmer.classList.add("active");
        if (sectionFarmer) {
            sectionFarmer.style.display = "block";
            sectionFarmer.classList.add("active");
        }
    } else if (role === "buyer") {
        if (tabBuyer) tabBuyer.classList.add("active");
        if (sectionBuyer) {
            sectionBuyer.style.display = "block";
            sectionBuyer.classList.add("active");
        }
    } else if (role === "admin") {
        if (tabAdmin) tabAdmin.classList.add("active");
        if (sectionAdmin) {
            sectionAdmin.style.display = "block";
            sectionAdmin.classList.add("active");
        }
    }
}

// Switch Farmer sub-mode (Login vs Registration)
function setFarmerAuthMode(mode) {
    const btnLogin = document.getElementById("farmerSubModeLogin");
    const btnReg = document.getElementById("farmerSubModeRegister");
    const loginContainer = document.getElementById("farmerLoginContainer");
    const regContainer = document.getElementById("farmerRegisterContainer");

    if (mode === "login") {
        if (btnLogin) {
            btnLogin.classList.add("active");
            btnLogin.style.background = "#ffffff";
            btnLogin.style.color = "#16a34a";
            btnLogin.style.boxShadow = "0 1px 3px rgba(0,0,0,0.1)";
        }
        if (btnReg) {
            btnReg.classList.remove("active");
            btnReg.style.background = "transparent";
            btnReg.style.color = "#64748b";
            btnReg.style.boxShadow = "none";
        }
        if (loginContainer) loginContainer.style.display = "block";
        if (regContainer) regContainer.style.display = "none";
    } else {
        if (btnReg) {
            btnReg.classList.add("active");
            btnReg.style.background = "#ffffff";
            btnReg.style.color = "#16a34a";
            btnReg.style.boxShadow = "0 1px 3px rgba(0,0,0,0.1)";
        }
        if (btnLogin) {
            btnLogin.classList.remove("active");
            btnLogin.style.background = "transparent";
            btnLogin.style.color = "#64748b";
            btnLogin.style.boxShadow = "none";
        }
        if (loginContainer) loginContainer.style.display = "none";
        if (regContainer) regContainer.style.display = "block";
    }
}

// Switch Buyer sub-mode (Login vs Registration)
function setBuyerAuthMode(mode) {
    const btnLogin = document.getElementById("buyerSubModeLogin");
    const btnReg = document.getElementById("buyerSubModeRegister");
    const loginContainer = document.getElementById("buyerLoginContainer");
    const regContainer = document.getElementById("buyerRegisterContainer");

    if (mode === "login") {
        if (btnLogin) {
            btnLogin.classList.add("active");
            btnLogin.style.background = "#ffffff";
            btnLogin.style.color = "#2563eb";
            btnLogin.style.boxShadow = "0 1px 3px rgba(0,0,0,0.1)";
        }
        if (btnReg) {
            btnReg.classList.remove("active");
            btnReg.style.background = "transparent";
            btnReg.style.color = "#64748b";
            btnReg.style.boxShadow = "none";
        }
        if (loginContainer) loginContainer.style.display = "block";
        if (regContainer) regContainer.style.display = "none";
    } else {
        if (btnReg) {
            btnReg.classList.add("active");
            btnReg.style.background = "#ffffff";
            btnReg.style.color = "#2563eb";
            btnReg.style.boxShadow = "0 1px 3px rgba(0,0,0,0.1)";
        }
        if (btnLogin) {
            btnLogin.classList.remove("active");
            btnLogin.style.background = "transparent";
            btnLogin.style.color = "#64748b";
            btnLogin.style.boxShadow = "none";
        }
        if (loginContainer) loginContainer.style.display = "none";
        if (regContainer) regContainer.style.display = "block";
    }
}

// Helper: Authenticated fetch sending Bearer token with fresh data guarantees
async function authFetch(url, options = {}) {
    const headers = {
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        ...(options.headers || {})
    };
    if (state.currentUser && state.currentUser.access_token) {
        headers["Authorization"] = `Bearer ${state.currentUser.access_token}`;
    }
    const res = await fetch(url, { cache: "no-store", ...options, headers });
    if (res.status === 401) {
        showToast("⚠️ Authentication session expired. Please log in again.", "warning");
        handleLogout();
    }
    return res;
}

// Helper: Show / Hide password visibility toggle for password fields
function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === "password") {
        input.type = "text";
        if (btn) {
            btn.innerHTML = "👁️‍🗨️";
            btn.title = "Hide password";
            btn.setAttribute("aria-label", "Hide password");
        }
    } else {
        input.type = "password";
        if (btn) {
            btn.innerHTML = "👁️";
            btn.title = "Show password";
            btn.setAttribute("aria-label", "Show password");
        }
    }
}

// Check saved session on load
function initAuthState() {
    const saved = localStorage.getItem("farmbuy_user");
    if (saved) {
        try {
            state.currentUser = JSON.parse(saved);
        } catch (e) {
            state.currentUser = null;
        }
    }

    const portalScreen = document.getElementById("portalLoginScreen");
    const mainScreen = document.getElementById("mainPlatformScreen");

    if (state.currentUser) {
        // User is logged in -> show main platform
        if (portalScreen) portalScreen.style.display = "none";
        if (mainScreen) mainScreen.style.display = "block";
        applyUserPlatformView();
    } else {
        // No user logged in -> present dedicated 3-option login screen directly
        if (portalScreen) portalScreen.style.display = "flex";
        if (mainScreen) mainScreen.style.display = "none";
    }
}

// Apply role-based platform view and user header pill (Farmer, Buyer, Admin, Owner)
function applyUserPlatformView() {
    const user = state.currentUser;
    if (!user) return;

    const navPill = document.getElementById("navUserStatusPill");
    const navIcon = document.getElementById("navUserRoleIcon");
    const navName = document.getElementById("navUserName");
    const farmerNav = document.getElementById("farmerNavLinks");
    const buyerNav = document.getElementById("buyerNavLinks");
    const adminNav = document.getElementById("adminNavLinks");
    const farmerSection = document.getElementById("farmerDashboardSection");
    const buyerSection = document.getElementById("buyerDashboardSection");
    const adminSection = document.getElementById("adminDashboardSection");
    const ownerNavTab = document.getElementById("adminNavTabManagement");

    if (user.role === "farmer") {
        if (navIcon) navIcon.textContent = "🌾";
        if (navName) navName.textContent = `Farmer: ${user.name}`;
        if (navPill) navPill.className = "user-status-pill farmer-pill";

        if (buyerNav) buyerNav.style.display = "none";
        if (adminNav) adminNav.style.display = "none";
        if (farmerNav) farmerNav.style.display = "flex";

        if (buyerSection) buyerSection.style.display = "none";
        if (adminSection) adminSection.style.display = "none";
        if (farmerSection) farmerSection.style.display = "block";

        const welcomeTitle = document.getElementById("farmerPortalWelcome");
        if (welcomeTitle) welcomeTitle.textContent = `🌾 Welcome, Farmer ${user.name}!`;
        const addrSub = document.getElementById("farmerPortalAddressSub");
        if (addrSub) addrSub.textContent = `${user.address || "Farm Gate"}, ${user.state || ""} (${user.pincode || ""}) • Phone: ${user.phone || ""}`;

        loadFarmerProduceList();
    } else if (user.role === "buyer") {
        if (navIcon) navIcon.textContent = "🏢";
        if (navName) navName.textContent = `Buyer: ${user.name}`;
        if (navPill) navPill.className = "user-status-pill buyer-pill";

        if (farmerNav) farmerNav.style.display = "none";
        if (adminNav) adminNav.style.display = "none";
        if (buyerNav) buyerNav.style.display = "flex";

        if (farmerSection) farmerSection.style.display = "none";
        if (adminSection) adminSection.style.display = "none";
        if (buyerSection) buyerSection.style.display = "block";

        loadProducts();
        runCompleteAnalysis();

        setTimeout(() => {
            if (state.miniMap) state.miniMap.invalidateSize();
            if (state.fullMap) state.fullMap.invalidateSize();
        }, 200);
    } else if (user.role === "admin" || user.role === "owner") {
        const isOwner = user.role === "owner";
        if (navIcon) navIcon.textContent = isOwner ? "👑" : "🛡️";
        if (navName) navName.textContent = isOwner ? `Owner: ${user.name}` : `Admin: ${user.name}`;
        if (navPill) navPill.className = isOwner ? "user-status-pill owner-pill" : "user-status-pill admin-pill";

        if (farmerNav) farmerNav.style.display = "none";
        if (buyerNav) buyerNav.style.display = "none";
        if (adminNav) adminNav.style.display = "flex";

        if (farmerSection) farmerSection.style.display = "none";
        if (buyerSection) buyerSection.style.display = "none";
        if (adminSection) adminSection.style.display = "block";

        // Show/hide owner-only management tab
        if (ownerNavTab) {
            ownerNavTab.style.display = isOwner ? "inline-block" : "none";
        }

        // Configure Admin banner
        const bName = document.getElementById("adminBannerName");
        const bBadge = document.getElementById("adminBannerRoleBadge");
        const bUserId = document.getElementById("adminBannerUserId");
        const bDesc = document.getElementById("adminBannerRoleDesc");

        if (bName) bName.textContent = user.name || "Administrator";
        if (bUserId) bUserId.textContent = user.admin_user_id || "admin";
        if (bBadge) {
            bBadge.textContent = isOwner ? "OWNER" : "ADMIN";
            bBadge.style.background = isOwner ? "#7c3aed" : "#3b82f6";
        }
        if (bDesc) {
            bDesc.textContent = isOwner
                ? "Full Platform Authority & Team Management"
                : "Operational Monitoring & Read Access";
        }

        switchAdminTab("overview");
    }
}

function scrollToFarmerSection(sectionId) {
    const el = document.getElementById(sectionId);
    if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

// 1. Farmer Login Handler
async function handleFarmerLoginSubmit(event) {
    if (event) event.preventDefault();
    const btn = document.getElementById("farmerLoginSubmitBtn");
    const originalText = btn ? btn.innerHTML : "🌾 Login as Farmer";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳ Verifying Farmer Credentials...</span>`;
    }

    const payload = {
        name: document.getElementById("farmerLoginNameInput").value.trim(),
        phone_number: document.getElementById("farmerLoginPhoneInput").value.trim()
    };

    try {
        const res = await fetch(`${API_BASE}/api/auth/farmer/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Farmer login failed.");
        }

        state.currentUser = {
            role: "farmer",
            id: data.user_id,
            name: data.name,
            phone: data.phone_number,
            address: data.address,
            pincode: data.pincode,
            state: data.state,
            details: data.details,
            access_token: data.access_token
        };
        localStorage.setItem("farmbuy_user", JSON.stringify(state.currentUser));

        const portalScreen = document.getElementById("portalLoginScreen");
        const mainScreen = document.getElementById("mainPlatformScreen");
        if (portalScreen) portalScreen.style.display = "none";
        if (mainScreen) mainScreen.style.display = "block";

        applyUserPlatformView();
        showToast(`🌱 Welcome back, Farmer ${data.name}!`, "success");
    } catch (err) {
        console.error("Farmer login error:", err);
        showToast(`⚠️ ${err.message}`, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

// 2. Farmer Register Handler
async function handleFarmerRegisterSubmit(event) {
    if (event) event.preventDefault();
    const btn = document.getElementById("farmerRegisterSubmitBtn");
    const originalText = btn ? btn.innerHTML : "📝 Register as Farmer";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳ Storing Farmer in Database...</span>`;
    }

    const nameVal = document.getElementById("farmerRegisterNameInput").value.trim();
    const phoneVal = document.getElementById("farmerRegisterPhoneInput").value.trim();

    const payload = {
        name: nameVal,
        phone_number: phoneVal,
        address: document.getElementById("farmerRegisterAddressInput").value.trim(),
        state: document.getElementById("farmerRegisterStateInput").value.trim(),
        pincode: document.getElementById("farmerRegisterPincodeInput").value.trim(),
        commodity: document.getElementById("farmerRegisterCropInput").value.trim(),
        quantity_kg: parseFloat(document.getElementById("farmerRegisterQtyInput").value),
        price_per_kg: parseFloat(document.getElementById("farmerRegisterPriceInput").value)
    };

    try {
        const res = await fetch(`${API_BASE}/api/auth/farmer/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Farmer registration failed.");
        }

        // Requirement notification: "Registration successful. You can now login."
        showToast("Registration successful. You can now login.", "success");

        // Switch to login sub-mode and prefill inputs
        setFarmerAuthMode("login");
        const loginName = document.getElementById("farmerLoginNameInput");
        const loginPhone = document.getElementById("farmerLoginPhoneInput");
        if (loginName) loginName.value = nameVal;
        if (loginPhone) loginPhone.value = phoneVal;

        // Clear registration form
        document.getElementById("farmerRegisterForm").reset();

        // Refresh products list in background so new crop is cached
        loadProducts();
    } catch (err) {
        console.error("Farmer registration error:", err);
        showToast(`⚠️ ${err.message}`, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

// 3. Buyer Login Handler
async function handleBuyerLoginSubmit(event) {
    if (event) event.preventDefault();
    const btn = document.getElementById("buyerLoginSubmitBtn");
    const originalText = btn ? btn.innerHTML : "🏢 Login as Buyer";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳ Verifying Buyer Credentials...</span>`;
    }

    const payload = {
        name: document.getElementById("buyerLoginNameInput").value.trim(),
        phone_number: document.getElementById("buyerLoginPhoneInput").value.trim()
    };

    try {
        const res = await fetch(`${API_BASE}/api/auth/buyer/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Buyer login failed.");
        }

        state.currentUser = {
            role: "buyer",
            id: data.user_id,
            name: data.name,
            phone: data.phone_number,
            address: data.address,
            pincode: data.pincode,
            state: data.state,
            details: data.details,
            access_token: data.access_token
        };
        localStorage.setItem("farmbuy_user", JSON.stringify(state.currentUser));

        const portalScreen = document.getElementById("portalLoginScreen");
        const mainScreen = document.getElementById("mainPlatformScreen");
        if (portalScreen) portalScreen.style.display = "none";
        if (mainScreen) mainScreen.style.display = "block";

        applyUserPlatformView();
        showToast(`🏢 Welcome back, ${data.name}!`, "success");
    } catch (err) {
        console.error("Buyer login error:", err);
        showToast(`⚠️ ${err.message}`, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

// 4. Buyer Register Handler
async function handleBuyerRegisterSubmit(event) {
    if (event) event.preventDefault();
    const btn = document.getElementById("buyerRegisterSubmitBtn");
    const originalText = btn ? btn.innerHTML : "📝 Register as Buyer";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳ Storing Buyer in Database...</span>`;
    }

    const nameVal = document.getElementById("buyerRegisterNameInput").value.trim();
    const phoneVal = document.getElementById("buyerRegisterPhoneInput").value.trim();

    const payload = {
        name: nameVal,
        address: document.getElementById("buyerRegisterAddressInput").value.trim(),
        city: document.getElementById("buyerRegisterCityInput").value.trim(),
        state: document.getElementById("buyerRegisterStateInput").value.trim(),
        pincode: document.getElementById("buyerRegisterPincodeInput").value.trim(),
        phone_number: phoneVal
    };

    try {
        const res = await fetch(`${API_BASE}/api/auth/buyer/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Buyer registration failed.");
        }

        // Requirement notification: "Registration successful. You can now login."
        showToast("Registration successful. You can now login.", "success");

        // Switch to buyer login sub-mode and prefill inputs
        setBuyerAuthMode("login");
        const loginName = document.getElementById("buyerLoginNameInput");
        const loginPhone = document.getElementById("buyerLoginPhoneInput");
        if (loginName) loginName.value = nameVal;
        if (loginPhone) loginPhone.value = phoneVal;

        // Clear registration form
        document.getElementById("buyerRegisterForm").reset();
    } catch (err) {
        console.error("Buyer registration error:", err);
        showToast(`⚠️ ${err.message}`, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

// 5. Admin & Owner Login Handler
async function handleAdminLoginSubmit(event) {
    if (event) event.preventDefault();
    const btn = document.getElementById("adminLoginSubmitBtn");
    const originalText = btn ? btn.innerHTML : "🛡️ Login to Admin Portal";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳ Authenticating Admin...</span>`;
    }

    const payload = {
        admin_user_id: document.getElementById("adminUserIdInput").value.trim(),
        password: document.getElementById("adminPasswordInput").value
    };

    try {
        const res = await fetch(`${API_BASE}/api/auth/admin/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Admin authentication failed.");
        }

        const roleLower = (data.role || "admin").toLowerCase();
        state.currentUser = {
            role: roleLower,
            id: data.user_id,
            name: data.name,
            admin_user_id: data.admin_user_id,
            access_token: data.access_token
        };
        localStorage.setItem("farmbuy_user", JSON.stringify(state.currentUser));

        // Switch to Platform View
        const portalScreen = document.getElementById("portalLoginScreen");
        const mainScreen = document.getElementById("mainPlatformScreen");
        if (portalScreen) portalScreen.style.display = "none";
        if (mainScreen) mainScreen.style.display = "block";

        applyUserPlatformView();
        showToast(`🛡️ Logged in as ${data.name} (${data.role})`, "success");
    } catch (err) {
        console.error("Admin login error:", err);
        showToast(`⚠️ ${err.message}`, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

// Legacy aliases for backward compatibility
const handlePortalFarmerSubmit = handleFarmerRegisterSubmit;
const handlePortalBuyerSubmit = handleBuyerRegisterSubmit;

// Logout & Return to Portal Login Screen
function handleLogout() {
    localStorage.removeItem("farmbuy_user");
    state.currentUser = null;

    const portalScreen = document.getElementById("portalLoginScreen");
    const mainScreen = document.getElementById("mainPlatformScreen");
    if (mainScreen) mainScreen.style.display = "none";
    if (portalScreen) portalScreen.style.display = "flex";

    showToast("🚪 Logged out. Choose Farmer, Buyer, or Admin to log in.", "info");
}

// ============================================================================
// ADMIN DASHBOARD & OWNER MANAGEMENT ENGINE
// ============================================================================
let currentAdminTab = "overview";

function switchAdminTab(tabName) {
    if (!state.currentUser || (state.currentUser.role !== "admin" && state.currentUser.role !== "owner")) {
        return;
    }

    // Owner protection check for management tab
    if (tabName === "management" && state.currentUser.role !== "owner") {
        showToast("⚠️ Admin Team Management is restricted to Super Admin (Owner).", "warning");
        tabName = "overview";
    }

    currentAdminTab = tabName;

    // Update nav tab buttons in #adminNavLinks
    const navTabs = document.querySelectorAll("#adminNavLinks .nav-tab");
    navTabs.forEach(t => t.classList.remove("active"));
    const activeTabBtn = {
        overview: document.getElementById("adminNavTabOverview"),
        farmers: document.getElementById("adminNavTabFarmers"),
        buyers: document.getElementById("adminNavTabBuyers"),
        supplies: document.getElementById("adminNavTabSupplies"),
        orders: document.getElementById("adminNavTabOrders"),
        management: document.getElementById("adminNavTabManagement")
    }[tabName];
    if (activeTabBtn) activeTabBtn.classList.add("active");

    // Show selected tab pane, hide others
    const panes = {
        overview: document.getElementById("adminTabPaneOverview"),
        farmers: document.getElementById("adminTabPaneFarmers"),
        buyers: document.getElementById("adminTabPaneBuyers"),
        supplies: document.getElementById("adminTabPaneSupplies"),
        orders: document.getElementById("adminTabPaneOrders"),
        management: document.getElementById("adminTabPaneManagement")
    };

    Object.keys(panes).forEach(k => {
        if (panes[k]) panes[k].style.display = k === tabName ? "block" : "none";
    });

    // Load data for active tab
    refreshCurrentAdminTab();
}

function refreshCurrentAdminTab() {
    switch (currentAdminTab) {
        case "overview":
            loadAdminOverview();
            break;
        case "farmers":
            loadAdminFarmers();
            break;
        case "buyers":
            loadAdminBuyers();
            break;
        case "supplies":
            loadAdminSupplies();
            break;
        case "orders":
            loadAdminOrders();
            break;
        case "management":
            loadAdminAccounts();
            break;
    }
}

// 1. Load Platform Overview Stats
async function loadAdminOverview() {
    try {
        const res = await authFetch(`${API_BASE}/api/admin/stats`);
        if (!res.ok) throw new Error("Failed to load platform statistics.");
        const data = await res.json();

        const kpiFarmers = document.getElementById("adminKpiTotalFarmers");
        const kpiBuyers = document.getElementById("adminKpiTotalBuyers");
        const kpiSuppliesKg = document.getElementById("adminKpiTotalSuppliesKg");
        const kpiSuppliesCount = document.getElementById("adminKpiTotalSuppliesCount");
        const kpiOrdersVal = document.getElementById("adminKpiTotalOrdersValue");
        const kpiOrdersCount = document.getElementById("adminKpiTotalOrdersCount");
        const kpiAdmins = document.getElementById("adminKpiActiveAdmins");

        if (kpiFarmers) kpiFarmers.textContent = Number(data.farmers_count || 0).toLocaleString();
        if (kpiBuyers) kpiBuyers.textContent = Number(data.buyers_count || 0).toLocaleString();
        if (kpiSuppliesKg) kpiSuppliesKg.textContent = `${Number(data.supplies_total_kg || 0).toLocaleString()} kg`;
        if (kpiSuppliesCount) kpiSuppliesCount.textContent = Number(data.supplies_count || 0).toLocaleString();
        if (kpiOrdersVal) kpiOrdersVal.textContent = `₹ ${Number(data.orders_total_val || 0).toLocaleString()}`;
        if (kpiOrdersCount) kpiOrdersCount.textContent = Number(data.orders_count || 0).toLocaleString();
        if (kpiAdmins) kpiAdmins.textContent = `${data.active_admins_count || 0} / 6`;
    } catch (err) {
        console.error("Admin stats error:", err);
    }
}

// Cache for Admin Farmers and Buyers data
window.__adminFarmersCache = {};
window.__adminBuyersCache = {};

// 2. Load Farmers Directory
async function loadAdminFarmers() {
    const tbody = document.getElementById("adminFarmersTableBody");
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="7" class="text-muted text-center py-3">Loading farmers directory...</td></tr>`;

    try {
        const res = await authFetch(`${API_BASE}/api/admin/farmers`);
        if (!res.ok) throw new Error("Failed to load farmers.");
        const farmers = await res.json();

        if (!farmers || farmers.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-muted text-center py-3">No farmers registered yet.</td></tr>`;
            return;
        }

        window.__adminFarmersCache = {};
        tbody.innerHTML = farmers.map(f => {
            window.__adminFarmersCache[f.id] = f;
            const phone = f.phone_number || f.contact || "N/A";
            return `
                <tr>
                    <td><strong>#${f.id}</strong></td>
                    <td style="font-weight:700; color:#1e293b;">${escapeHtml(f.name)}</td>
                    <td>📞 ${escapeHtml(phone)}</td>
                    <td>${escapeHtml(f.address || f.location || "Farm Gate")}</td>
                    <td>${escapeHtml(f.state || "N/A")}</td>
                    <td><code>${escapeHtml(f.pincode || "N/A")}</code></td>
                    <td style="text-align:center;">
                        <div style="display:flex; gap:6px; justify-content:center; flex-wrap:wrap;">
                            <button type="button" class="admin-action-btn" onclick="openEditFarmerModal(${f.id})" title="Edit Farmer Details">✏️ Edit</button>
                            <button type="button" class="admin-action-btn delete" onclick="deleteFarmerRecord(${f.id})" title="Delete Farmer">🗑️ Delete</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");
    } catch (err) {
        console.error("Farmers load error:", err);
        tbody.innerHTML = `<tr><td colspan="7" class="text-danger text-center py-3">Error loading farmers: ${err.message}</td></tr>`;
    }
}

// 2b. Admin: Edit Farmer Modal Controls & Handlers
function openEditFarmerModal(farmerId) {
    const f = window.__adminFarmersCache[farmerId];
    if (!f) return;
    const modal = document.getElementById("adminEditFarmerModal");
    const idInput = document.getElementById("editFarmerId");
    const nameInput = document.getElementById("editFarmerNameInput");
    const phoneInput = document.getElementById("editFarmerPhoneInput");
    const addrInput = document.getElementById("editFarmerAddressInput");
    const stateInput = document.getElementById("editFarmerStateInput");
    const pinInput = document.getElementById("editFarmerPincodeInput");

    if (idInput) idInput.value = f.id;
    if (nameInput) nameInput.value = f.name || "";
    if (phoneInput) phoneInput.value = f.phone_number || f.contact || "";
    if (addrInput) addrInput.value = f.address || "";
    if (stateInput) stateInput.value = f.state || "West Bengal";
    if (pinInput) pinInput.value = f.pincode || "";

    if (modal) modal.style.display = "flex";
}

function closeEditFarmerModal() {
    const modal = document.getElementById("adminEditFarmerModal");
    if (modal) modal.style.display = "none";
}

async function handleEditFarmerSubmit(event) {
    if (event) event.preventDefault();
    const btn = document.getElementById("saveEditFarmerBtn");
    const originalText = btn ? btn.innerHTML : "💾 Update Farmer";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳ Saving...</span>`;
    }

    const farmerId = document.getElementById("editFarmerId").value;
    const payload = {
        name: document.getElementById("editFarmerNameInput").value.trim(),
        phone_number: document.getElementById("editFarmerPhoneInput").value.trim(),
        address: document.getElementById("editFarmerAddressInput").value.trim(),
        state: document.getElementById("editFarmerStateInput").value.trim(),
        pincode: document.getElementById("editFarmerPincodeInput").value.trim()
    };

    try {
        const res = await authFetch(`${API_BASE}/api/admin/farmers/${farmerId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update farmer.");

        closeEditFarmerModal();
        showToast(data.message || `🌾 Farmer #${farmerId} updated successfully.`, "success");
        loadAdminFarmers();
        loadAdminOverview();
    } catch (err) {
        console.error("Edit farmer error:", err);
        showToast(`⚠️ ${err.message}`, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

async function deleteFarmerRecord(farmerId) {
    const f = window.__adminFarmersCache[farmerId] || {};
    const name = f.name || `#${farmerId}`;
    if (!confirm(`Are you sure you want to permanently delete Farmer "${name}" (ID: #${farmerId}) and all their listed produce?\n\nBoth Admins and Super Admins have permission to perform this action.`)) {
        return;
    }

    try {
        const res = await authFetch(`${API_BASE}/api/admin/farmers/${farmerId}`, {
            method: "DELETE"
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to delete farmer.");

        showToast(data.message || `🗑️ Farmer #${farmerId} deleted successfully.`, "success");
        loadAdminFarmers();
        loadAdminSupplies();
        loadAdminOverview();
    } catch (err) {
        console.error("Delete farmer error:", err);
        showToast(`⚠️ ${err.message}`, "error");
    }
}

// 3. Load Buyers Directory
async function loadAdminBuyers() {
    const tbody = document.getElementById("adminBuyersTableBody");
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="9" class="text-muted text-center py-3">Loading buyers directory...</td></tr>`;

    try {
        const res = await authFetch(`${API_BASE}/api/admin/buyers`);
        if (!res.ok) throw new Error("Failed to load buyers.");
        const buyers = await res.json();

        if (!buyers || buyers.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-muted text-center py-3">No buyers registered yet.</td></tr>`;
            return;
        }

        window.__adminBuyersCache = {};
        tbody.innerHTML = buyers.map(b => {
            window.__adminBuyersCache[b.id] = b;
            return `
                <tr>
                    <td><strong>#${b.id}</strong></td>
                    <td style="font-weight:700; color:#1e293b;">${escapeHtml(b.name)}</td>
                    <td>📞 ${escapeHtml(b.phone_number || "N/A")}</td>
                    <td>${escapeHtml(b.address || "Central Depot")}</td>
                    <td>${escapeHtml(b.city || "N/A")}</td>
                    <td>${escapeHtml(b.state || "N/A")}</td>
                    <td><code>${escapeHtml(b.pincode || "N/A")}</code></td>
                    <td style="font-size:12px; color:#64748b;">${b.created_at ? new Date(b.created_at).toLocaleDateString() : "—"}</td>
                    <td style="text-align:center;">
                        <div style="display:flex; gap:6px; justify-content:center; flex-wrap:wrap;">
                            <button type="button" class="admin-action-btn" onclick="openEditBuyerModal(${b.id})" title="Edit Buyer Details">✏️ Edit</button>
                            <button type="button" class="admin-action-btn delete" onclick="deleteBuyerRecord(${b.id})" title="Delete Buyer">🗑️ Delete</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");
    } catch (err) {
        console.error("Buyers load error:", err);
        tbody.innerHTML = `<tr><td colspan="9" class="text-danger text-center py-3">Error loading buyers: ${err.message}</td></tr>`;
    }
}

// 3b. Admin: Edit Buyer Modal Controls & Handlers
function openEditBuyerModal(buyerId) {
    const b = window.__adminBuyersCache[buyerId];
    if (!b) return;
    const modal = document.getElementById("adminEditBuyerModal");
    const idInput = document.getElementById("editBuyerId");
    const nameInput = document.getElementById("editBuyerNameInput");
    const phoneInput = document.getElementById("editBuyerPhoneInput");
    const addrInput = document.getElementById("editBuyerAddressInput");
    const cityInput = document.getElementById("editBuyerCityInput");
    const stateInput = document.getElementById("editBuyerStateInput");
    const pinInput = document.getElementById("editBuyerPincodeInput");

    if (idInput) idInput.value = b.id;
    if (nameInput) nameInput.value = b.name || "";
    if (phoneInput) phoneInput.value = b.phone_number || "";
    if (addrInput) addrInput.value = b.address || "";
    if (cityInput) cityInput.value = b.city || "";
    if (stateInput) stateInput.value = b.state || "West Bengal";
    if (pinInput) pinInput.value = b.pincode || "";

    if (modal) modal.style.display = "flex";
}

function closeEditBuyerModal() {
    const modal = document.getElementById("adminEditBuyerModal");
    if (modal) modal.style.display = "none";
}

async function handleEditBuyerSubmit(event) {
    if (event) event.preventDefault();
    const btn = document.getElementById("saveEditBuyerBtn");
    const originalText = btn ? btn.innerHTML : "💾 Update Buyer";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳ Saving...</span>`;
    }

    const buyerId = document.getElementById("editBuyerId").value;
    const payload = {
        name: document.getElementById("editBuyerNameInput").value.trim(),
        phone_number: document.getElementById("editBuyerPhoneInput").value.trim(),
        address: document.getElementById("editBuyerAddressInput").value.trim(),
        city: document.getElementById("editBuyerCityInput").value.trim(),
        state: document.getElementById("editBuyerStateInput").value.trim(),
        pincode: document.getElementById("editBuyerPincodeInput").value.trim()
    };

    try {
        const res = await authFetch(`${API_BASE}/api/admin/buyers/${buyerId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update buyer.");

        closeEditBuyerModal();
        showToast(data.message || `🏢 Buyer #${buyerId} updated successfully.`, "success");
        loadAdminBuyers();
        loadAdminOverview();
    } catch (err) {
        console.error("Edit buyer error:", err);
        showToast(`⚠️ ${err.message}`, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

async function deleteBuyerRecord(buyerId) {
    const b = window.__adminBuyersCache[buyerId] || {};
    const name = b.name || `#${buyerId}`;
    if (!confirm(`Are you sure you want to permanently delete Buyer "${name}" (ID: #${buyerId})?\n\nBoth Admins and Super Admins have permission to perform this action.`)) {
        return;
    }

    try {
        const res = await authFetch(`${API_BASE}/api/admin/buyers/${buyerId}`, {
            method: "DELETE"
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to delete buyer.");

        showToast(data.message || `🗑️ Buyer #${buyerId} deleted successfully.`, "success");
        loadAdminBuyers();
        loadAdminOverview();
    } catch (err) {
        console.error("Delete buyer error:", err);
        showToast(`⚠️ ${err.message}`, "error");
    }
}

// 4. Load Supplies Inventory
async function loadAdminSupplies() {
    const tbody = document.getElementById("adminSuppliesTableBody");
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="8" class="text-muted text-center py-3">Loading live supplies...</td></tr>`;

    try {
        const res = await authFetch(`${API_BASE}/api/admin/supplies`);
        if (!res.ok) throw new Error("Failed to load supplies.");
        const supplies = await res.json();

        if (!supplies || supplies.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-muted text-center py-3">No active produce listed in inventory.</td></tr>`;
            return;
        }

        tbody.innerHTML = supplies.map(s => {
            const comm = s.commodity || s.product_name || "Produce";
            const qty = Number(s.quantity_kg ?? s.quantity_left_kg ?? 0);
            const price = Number(s.price_per_kg ?? s.expected_price ?? 0);
            return `
                <tr>
                    <td><strong>#${s.id}</strong></td>
                    <td><code>F-${s.farmer_id}</code></td>
                    <td style="font-weight:600; color:#1e293b;">${escapeHtml(s.farmer_name || `Farmer #${s.farmer_id}`)}</td>
                    <td><strong>${escapeHtml(comm)}</strong></td>
                    <td><span style="font-weight:700; color:#15803d;">${qty.toLocaleString()} kg</span></td>
                    <td>₹ ${price.toFixed(2)} / kg</td>
                    <td><span class="badge" style="background:#f1f5f9; color:#475569; font-size:11px;">${escapeHtml(s.quality_grade || "Grade A")}</span></td>
                    <td style="font-size:12px; color:#64748b;">${escapeHtml(s.available_date || "Today")}</td>
                </tr>
            `;
        }).join("");
    } catch (err) {
        console.error("Supplies load error:", err);
        tbody.innerHTML = `<tr><td colspan="8" class="text-danger text-center py-3">Error loading supplies: ${err.message}</td></tr>`;
    }
}

// 5. Load Platform Orders
async function loadAdminOrders() {
    const tbody = document.getElementById("adminOrdersTableBody");
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="8" class="text-muted text-center py-3">Loading platform orders...</td></tr>`;

    try {
        const res = await authFetch(`${API_BASE}/api/admin/orders`);
        if (!res.ok) throw new Error("Failed to load orders.");
        const orders = await res.json();

        if (!orders || orders.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-muted text-center py-3">No platform orders placed yet.</td></tr>`;
            return;
        }

        tbody.innerHTML = orders.map(o => {
            const orderCode = o.order_code || o.order_number || `#${o.id}`;
            const commodity = o.commodity || o.product_name || "Produce";
            const qty = Number(o.total_quantity_kg ?? o.total_quantity ?? 0);
            const totalCost = Number(o.total_cost ?? o.total_procurement_cost ?? o.grand_total ?? 0);
            const distance = Number(o.total_distance_km ?? o.estimated_distance_km ?? 0);
            const timeStr = o.created_at || "N/A";

            return `
                <tr>
                    <td><strong>${escapeHtml(orderCode)}</strong></td>
                    <td style="font-size:12px; color:#64748b;">${escapeHtml(timeStr)}</td>
                    <td style="font-weight:700; color:#1e293b;">${escapeHtml(o.buyer_name || "Buyer")}</td>
                    <td><strong>${escapeHtml(commodity)}</strong></td>
                    <td>${qty.toLocaleString()} kg</td>
                    <td style="font-weight:700; color:#15803d;">₹ ${totalCost.toLocaleString()}</td>
                    <td>${distance > 0 ? `${distance.toFixed(1)} km TSP Route` : "Direct Hub"}</td>
                    <td>
                        <span class="badge ${o.status === 'CANCELLED' ? 'badge-danger' : 'badge-success'}" style="font-size:11px;">
                            ${escapeHtml(o.status || "CONFIRMED")}
                        </span>
                    </td>
                </tr>
            `;
        }).join("");
    } catch (err) {
        console.error("Orders load error:", err);
        tbody.innerHTML = `<tr><td colspan="8" class="text-danger text-center py-3">Error loading orders: ${err.message}</td></tr>`;
    }
}

// 6. Owner Management: Load Admin Accounts
async function loadAdminAccounts() {
    if (!state.currentUser || state.currentUser.role !== "owner") return;

    const tbody = document.getElementById("adminAccountsTableBody");
    const quotaBadge = document.getElementById("adminQuotaBadge");
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="7" class="text-muted text-center py-3">Loading system administrators...</td></tr>`;

    try {
        const res = await authFetch(`${API_BASE}/api/admin/manage/admins`);
        if (!res.ok) throw new Error("Failed to load administrator accounts.");
        const accounts = await res.json();

        const regularAdminCount = accounts.filter(a => a.role !== "OWNER").length;
        if (quotaBadge) {
            quotaBadge.textContent = `Admins: ${regularAdminCount} / 6`;
            quotaBadge.style.background = regularAdminCount >= 6 ? "#dc2626" : "#7c3aed";
        }

        tbody.innerHTML = accounts.map(a => {
            const isOwner = a.role === "OWNER";
            const roleBadge = isOwner
                ? `<span class="badge-owner">OWNER</span>`
                : `<span class="badge-admin">ADMIN</span>`;
            const statusBadge = a.is_active
                ? `<span class="badge-active">● Active</span>`
                : `<span class="badge-disabled">○ Disabled</span>`;

            const actions = isOwner
                ? `<button type="button" class="admin-action-btn" style="background:#5b21b6; color:white; border-color:#4c1d95;" onclick="openSuperAdminCredsModal()" title="Change Super Admin Credentials">👑 Change Creds</button>`
                : `
                    <div style="display:flex; gap:6px; justify-content:center; flex-wrap:wrap;">
                        <button type="button" class="admin-action-btn" onclick="openChangeAdminIdModal(${a.id}, '${escapeHtml(a.admin_user_id)}', '${escapeHtml(a.name)}')" title="Change User ID">✏️ Change ID</button>
                        <button type="button" class="admin-action-btn" onclick="openChangeAdminPasswordModal(${a.id}, '${escapeHtml(a.name)}')" title="Change Password">🔑 Password</button>
                        <button type="button" class="admin-action-btn" onclick="toggleAdminStatus(${a.id}, ${a.is_active})" title="${a.is_active ? 'Disable Account' : 'Activate Account'}">
                            ${a.is_active ? '⏸️ Disable' : '▶️ Enable'}
                        </button>
                        <button type="button" class="admin-action-btn delete" onclick="deleteAdminAccount(${a.id}, '${escapeHtml(a.name)}')" title="Delete Account">🗑️ Delete</button>
                    </div>
                `;

            const idCell = isOwner
                ? `<span style="display:inline-block; padding:2px 8px; font-size:11.5px; font-weight:700; color:#5b21b6; background:#f3e8ff; border:1px solid #d8b4fe; border-radius:6px;">👑 Root</span>`
                : `<strong style="font-size:13px; color:#1e293b;">#${a.id}</strong>`;

            return `
                <tr>
                    <td>${idCell}</td>
                    <td style="font-weight:700; color:#1e293b;">${escapeHtml(a.name)}</td>
                    <td><code>${escapeHtml(a.admin_user_id)}</code></td>
                    <td>${roleBadge}</td>
                    <td>${statusBadge}</td>
                    <td style="font-size:12px; color:#64748b;">${a.created_at ? new Date(a.created_at).toLocaleDateString() : "System Root"}</td>
                    <td style="text-align:center;">${actions}</td>
                </tr>
            `;
        }).join("");
    } catch (err) {
        console.error("Admin accounts load error:", err);
        tbody.innerHTML = `<tr><td colspan="7" class="text-danger text-center py-3">Error loading admin accounts: ${err.message}</td></tr>`;
    }
}

// 7. Owner Management: Create New Team Admin (Max 6 limit)
async function handleCreateAdminSubmit(event) {
    if (event) event.preventDefault();
    const btn = document.getElementById("createAdminBtn");
    const originalText = btn ? btn.innerHTML : "🛡️ Create Admin Account";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳ Creating Admin Account...</span>`;
    }

    const payload = {
        name: document.getElementById("newAdminNameInput").value.trim(),
        admin_user_id: document.getElementById("newAdminUserIdInput").value.trim(),
        password: document.getElementById("newAdminPasswordInput").value
    };

    try {
        const res = await authFetch(`${API_BASE}/api/admin/manage/create`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Failed to create admin account.");
        }

        document.getElementById("createAdminForm").reset();
        showToast(`🛡️ Team Admin "${data.name}" created successfully!`, "success");
        loadAdminAccounts();
    } catch (err) {
        console.error("Create admin error:", err);
        showToast(`⚠️ ${err.message}`, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

// 8. Owner Management: Change Admin User ID
function openChangeAdminIdModal(id, currentUserId, name) {
    const modal = document.getElementById("adminChangeIdModal");
    const targetId = document.getElementById("adminTargetDbId");
    const targetName = document.getElementById("adminChangeIdTargetName");
    const input = document.getElementById("adminNewUserIdInput");

    if (targetId) targetId.value = id;
    if (targetName) targetName.textContent = `${name} (${currentUserId})`;
    if (input) input.value = currentUserId;
    if (modal) modal.style.display = "flex";
}

function closeChangeAdminIdModal() {
    const modal = document.getElementById("adminChangeIdModal");
    if (modal) modal.style.display = "none";
}

async function submitChangeAdminId(event) {
    if (event) event.preventDefault();
    const id = document.getElementById("adminTargetDbId").value;
    const newId = document.getElementById("adminNewUserIdInput").value.trim();
    if (!newId) return;

    try {
        const res = await authFetch(`${API_BASE}/api/admin/manage/${id}/user-id`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ new_admin_user_id: newId })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update User ID.");

        closeChangeAdminIdModal();
        showToast(`✏️ Admin User ID updated to "${newId}"`, "success");
        loadAdminAccounts();
    } catch (err) {
        showToast(`⚠️ ${err.message}`, "error");
    }
}

// 9. Owner Management: Change Admin Password
function openChangeAdminPasswordModal(id, name) {
    const modal = document.getElementById("adminChangePasswordModal");
    const targetId = document.getElementById("adminPasswordTargetDbId");
    const targetName = document.getElementById("adminChangePasswordTargetName");
    const inputNew = document.getElementById("adminNewPasswordInput");
    const inputConfirm = document.getElementById("adminConfirmPasswordInput");

    if (targetId) targetId.value = id;
    if (targetName) targetName.textContent = name;
    if (inputNew) inputNew.value = "";
    if (inputConfirm) inputConfirm.value = "";
    if (modal) modal.style.display = "flex";
}

function closeChangeAdminPasswordModal() {
    const modal = document.getElementById("adminChangePasswordModal");
    if (modal) modal.style.display = "none";
}

async function submitChangeAdminPassword(event) {
    if (event) event.preventDefault();
    const id = document.getElementById("adminPasswordTargetDbId").value;
    const p1 = document.getElementById("adminNewPasswordInput").value;
    const p2 = document.getElementById("adminConfirmPasswordInput").value;

    if (p1.length < 6) {
        showToast("⚠️ Password must be at least 6 characters long.", "warning");
        return;
    }
    if (p1 !== p2) {
        showToast("⚠️ Passwords do not match.", "warning");
        return;
    }

    try {
        const res = await authFetch(`${API_BASE}/api/admin/manage/${id}/password`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ new_password: p1 })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update password.");

        closeChangeAdminPasswordModal();
        showToast("🔑 Admin password updated successfully!", "success");
    } catch (err) {
        showToast(`⚠️ ${err.message}`, "error");
    }
}

// 10. Owner Management: Toggle Admin Status (Enable / Disable)
async function toggleAdminStatus(id, currentStatus) {
    const newStatus = !currentStatus;
    try {
        const res = await authFetch(`${API_BASE}/api/admin/manage/${id}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_active: newStatus })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update status.");

        showToast(`Admin account ${newStatus ? 'enabled' : 'disabled'}.`, "info");
        loadAdminAccounts();
    } catch (err) {
        showToast(`⚠️ ${err.message}`, "error");
    }
}

// 11. Owner Management: Delete Admin Account
async function deleteAdminAccount(id, name) {
    if (!confirm(`Are you sure you want to permanently delete admin account "${name}"?`)) {
        return;
    }

    try {
        const res = await authFetch(`${API_BASE}/api/admin/manage/${id}/delete`, {
            method: "DELETE"
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to delete admin account.");

        showToast(`🗑️ Admin account "${name}" deleted.`, "info");
        loadAdminAccounts();
    } catch (err) {
        showToast(`⚠️ ${err.message}`, "error");
    }
}

// 12. Owner Management: Reset Demo Database
function openResetDemoModal() {
    const modal = document.getElementById("adminResetDemoModal");
    const checkbox = document.getElementById("resetDemoConfirmCheckbox");
    if (checkbox) checkbox.checked = false;
    if (modal) modal.style.display = "flex";
}

function closeResetDemoModal() {
    const modal = document.getElementById("adminResetDemoModal");
    if (modal) modal.style.display = "none";
}

async function submitResetDemoDatabase() {
    const checkbox = document.getElementById("resetDemoConfirmCheckbox");
    if (!checkbox || !checkbox.checked) {
        showToast("⚠️ Please check the confirmation box before resetting.", "warning");
        return;
    }

    const btn = document.getElementById("confirmResetDemoBtn");
    const originalText = btn ? btn.innerHTML : "🧹 Confirm & Reset";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳ Resetting Database...</span>`;
    }

    try {
        const res = await authFetch(`${API_BASE}/api/admin/reset-demo-data`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ confirm: true })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to reset demo database.");

        closeResetDemoModal();
        showToast("🧹 All platform data wiped! Database is clean with 0 synthetic users.", "success");

        // Reload products and refresh admin data
        await loadProducts();
        refreshCurrentAdminTab();
    } catch (err) {
        console.error("Demo reset error:", err);
        showToast(`⚠️ ${err.message}`, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

// 12b. Super Admin: Change Super Admin Credentials
function openSuperAdminCredsModal() {
    const modal = document.getElementById("superAdminChangeCredsModal");
    const idInput = document.getElementById("superAdminNewUserIdInput");
    const pwdInput = document.getElementById("superAdminNewPasswordInput");
    const confInput = document.getElementById("superAdminConfirmPasswordInput");

    if (idInput) {
        idInput.value = state.currentUser ? (state.currentUser.user_id || "Sm_0629") : "Sm_0629";
    }
    if (pwdInput) pwdInput.value = "";
    if (confInput) confInput.value = "";
    if (modal) modal.style.display = "flex";
}

function closeSuperAdminCredsModal() {
    const modal = document.getElementById("superAdminChangeCredsModal");
    if (modal) modal.style.display = "none";
}

async function submitSuperAdminCreds(event) {
    if (event) event.preventDefault();
    const newId = document.getElementById("superAdminNewUserIdInput").value.trim();
    const newPwd = document.getElementById("superAdminNewPasswordInput").value;
    const confPwd = document.getElementById("superAdminConfirmPasswordInput").value;

    if (!newId && !newPwd) {
        showToast("Please enter a new User ID or Password.", "warning");
        return;
    }

    if (newPwd && newPwd.length < 4) {
        showToast("Password must be at least 4 characters long.", "warning");
        return;
    }

    if (newPwd && newPwd !== confPwd) {
        showToast("Passwords do not match!", "error");
        return;
    }

    const saveBtn = document.getElementById("saveSuperAdminCredsBtn");
    const origText = saveBtn ? saveBtn.innerHTML : "💾 Save Credentials";
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = `<span>⏳ Saving...</span>`;
    }

    try {
        const payload = {};
        if (newId) payload.new_admin_user_id = newId;
        if (newPwd) payload.new_password = newPwd;

        const res = await authFetch(`${API_BASE}/api/admin/manage/owner/credentials`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update Super Admin credentials.");

        if (state.currentUser && newId) {
            state.currentUser.user_id = newId;
            localStorage.setItem("farmbuy_user", JSON.stringify(state.currentUser));
            const adminUserIdDisplay = document.getElementById("adminUserBadgeId");
            if (adminUserIdDisplay) adminUserIdDisplay.textContent = `ID: ${newId}`;
        }

        closeSuperAdminCredsModal();
        showToast("👑 Super Admin credentials successfully updated!", "success");
        loadAdminAccounts();
    } catch (err) {
        console.error("Super admin update error:", err);
        showToast(`⚠️ ${err.message}`, "error");
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = origText;
        }
    }
}

// Helper: HTML escape for safe table rendering
function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Fetch Farmer's Listed Produce, KPIs & Stock Clearance from Database
async function loadFarmerProduceList() {
    if (!state.currentUser || state.currentUser.role !== "farmer") return;
    const tableBody = document.getElementById("farmerProduceListBody");
    const kpiHarvest = document.getElementById("farmerKpiHarvest");
    const kpiOrdered = document.getElementById("farmerKpiOrdered") || document.getElementById("farmerKpiCleared");
    const kpiClearancePct = document.getElementById("farmerKpiClearancePct");
    const kpiLeft = document.getElementById("farmerKpiLeft");
    const kpiRevenue = document.getElementById("farmerKpiRevenue");
    const kpiRemainingVal = document.getElementById("farmerKpiRemainingVal");
    const cropFilter = document.getElementById("farmerOrderCropFilter");
    const mandiContainer = document.getElementById("farmerMandiRatesContainer");

    try {
        const res = await fetch(`${API_BASE}/api/auth/farmer/${state.currentUser.id}/supplies`);
        if (res.status === 404) {
            handleLogout();
            return;
        }
        if (!res.ok) return;
        const data = await res.json();

        // 1. Update 4 Farmer KPI Cards
        if (data.kpis) {
            const totOrdered = data.kpis.total_ordered_kg ?? data.kpis.total_cleared_kg ?? 0;
            const totLeft = data.kpis.total_left_kg ?? 0;
            const orderRev = data.kpis.earned_from_orders ?? data.kpis.total_ordered_revenue ?? data.kpis.total_cleared_revenue ?? 0;
            const stockVal = data.kpis.current_stock_value ?? data.kpis.total_remaining_value ?? 0;

            if (kpiHarvest) kpiHarvest.textContent = `${Number(data.kpis.total_harvest_kg).toLocaleString()} kg`;
            if (kpiOrdered) kpiOrdered.textContent = `${Number(totOrdered).toLocaleString()} kg`;
            if (kpiClearancePct) kpiClearancePct.textContent = `${orderPct}% Ordered`;
            if (kpiLeft) kpiLeft.textContent = `${Number(totLeft).toLocaleString()} kg`;
            if (kpiRevenue) kpiRevenue.textContent = `₹${Number(orderRev).toLocaleString()}`;
            if (kpiRemainingVal) kpiRemainingVal.textContent = `₹${Number(stockVal).toLocaleString()}`;
        }

        // 2. Populate Farmer Crop Filter Dropdown for Orders
        if (cropFilter && data.supplies) {
            const currentVal = cropFilter.value;
            cropFilter.innerHTML = `<option value="">🌾 All Commodities</option>` +
                data.supplies.map(s => `
                    <option value="${s.product_id}">
                        ${s.product_name} (${Number(s.quantity_ordered_kg || 0).toLocaleString()} kg ordered)
                    </option>
                `).join("");
            if (currentVal) {
                cropFilter.value = currentVal;
            }
        }

        // 2B. Populate Farmer Forecast Crop Dropdown & Load Demand Prediction
        const forecastCropSelect = document.getElementById("farmerForecastCropSelect");
        if (forecastCropSelect) {
            const currentSelected = forecastCropSelect.value;
            let optionsHtml = "";
            if (data.supplies && data.supplies.length > 0) {
                optionsHtml = data.supplies.map(s => `<option value="${s.product_id}">🌾 ${s.product_name}</option>`).join("");
            } else if (state.products && state.products.length > 0) {
                optionsHtml = state.products.map(p => `<option value="${p.id}">🌾 ${p.name}</option>`).join("");
            } else {
                optionsHtml = `<option value="1">🌾 Tomato</option><option value="2">🌾 Potato</option><option value="3">🌾 Onion</option>`;
            }
            forecastCropSelect.innerHTML = optionsHtml;
            if (currentSelected && forecastCropSelect.querySelector(`option[value="${currentSelected}"]`)) {
                forecastCropSelect.value = currentSelected;
            }
            loadFarmerDemandForecast();
        }

        // 3. Render Commodities & Stock Table
        if (tableBody) {
            if (!data.supplies || data.supplies.length === 0) {
                tableBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No active produce listed yet. Use the form below to list your commodities.</td></tr>`;
            } else {
                tableBody.innerHTML = data.supplies.map(s => {
                    const ordKg = s.quantity_ordered_kg ?? s.stock_cleared_kg ?? 0;
                    const leftKg = s.quantity_left_kg ?? s.stock_left_kg ?? 0;
                    const totKg = s.total_harvest_kg || (leftKg + ordKg);
                    const pctOrdered = Math.min(100, Math.max(0, s.ordered_pct ?? s.clearance_pct ?? 0));
                    const pctLeft = Math.max(0, 100 - pctOrdered);
                    
                    let diffBadge = "";
                    if (s.price_diff > 0) {
                        diffBadge = `<span class="mandi-diff-tag above">+₹${s.price_diff.toFixed(2)} vs Mandi</span>`;
                    } else if (s.price_diff < 0) {
                        diffBadge = `<span class="mandi-diff-tag below">-₹${Math.abs(s.price_diff).toFixed(2)} vs Mandi</span>`;
                    } else {
                        diffBadge = `<span class="mandi-diff-tag equal">At Mandi Parity</span>`;
                    }

                    return `
                        <tr>
                            <td>
                                <strong>${s.product_name}</strong> 
                                <span class="badge" style="background:#f1f5f9; color:#475569; font-size:11px; margin-left:4px;">${s.quality_grade}</span>
                            </td>
                            <td><strong>₹${Number(s.expected_price).toFixed(2)}</strong>/kg</td>
                            <td>
                                <span>₹${Number(s.mandi_benchmark).toFixed(2)}/kg</span>
                                ${diffBadge}
                            </td>
                            <td><strong style="color:#16a34a; font-size:14px;">${Number(leftKg).toLocaleString()}</strong> kg</td>
                            <td>
                                <strong style="color:#2563eb; font-size:14px;">${Number(ordKg).toLocaleString()}</strong> kg
                                ${(s.ordered_revenue || s.cleared_revenue) > 0 ? `<div style="font-size:11.5px; color:#15803d; font-weight:700; margin-top:2px;">Earned: ₹${Number(s.ordered_revenue || s.cleared_revenue).toLocaleString()}</div>` : ''}
                            </td>
                            <td>
                                <div class="stock-progress-wrap">
                                    <div class="stock-progress-bar">
                                        <div class="stock-fill-cleared" style="width: ${pctOrdered}%;" title="${pctOrdered}% Ordered"></div>
                                        <div class="stock-fill-left" style="width: ${pctLeft}%;" title="${pctLeft}% Left"></div>
                                    </div>
                                    <div class="stock-progress-text">
                                        <span style="color:#2563eb; font-weight:600;">${pctOrdered}% Ordered</span>
                                        <span style="color:#16a34a; font-weight:600;">${Number(leftKg).toLocaleString()} kg left</span>
                                    </div>
                                </div>
                            </td>
                            <td>
                                <strong class="text-success" style="font-size:14px;">₹${Number(s.remaining_value).toLocaleString()}</strong>
                                <div style="font-size:11px; color:#64748b;">${Number(leftKg).toLocaleString()} kg unsold</div>
                            </td>
                            <td>
                                <div style="display:flex; gap:6px; align-items:center;">
                                    <button type="button" class="btn-sm" style="padding:5px 10px; font-size:12px; background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; border-radius:4px; font-weight:600; cursor:pointer;" onclick="openEditProduceModal(${s.supply_id}, '${s.product_name}', ${leftKg}, ${s.expected_price}, '${s.quality_grade}')">
                                        ✏️ Edit
                                    </button>
                                    <button type="button" class="btn-primary" style="padding:5px 12px; font-size:12px; background:#2563eb; display:inline-flex; align-items:center; gap:5px;" onclick="selectCropAndShowOrders(${s.product_id}, '${s.product_name}')">
                                        🔍 View Orders
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join("");
            }
        }

        // 4. Render Mandi Guidance Cards
        if (mandiContainer && data.supplies) {
            mandiContainer.innerHTML = data.supplies.map(s => {
                const leftKg = s.quantity_left_kg ?? s.stock_left_kg ?? 0;
                const ordKg = s.quantity_ordered_kg ?? s.stock_cleared_kg ?? 0;
                return `
                <div class="farmer-mandi-card">
                    <h4>${s.product_name}</h4>
                    <div class="rate-row">
                        <span style="color:#64748b;">Mandi Benchmark</span>
                        <strong>₹${Number(s.mandi_benchmark).toFixed(2)}/kg</strong>
                    </div>
                    <div class="rate-row">
                        <span style="color:#64748b;">Your Asking Rate</span>
                        <strong style="color:${s.price_diff > 0 ? '#b91c1c' : '#15803d'};">₹${Number(s.expected_price).toFixed(2)}/kg</strong>
                    </div>
                    <div class="rate-row" style="font-size:11.5px;">
                        <span style="color:#64748b;">Quantity Left / Ordered</span>
                        <strong><span style="color:#16a34a;">${Number(leftKg).toLocaleString()} kg left</span> • <span style="color:#2563eb;">${Number(ordKg).toLocaleString()} kg ord.</span></strong>
                    </div>
                </div>
            `}).join("");
        }

        // 5. Load and Render Incoming Buyer Orders
        const activeProdFilter = cropFilter && cropFilter.value ? parseInt(cropFilter.value) : null;
        await loadFarmerOrders(activeProdFilter);

    } catch (err) {
        console.error("Error loading farmer produce list:", err);
    }
}

// Load and Render Incoming Buyer Orders for Farmer
async function loadFarmerOrders(productId = null) {
    if (!state.currentUser || state.currentUser.role !== "farmer") return;
    const container = document.getElementById("farmerOrdersListContainer");
    if (!container) return;

    try {
        const url = `${API_BASE}/api/auth/farmer/${state.currentUser.id}/orders${productId ? `?product_id=${productId}` : ""}`;
        const res = await fetch(url);
        if (!res.ok) {
            container.innerHTML = `<div class="text-center text-muted py-4">Unable to load buyer orders.</div>`;
            return;
        }
        const data = await res.json();
        const orders = data.orders || [];

        if (orders.length === 0) {
            const cropFilter = document.getElementById("farmerOrderCropFilter");
            const selectedCropText = cropFilter && cropFilter.selectedIndex > 0 ? cropFilter.options[cropFilter.selectedIndex].text.split("(")[0].trim() : "your crops";
            container.innerHTML = `
                <div class="farmer-orders-empty">
                    <div style="font-size:32px; margin-bottom:8px;">📦</div>
                    <h4>No Incoming Orders Yet for ${selectedCropText}</h4>
                    <p>When verified buyers (wholesalers, institutions, or retail networks) procure this crop through FarmBuy AI, their order details, contact info, and pickup quantities will appear here.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="farmer-orders-grid">
                ${orders.map(o => `
                    <div class="farmer-order-card">
                        <div class="order-card-header">
                            <div>
                                <div class="order-buyer-name">
                                    <span>🏢</span>
                                    <span>${o.buyer_name}</span>
                                </div>
                                <div class="order-buyer-contact">
                                    <span>📞 <a href="tel:${o.buyer_phone}">${o.buyer_phone}</a></span>
                                    <span>•</span>
                                    <span>📍 ${o.buyer_city}</span>
                                </div>
                            </div>
                            <span class="badge badge-verified" style="font-size:11px;">${o.status || 'CONFIRMED'}</span>
                        </div>

                        <div class="order-card-details">
                            <div class="order-card-row">
                                <span class="order-card-label">Commodity</span>
                                <span class="order-card-value">${o.product_name}</span>
                            </div>
                            <div class="order-card-row">
                                <span class="order-card-label">Quantity Taking</span>
                                <span class="order-card-value" style="color:#2563eb; font-size:14.5px;">${Number(o.allocated_quantity_kg).toLocaleString()} kg</span>
                            </div>
                            <div class="order-card-row">
                                <span class="order-card-label">Agreed Rate</span>
                                <span class="order-card-value">₹${Number(o.price_per_kg).toFixed(2)}/kg</span>
                            </div>
                            <div class="order-card-row">
                                <span class="order-card-label">Order Payout</span>
                                <span class="order-card-value" style="color:#16a34a; font-size:14.5px;">₹${Number(o.subtotal).toLocaleString()}</span>
                            </div>
                        </div>

                        <div class="order-card-footer">
                            <div style="font-size:11.5px; color:#64748b;">
                                <span>#${o.order_number}</span> • <span>${o.created_at}</span>
                            </div>
                            <button type="button" class="btn-delete-order" onclick="deleteFarmerOrder(${o.order_item_id}, '${o.product_name}', ${o.allocated_quantity_kg})">
                                🗑️ Remove from History
                            </button>
                        </div>
                    </div>
                `).join("")}
            </div>
        `;

    } catch (err) {
        console.error("Error loading farmer orders:", err);
        container.innerHTML = `<div class="text-center text-danger py-4">Error loading orders.</div>`;
    }
}

// React when crop filter changes in the Orders panel
function onFarmerOrderCropFilterChange() {
    const filterEl = document.getElementById("farmerOrderCropFilter");
    const prodId = filterEl && filterEl.value ? parseInt(filterEl.value) : null;
    loadFarmerOrders(prodId);
}

// Select a crop and immediately view its buyer orders
function selectCropAndShowOrders(productId, productName) {
    const filterEl = document.getElementById("farmerOrderCropFilter");
    if (filterEl) {
        filterEl.value = productId;
    }
    loadFarmerOrders(productId);
    scrollToFarmerSection("farmerOrdersSection");
    showToast(`🔍 Showing orders for ${productName}`, "info");
}

// Delete an individual order item from farmer's history
async function deleteFarmerOrder(orderItemId, cropName, qtyKg) {
    if (!state.currentUser || state.currentUser.role !== "farmer") return;
    if (!confirm(`Are you sure you want to remove this order of ${qtyKg} kg ${cropName} from your history?`)) {
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/auth/farmer/${state.currentUser.id}/orders/${orderItemId}`, {
            method: "DELETE"
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to remove order.");

        showToast(`🗑️ ${data.message}`, "success");
        await loadFarmerProduceList();
    } catch (err) {
        console.error("Error deleting order:", err);
        showToast(`⚠️ ${err.message}`, "error");
    }
}

// Clear all order history (or for selected crop)
async function clearFarmerOrderHistory() {
    if (!state.currentUser || state.currentUser.role !== "farmer") return;
    const filterEl = document.getElementById("farmerOrderCropFilter");
    const prodId = filterEl && filterEl.value ? parseInt(filterEl.value) : null;
    const cropName = prodId && filterEl.selectedIndex > 0 ? filterEl.options[filterEl.selectedIndex].text.split("(")[0].trim() : "all crops";

    if (!confirm(`Are you sure you want to clear order history for ${cropName}?`)) {
        return;
    }

    try {
        const url = `${API_BASE}/api/auth/farmer/${state.currentUser.id}/orders${prodId ? `?product_id=${prodId}` : ""}`;
        const res = await fetch(url, { method: "DELETE" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to clear history.");

        showToast(`🧹 ${data.message}`, "success");
        await loadFarmerProduceList();
    } catch (err) {
        console.error("Error clearing order history:", err);
        showToast(`⚠️ ${err.message}`, "error");
    }
}

// Save Additional Crop to Farmer's Catalog in Database
async function handleInlineAddSupply(event) {
    if (event) event.preventDefault();
    if (!state.currentUser || state.currentUser.role !== "farmer") return;

    const cropInput = document.getElementById("inlineCropName");
    const qtyInput = document.getElementById("inlineCropQty");
    const priceInput = document.getElementById("inlineCropPrice");
    const gradeInput = document.getElementById("inlineCropGrade");
    const btn = document.getElementById("inlineSaveCropBtn");

    const originalText = btn ? btn.innerHTML : "🌾 Save Crop to Database";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳ Saving Crop...</span>`;
    }

    const payload = {
        farmer_id: state.currentUser.id,
        commodity: cropInput.value.trim(),
        quantity_kg: parseFloat(qtyInput.value),
        price_per_kg: parseFloat(priceInput.value),
        quality_grade: gradeInput ? gradeInput.value : "Grade A"
    };

    try {
        const res = await fetch(`${API_BASE}/api/auth/farmer/add-supply`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Could not add supply");

        showToast(`✅ ${data.message}`, "success");
        cropInput.value = "";
        qtyInput.value = "";
        priceInput.value = "";

        await loadFarmerProduceList();
        await loadProducts();
    } catch (err) {
        showToast(`⚠️ ${err.message}`, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

// Open Edit Produce Modal for Farmer
function openEditProduceModal(supplyId, cropName, quantity, price, grade) {
    const modal = document.getElementById("farmerEditProduceModal");
    if (!modal) return;
    document.getElementById("editSupplyId").value = supplyId;
    document.getElementById("editCommodityInput").value = cropName || "";
    document.getElementById("editQuantityInput").value = quantity || "";
    document.getElementById("editPriceInput").value = price || "";
    const gradeSelect = document.getElementById("editGradeSelect");
    if (gradeSelect) gradeSelect.value = grade || "Grade A";
    modal.style.display = "flex";
}

// Close Edit Produce Modal
function closeEditProduceModal() {
    const modal = document.getElementById("farmerEditProduceModal");
    if (modal) modal.style.display = "none";
}

// Submit Farmer Produce Update to Backend
async function submitFarmerProduceUpdate(event) {
    if (event) event.preventDefault();
    if (!state.currentUser || state.currentUser.role !== "farmer") return;

    const supplyId = parseInt(document.getElementById("editSupplyId").value, 10);
    const commodity = document.getElementById("editCommodityInput").value.trim();
    const quantity = parseFloat(document.getElementById("editQuantityInput").value);
    const price = parseFloat(document.getElementById("editPriceInput").value);
    const grade = document.getElementById("editGradeSelect").value;

    if (!commodity || quantity <= 0 || price <= 0) {
        showToast("⚠️ Please enter valid commodity name, quantity, and price.", "error");
        return;
    }

    const btn = document.getElementById("saveEditProduceBtn");
    const originalText = btn ? btn.innerHTML : "💾 Save Changes";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳ Saving...</span>`;
    }

    try {
        const res = await fetch(`${API_BASE}/api/auth/farmer/supply/${supplyId}/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                farmer_id: state.currentUser.id,
                supply_id: supplyId,
                commodity: commodity,
                quantity_kg: quantity,
                price_per_kg: price,
                quality_grade: grade
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update commodity");

        showToast(`✅ ${data.message || "Produce updated successfully!"}`, "success");
        closeEditProduceModal();
        await loadFarmerProduceList();
        await loadProducts();
    } catch (err) {
        console.error("Error updating produce:", err);
        showToast(`⚠️ ${err.message || "Failed to update produce"}`, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

function showToast(msg, type = "info") {
    let toast = document.getElementById("agriToast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "agriToast";
        toast.className = "agri-toast";
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.className = `agri-toast show ${type}`;
    setTimeout(() => {
        toast.className = "agri-toast";
    }, 4500);
}

// 1. Health Check
async function checkBackendStatus() {
    const statusText = document.getElementById("statusText");
    const statusPulse = document.querySelector(".status-pulse");
    try {
        const res = await fetch(`${API_BASE}/health`);
        const data = await res.json();
        if (data.status === "healthy") {
            state.databaseInfo = data.database;
            const storageBadge = data.database?.is_persistent ? "🟢 PostgreSQL (Persistent)" : "💾 Local Database";
            if (statusText) statusText.textContent = `Backend Connected (v${data.version || "2.0"}) • ${storageBadge}`;
            if (statusPulse) statusPulse.style.background = "#22c55e";
        }
    } catch (err) {
        console.warn("Backend not yet reachable:", err);
        if (statusText) statusText.textContent = "Backend Offline";
        if (statusPulse) statusPulse.style.background = "#ef4444";
    }
}

// 2. Load Products dynamically
async function loadProducts() {
    try {
        const res = await fetch(`${API_BASE}/api/products`, {
            cache: "no-store",
            headers: { "Cache-Control": "no-cache", "Pragma": "no-cache" }
        });
        const products = await res.json();
        state.products = products;
        const select = document.getElementById("productSelect");
        if (products.length > 0 && select) {
            const prevVal = select.value;
            select.innerHTML = products.map(p => 
                `<option value="${p.id}">${p.name} (Mandi: ₹${p.mandi_benchmark_price}/kg)</option>`
            ).join("");
            if (prevVal && products.some(p => p.id == prevVal)) {
                select.value = prevVal;
            }
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

    if (tabId === "dashboard") {
        applyNegotiatedPriceUI();
    }

    if (tabId === "pricing") {
        const prodSelect = document.getElementById("productSelect");
        if (prodSelect) {
            const pId = parseInt(prodSelect.value, 10);
            const negInfo = (state.negotiatedPrices && state.negotiatedPrices[pId]) ? state.negotiatedPrices[pId] : null;
            const actionCard = document.getElementById("negAgreedActionCard");
            if (negInfo && actionCard) {
                actionCard.style.display = "block";
                const priceEl = document.getElementById("negAgreedPriceDisplay");
                const savEl = document.getElementById("negAgreedSavingsDisplay");
                if (priceEl) priceEl.textContent = `₹${negInfo.negotiatedPrice.toFixed(2)}`;
                if (savEl) {
                    savEl.textContent = negInfo.savingsPerKg > 0 
                        ? `Saved ₹${negInfo.savingsPerKg.toFixed(2)}/kg vs Asking Rate (Total Savings: ₹${negInfo.totalSavings.toLocaleString()})`
                        : `Fair market rate agreed with farmers (₹${negInfo.negotiatedPrice.toFixed(2)}/kg)`;
                }
            }
        }
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
        applyNegotiatedPriceUI();
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
        applyNegotiatedPriceUI();
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

    const productId = matching.product_id;
    const negInfo = (state.negotiatedPrices && state.negotiatedPrices[productId]) ? state.negotiatedPrices[productId] : null;

    if (negInfo) {
        document.getElementById("kpiPrice").innerHTML = `₹${negInfo.negotiatedPrice.toFixed(2)} <span style="font-size:12px; font-weight:700; color:#16a34a;">🤝 (Negotiated)</span>`;
        document.getElementById("kpiMandiBenchmark").innerHTML = `<span style="color:#16a34a; font-weight:600;">Negotiated Rate Active</span> (Ask: ₹${matching.blended_price_per_kg.toFixed(2)})`;
    } else {
        document.getElementById("kpiPrice").textContent = `₹${matching.blended_price_per_kg.toFixed(2)} / kg`;
        document.getElementById("kpiMandiBenchmark").textContent = `Govt Mandi: ₹${priceInsight.mandi_benchmark_price.toFixed(2)}`;
    }

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

    const productId = matching.product_id;
    const negInfo = (state.negotiatedPrices && state.negotiatedPrices[productId]) ? state.negotiatedPrices[productId] : null;

    let aggregateTotalCost = 0;
    tbody.innerHTML = matching.farmers.map(f => {
        const hasCustomRate = state.farmerNegotiatedPrices && state.farmerNegotiatedPrices[f.farmer_id] !== undefined;
        const unitRate = hasCustomRate 
            ? Number(state.farmerNegotiatedPrices[f.farmer_id]) 
            : (negInfo ? Number(negInfo.negotiatedPrice) : Number(f.expected_price));
        const subtotal = Math.round(f.matched_quantity * unitRate * 100) / 100;
        aggregateTotalCost += subtotal;

        const isNeg = hasCustomRate || Boolean(negInfo);

        return `
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
                <td>
                    <div style="display:flex; align-items:center; gap:4px;">
                        <span style="font-weight:600; color:#334155; font-size:13px;">₹</span>
                        <input type="number" step="0.1" min="0" 
                            value="${unitRate.toFixed(2)}" 
                            id="farmerRateInput_${f.farmer_id}" 
                            class="farmer-rate-input"
                            title="Individual agreed rate for ${f.farmer_name}. You can edit manually."
                            style="width:72px; padding:3px 5px; font-weight:700; border:1px solid #cbd5e1; border-radius:4px; font-size:12.5px; text-align:right;" 
                            onchange="onIndividualFarmerRateChange(${f.farmer_id}, this.value)" />
                        <span class="text-muted" style="font-size:11px;">/kg</span>
                        ${isNeg ? `<span class="badge badge-success" style="font-size:9.5px; padding:2px 5px; margin-left:2px;">Agreed</span>` : ''}
                    </div>
                </td>
                <td>${f.distance_km} km</td>
                <td id="farmerSubtotal_${f.farmer_id}"><strong>₹${subtotal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</strong></td>
            </tr>
        `;
    }).join("");

    aggregateTotalCost = Math.round(aggregateTotalCost * 100) / 100;
    document.getElementById("summaryTotalCost").textContent = `₹${aggregateTotalCost.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
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
    if (trendBadge) {
        trendBadge.textContent = forecast.trend_direction;
        if (forecast.growth_percentage > 5) {
            trendBadge.className = "badge badge-danger";
        } else if (forecast.growth_percentage < -5) {
            trendBadge.className = "badge badge-warning";
        } else {
            trendBadge.className = "badge badge-success";
        }
    }

    const insightsList = document.getElementById("forecastInsightsList");
    if (insightsList) {
        insightsList.innerHTML = forecast.insights.map(item => `<li>${item}</li>`).join("");
    }

    // Update Buyer Supply Hub Quick Forecast Card
    const quickCropName = document.getElementById("buyerQuickCropName");
    if (quickCropName) {
        quickCropName.textContent = forecast.product_name || "Selected Crop";
    }
    const totDemand = Math.round(forecast.forecast.reduce((acc, f) => acc + f.predicted_demand_kg, 0));
    const quickDemand = document.getElementById("buyerQuick7DayDemand");
    if (quickDemand) {
        quickDemand.textContent = `${totDemand.toLocaleString()} kg`;
    }
    const quickGrowth = document.getElementById("buyerQuickGrowth");
    if (quickGrowth) {
        const sign = forecast.growth_percentage > 0 ? "+" : "";
        quickGrowth.textContent = `${sign}${forecast.growth_percentage.toFixed(1)}%`;
        quickGrowth.style.color = forecast.growth_percentage >= 0 ? "#15803d" : "#dc2626";
    }
    const quickBadge = document.getElementById("buyerQuickTrendBadge");
    if (quickBadge) {
        quickBadge.textContent = forecast.trend_direction;
        if (forecast.growth_percentage > 5) {
            quickBadge.className = "badge badge-success";
        } else if (forecast.growth_percentage < -5) {
            quickBadge.className = "badge badge-danger";
        } else {
            quickBadge.className = "badge badge-warning";
        }
    }
}

// 8B. Fetch and Render ML Demand Forecast for Farmer Dashboard
async function loadFarmerDemandForecast() {
    const cropSelect = document.getElementById("farmerForecastCropSelect");
    if (!cropSelect) return;

    let productId = parseInt(cropSelect.value, 10);
    if (!productId || isNaN(productId)) {
        if (state.products && state.products.length > 0) {
            productId = state.products[0].id;
        } else {
            productId = 1;
        }
    }

    try {
        const res = await fetch(`${API_BASE}/api/demand/forecast`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                product_id: productId,
                days_ahead: 7,
                region: (state.currentUser && state.currentUser.location) ? state.currentUser.location : "Kolkata Metro Hub"
            })
        });

        if (!res.ok) {
            console.warn("Farmer demand forecast fetch failed:", res.status);
            return;
        }

        const forecast = await res.json();
        state.currentFarmerForecast = forecast;
        renderFarmerForecastChart(forecast);
    } catch (err) {
        console.error("Error loading farmer demand forecast:", err);
    }
}

function onFarmerForecastCropChange() {
    loadFarmerDemandForecast();
}

function renderFarmerForecastChart(forecast) {
    if (!forecast) return;
    state.currentFarmerForecast = forecast;

    const totDemandFarmer = Math.round((forecast.forecast || []).reduce((acc, f) => acc + f.predicted_demand_kg, 0));
    const dailyAvgFarmer = Math.round(totDemandFarmer / ((forecast.forecast && forecast.forecast.length) || 7));
    const growth = Number(forecast.growth_percentage || 0);
    const cropName = forecast.product_name || "Commodity";

    // 1. Update Traffic-Light Status Banner and Trend Indicators
    const bannerEl = document.getElementById("farmerDemandSignalBanner");
    const iconEl = document.getElementById("farmerDemandSignalIcon");
    const titleEl = document.getElementById("farmerDemandSignalTitle");
    const subEl = document.getElementById("farmerDemandSignalSub");
    const trendBadge = document.getElementById("farmerTrendBadge");
    const simpleTrendEl = document.getElementById("farmerForecastSimpleTrend");

    if (growth > 2.0) {
        // High Demand
        if (bannerEl) {
            bannerEl.style.background = "#f0fdf4";
            bannerEl.style.borderColor = "#86efac";
        }
        if (iconEl) {
            iconEl.style.background = "#dcfce7";
            iconEl.textContent = "🟢";
        }
        if (titleEl) {
            titleEl.style.color = "#14532d";
            titleEl.textContent = "🟢 HIGH DEMAND (बड़ी मांग)";
        }
        if (subEl) {
            subEl.style.color = "#166534";
            subEl.textContent = `Buyers are actively purchasing ${cropName} this week • बेचने का सही समय है!`;
        }
        if (trendBadge) {
            trendBadge.className = "badge badge-success";
            trendBadge.textContent = "📈 Increase in Demand";
        }
        if (simpleTrendEl) {
            simpleTrendEl.style.color = "#047857";
            simpleTrendEl.textContent = "Demand is Increasing (मांग बढ़ रही है)";
        }
    } else if (growth < -2.0) {
        // Decreasing / Slow Demand
        if (bannerEl) {
            bannerEl.style.background = "#fef2f2";
            bannerEl.style.borderColor = "#fca5a5";
        }
        if (iconEl) {
            iconEl.style.background = "#fee2e2";
            iconEl.textContent = "🔴";
        }
        if (titleEl) {
            titleEl.style.color = "#991b1b";
            titleEl.textContent = "🔴 SLOWING DEMAND (मांग कम है)";
        }
        if (subEl) {
            subEl.style.color = "#b91c1c";
            subEl.textContent = `Buyer inquiries for ${cropName} are slower this week • जल्दी स्टॉक निकालें`;
        }
        if (trendBadge) {
            trendBadge.className = "badge badge-danger";
            trendBadge.textContent = "📉 Decreasing Demand";
        }
        if (simpleTrendEl) {
            simpleTrendEl.style.color = "#b91c1c";
            simpleTrendEl.textContent = "Demand is Softening (मांग कम हो रही है)";
        }
    } else {
        // Steady / Normal Demand
        if (bannerEl) {
            bannerEl.style.background = "#fefce8";
            bannerEl.style.borderColor = "#fde047";
        }
        if (iconEl) {
            iconEl.style.background = "#fef9c3";
            iconEl.textContent = "🟡";
        }
        if (titleEl) {
            titleEl.style.color = "#854d0e";
            titleEl.textContent = "🟡 STEADY DEMAND (मांग स्थिर है)";
        }
        if (subEl) {
            subEl.style.color = "#a16207";
            subEl.textContent = `Steady buyer consumption this week • सामान्य बाज़ार भाव`;
        }
        if (trendBadge) {
            trendBadge.className = "badge badge-warning";
            trendBadge.textContent = "⚖️ Steady Demand";
        }
        if (simpleTrendEl) {
            simpleTrendEl.style.color = "#a16207";
            simpleTrendEl.textContent = "Demand is Steady (मांग स्थिर है)";
        }
    }

    // 2. Update KPI Metric Cards
    const totDemandEl = document.getElementById("farmerForecastTotalDemand");
    if (totDemandEl) totDemandEl.textContent = `${totDemandFarmer.toLocaleString()} kg`;

    const dailyAvgEl = document.getElementById("farmerForecastDailyAvg");
    if (dailyAvgEl) dailyAvgEl.textContent = `~${dailyAvgFarmer.toLocaleString()} kg needed every day`;

    const growthEl = document.getElementById("farmerForecastGrowthPct");
    if (growthEl) {
        const sign = growth >= 0 ? "+" : "";
        growthEl.textContent = `${sign}${growth.toFixed(1)}%`;
        growthEl.style.color = growth >= 0 ? "#15803d" : "#dc2626";
    }

    // 3. If technical graph wrapper is currently visible, re-render the chart
    const wrapper = document.getElementById("farmerChartWrapper");
    if (wrapper && wrapper.style.display !== "none") {
        renderFarmerTechnicalChartOnly(forecast);
    }
}

// Optional technical chart renderer (only called when user opens the toggle)
function renderFarmerTechnicalChartOnly(forecast) {
    const ctx = document.getElementById('farmerForecastChart');
    if (!ctx || typeof Chart === "undefined" || !forecast) return;

    if (state.farmerForecastChart) {
        state.farmerForecastChart.destroy();
        state.farmerForecastChart = null;
    }

    const histLabels = (forecast.historical_data || []).map(d => d.date.slice(5));
    const histValues = (forecast.historical_data || []).map(d => d.quantity_demanded);

    const foreLabels = (forecast.forecast || []).map(d => d.date.slice(5));
    const foreValues = (forecast.forecast || []).map(d => d.predicted_demand_kg);
    const upperBounds = (forecast.forecast || []).map(d => d.upper_bound_kg);
    const lowerBounds = (forecast.forecast || []).map(d => d.lower_bound_kg);

    const allLabels = [...histLabels, ...foreLabels];
    const histDataExtended = [...histValues, ...Array(foreLabels.length).fill(null)];
    const foreDataExtended = [
        ...Array(histLabels.length > 0 ? histLabels.length - 1 : 0).fill(null),
        histValues.length > 0 ? histValues[histValues.length - 1] : (foreValues[0] || 0),
        ...foreValues
    ];
    const upperExtended = [
        ...Array(histLabels.length > 0 ? histLabels.length - 1 : 0).fill(null),
        histValues.length > 0 ? histValues[histValues.length - 1] : (upperBounds[0] || 0),
        ...upperBounds
    ];
    const lowerExtended = [
        ...Array(histLabels.length > 0 ? histLabels.length - 1 : 0).fill(null),
        histValues.length > 0 ? histValues[histValues.length - 1] : (lowerBounds[0] || 0),
        ...lowerBounds
    ];

    state.farmerForecastChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: allLabels,
            datasets: [
                {
                    label: 'Historical Mandi Demand (kg/day)',
                    data: histDataExtended,
                    borderColor: '#64748b',
                    backgroundColor: 'rgba(100, 116, 139, 0.1)',
                    borderWidth: 2,
                    pointRadius: 3,
                    tension: 0.3
                },
                {
                    label: 'ML Projected Demand Trajectory (7-Day)',
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
                    label: 'Upper Peak Demand Band (95%)',
                    data: upperExtended,
                    borderColor: 'rgba(34, 197, 94, 0.3)',
                    borderDash: [2, 2],
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: '+1',
                    backgroundColor: 'rgba(34, 197, 94, 0.08)'
                },
                {
                    label: 'Lower Demand Baseline (95%)',
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
            interaction: { mode: 'index', intersect: false },
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
                    labels: { boxWidth: 12, font: { family: 'Inter', size: 12 } }
                }
            },
            scales: {
                y: {
                    title: { display: true, text: 'Buyer Demand Volume (kg)' },
                    grid: { color: '#f1f5f9' }
                },
                x: { grid: { color: '#f8fafc' } }
            }
        }
    });
}

function toggleFarmerTechnicalChart() {
    const wrapper = document.getElementById("farmerChartWrapper");
    const textSpan = document.getElementById("toggleFarmerChartText");
    if (!wrapper) return;

    if (wrapper.style.display === "none" || !wrapper.style.display) {
        wrapper.style.display = "block";
        if (textSpan) textSpan.textContent = "Hide Technical Graph (ग्राफ छिपाएं)";
        if (state.currentFarmerForecast) {
            renderFarmerTechnicalChartOnly(state.currentFarmerForecast);
        }
    } else {
        wrapper.style.display = "none";
        if (textSpan) textSpan.textContent = "Show Technical Graph (तकनीकी ग्राफ देखें)";
    }
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

        // Determine agreed price based on negotiation evaluation
        const origBlended = (state.currentMatching && state.currentMatching.blended_price_per_kg)
            ? state.currentMatching.blended_price_per_kg
            : (neg.average_asking_price || targetPrice);

        let agreedPrice = targetPrice;
        if (neg.farmer_acceptance_likelihood === "HIGH") {
            agreedPrice = neg.target_price;
        } else if (neg.farmer_acceptance_likelihood === "MODERATE") {
            agreedPrice = neg.recommended_counter_offer;
        } else {
            agreedPrice = neg.recommended_counter_offer;
        }

        const savingsPerKg = Math.max(0, origBlended - agreedPrice);
        const totalSavings = Math.round(savingsPerKg * quantity);

        if (!state.negotiatedPrices) state.negotiatedPrices = {};
        state.negotiatedPrices[productId] = {
            negotiatedPrice: agreedPrice,
            targetPrice: neg.target_price,
            counterOffer: neg.recommended_counter_offer,
            likelihood: neg.farmer_acceptance_likelihood,
            originalBlendedPrice: origBlended,
            savingsPerKg: savingsPerKg,
            totalSavings: totalSavings,
            quantity: quantity,
            productName: (state.currentMatching ? state.currentMatching.product_name : "Crop")
        };

        // Populate individual farmer negotiated prices
        if (!state.farmerNegotiatedPrices) state.farmerNegotiatedPrices = {};
        if (neg.farmer_responses && Array.isArray(neg.farmer_responses)) {
            neg.farmer_responses.forEach(r => {
                if (r.farmer_id) {
                    state.farmerNegotiatedPrices[r.farmer_id] = (r.agreed_price !== undefined && r.agreed_price !== null)
                        ? Number(r.agreed_price)
                        : agreedPrice;
                }
            });
        }

        // Render Applied Negotiated Card in Tab 3
        const actionCard = document.getElementById("negAgreedActionCard");
        if (actionCard) {
            actionCard.style.display = "block";
            const priceEl = document.getElementById("negAgreedPriceDisplay");
            const savEl = document.getElementById("negAgreedSavingsDisplay");
            if (priceEl) priceEl.textContent = `₹${agreedPrice.toFixed(2)}`;
            if (savEl) {
                savEl.textContent = savingsPerKg > 0 
                    ? `Saved ₹${savingsPerKg.toFixed(2)}/kg vs Asking Rate (Total Savings: ₹${totalSavings.toLocaleString()})`
                    : `Fair market rate agreed with farmers (₹${agreedPrice.toFixed(2)}/kg)`;
            }
        }

        // Apply immediately to the main dashboard UI
        applyNegotiatedPriceUI();

        showNotification(`🤝 Negotiated rate of ₹${agreedPrice.toFixed(2)}/kg locked! Return to Main Page to place order.`);

    } catch (err) {
        console.error("Error evaluating negotiation:", err);
    }
}

// 10B. Apply Negotiated Price to Main Page UI
function applyNegotiatedPriceUI() {
    const prodSelect = document.getElementById("productSelect");
    if (!prodSelect) return;
    const productId = parseInt(prodSelect.value, 10);
    const banner = document.getElementById("negotiatedAlertBanner");
    const negInfo = (state.negotiatedPrices && state.negotiatedPrices[productId]) ? state.negotiatedPrices[productId] : null;

    if (negInfo) {
        if (banner) {
            banner.style.display = "block";
            const priceEl = document.getElementById("bannerNegotiatedPrice");
            const savingsEl = document.getElementById("bannerSavingsBadge");
            const origEl = document.getElementById("bannerOriginalPrice");
            if (priceEl) priceEl.textContent = negInfo.negotiatedPrice.toFixed(2);
            if (savingsEl) savingsEl.textContent = `Saved ₹${negInfo.savingsPerKg.toFixed(2)}/kg`;
            if (origEl) origEl.textContent = negInfo.originalBlendedPrice.toFixed(2);
        }
    } else {
        if (banner) banner.style.display = "none";
    }

    if (state.currentMatching && state.currentPriceInsight) {
        updateKPIs(state.currentMatching, state.currentPriceInsight, state.currentRoute);
        renderFarmerMatchTable(state.currentMatching);
    }
}

// 10B-2. Handle Manual or Negotiated Rate Adjustment for Individual Farmers
function onIndividualFarmerRateChange(farmerId, newRate) {
    const parsedRate = parseFloat(newRate);
    if (isNaN(parsedRate) || parsedRate < 0) return;
    if (!state.farmerNegotiatedPrices) state.farmerNegotiatedPrices = {};
    state.farmerNegotiatedPrices[farmerId] = parsedRate;

    if (state.currentMatching && state.currentMatching.farmers) {
        let totalProduceCost = 0;
        let totalWeight = 0;
        state.currentMatching.farmers.forEach(f => {
            const r = (state.farmerNegotiatedPrices && state.farmerNegotiatedPrices[f.farmer_id] !== undefined)
                ? Number(state.farmerNegotiatedPrices[f.farmer_id])
                : Number(f.expected_price);
            const sub = Math.round(f.matched_quantity * r * 100) / 100;
            totalProduceCost += sub;
            totalWeight += f.matched_quantity;

            const subEl = document.getElementById(`farmerSubtotal_${f.farmer_id}`);
            if (subEl) {
                subEl.innerHTML = `<strong>₹${sub.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</strong>`;
            }
        });

        totalProduceCost = Math.round(totalProduceCost * 100) / 100;
        const blended = totalWeight > 0 ? (totalProduceCost / totalWeight) : 0;

        const summaryCost = document.getElementById("summaryTotalCost");
        if (summaryCost) {
            summaryCost.textContent = `₹${totalProduceCost.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        }

        const kpiPrice = document.getElementById("kpiPrice");
        if (kpiPrice) {
            kpiPrice.innerHTML = `₹${blended.toFixed(2)} <span style="font-size:12px; font-weight:700; color:#16a34a;">🤝 (Negotiated)</span>`;
        }
    }
}

// 10C. Clear Negotiated Rate and Revert to Original Asking Price
function clearNegotiatedPrice(prodId = null) {
    const id = prodId || parseInt(document.getElementById("productSelect").value, 10);
    if (state.negotiatedPrices && state.negotiatedPrices[id]) {
        delete state.negotiatedPrices[id];
    }
    state.farmerNegotiatedPrices = {};
    const banner = document.getElementById("negotiatedAlertBanner");
    if (banner) banner.style.display = "none";
    const actionCard = document.getElementById("negAgreedActionCard");
    if (actionCard) actionCard.style.display = "none";

    if (state.currentMatching && state.currentPriceInsight) {
        updateKPIs(state.currentMatching, state.currentPriceInsight, state.currentRoute);
        renderFarmerMatchTable(state.currentMatching);
    }
    showNotification("Negotiated price cleared. Standard asking price restored.");
}

// 10D. Apply and Switch Back to Main Dashboard to Place Order
function applyAndGoToOrder() {
    switchTab('dashboard');
    applyNegotiatedPriceUI();
    showNotification("🤝 Negotiated price applied! Click 'Lock & Generate Procurement Contract' to place order.");
    setTimeout(() => {
        const btn = document.getElementById("generateContractBtn");
        if (btn) {
            btn.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }, 250);
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

    // Check if a negotiated rate was established in Price Intelligence
    const negInfo = (state.negotiatedPrices && state.negotiatedPrices[productId]) 
        ? state.negotiatedPrices[productId] 
        : null;

    let totalProduceCost = 0;
    // Map individual farmer allocations with their individual negotiated rates
    const allocations = state.currentMatching.farmers.map(f => {
        const indRate = (state.farmerNegotiatedPrices && state.farmerNegotiatedPrices[f.farmer_id] !== undefined)
            ? Number(state.farmerNegotiatedPrices[f.farmer_id])
            : (negInfo ? Number(negInfo.negotiatedPrice) : Number(f.expected_price));
        const subtotal = Math.round(f.matched_quantity * indRate * 100) / 100;
        totalProduceCost += subtotal;
        return {
            farmer_id: f.farmer_id,
            farmer_name: f.farmer_name,
            location: f.location,
            matched_quantity: f.matched_quantity,
            expected_price: indRate,
            subtotal: subtotal
        };
    });

    const blendedRate = quantity > 0 
        ? Math.round((totalProduceCost / quantity) * 100) / 100 
        : (negInfo ? negInfo.negotiatedPrice : state.currentMatching.blended_price_per_kg);

    const buyerName = (state.currentUser && state.currentUser.name) 
        ? state.currentUser.name 
        : (BUYER_HUB.name || "Verified Wholesale Buyer");

    const payload = {
        buyer_name: buyerName,
        product_id: productId,
        total_quantity: quantity,
        agreed_price_per_kg: blendedRate,
        farmer_allocations: allocations,
        route_summary: state.currentRoute
    };

    try {
        const res = await fetch(`${API_BASE}/api/orders/fulfill`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const order = await res.json();
        renderOrderContract(order, negInfo);
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
function renderOrderContract(order, negInfo = null) {
    const area = document.getElementById("orderConfirmationArea");
    const isNegotiated = Boolean(negInfo) || 
        (state.farmerNegotiatedPrices && Object.keys(state.farmerNegotiatedPrices).length > 0) || 
        (state.negotiatedPrices && Object.values(state.negotiatedPrices).some(np => Math.abs(np.negotiatedPrice - order.agreed_price_per_kg) < 0.05));

    const rateBadge = isNegotiated 
        ? `<div style="margin-top:3px;"><span class="badge badge-success" style="font-size:10px; font-weight:700;">🤝 NEGOTIATED CONTRACT RATE</span></div>` 
        : '';

    // Date formatting: ensure no UTC text and clean AM/PM display
    let formattedDate = order.created_at || "";
    formattedDate = formattedDate.replace(/\s*UTC\s*/gi, "").trim();

    // Prepare farmer item list
    const items = (order.farmer_items && order.farmer_items.length > 0)
        ? order.farmer_items
        : (state.currentMatching ? state.currentMatching.farmers.map(f => {
            const indRate = (state.farmerNegotiatedPrices && state.farmerNegotiatedPrices[f.farmer_id] !== undefined)
                ? Number(state.farmerNegotiatedPrices[f.farmer_id])
                : (negInfo ? Number(negInfo.negotiatedPrice) : Number(f.expected_price));
            return {
                farmer_id: f.farmer_id,
                farmer_name: f.farmer_name,
                quantity_kg: f.matched_quantity,
                price_per_kg: indRate,
                subtotal: Math.round(f.matched_quantity * indRate * 100) / 100
            };
        }) : []);

    area.innerHTML = `
        <div class="order-contract-box">
            <div class="contract-header">
                <div>
                    <span class="badge badge-success">DIGITAL CONTRACT VERIFIED</span>
                    <h2 class="mt-2" style="font-family: var(--font-head); font-size:22px;">Order #${order.order_number}</h2>
                    <p class="text-muted" style="margin-top:4px; font-size:13px;">Generated on ${formattedDate}</p>
                </div>
                <div style="text-align:right;">
                    <span class="text-muted" style="font-size:12px;">Total Contract Value</span>
                    <div style="font-size:24px; font-weight:800; color:#15803d;">₹${order.grand_total.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                    <span class="badge" style="background:#ecfdf5; color:#065f46;">Includes ₹${order.logistics_cost.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} Freight</span>
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
                    <span class="label">Blended Unit Rate</span>
                    <span class="val" style="font-size:16px;">₹${order.agreed_price_per_kg.toFixed(2)} / kg</span>
                    ${rateBadge}
                </div>
                <div class="price-stat-box">
                    <span class="label">Participating Smallholders</span>
                    <span class="val" style="font-size:16px;">${order.farmers_involved || items.length} Local Farmers</span>
                </div>
            </div>

            <!-- Itemized Farmer Payout & Produce Breakdown Table -->
            <div class="mt-4 mb-3">
                <h4 style="font-size:15px; font-weight:700; color:#1e293b; margin-bottom:10px;">📋 Itemized Farmer Payout & Produce Bill:</h4>
                <div class="table-responsive">
                    <table class="data-table" style="font-size:13px;">
                        <thead>
                            <tr style="background:#f8fafc;">
                                <th>Farmer Name</th>
                                <th>Allocated Volume</th>
                                <th>Agreed Unit Rate</th>
                                <th>Individual Farmer Payout</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${items.map(item => `
                                <tr>
                                    <td><strong>${item.farmer_name}</strong> <span class="text-muted" style="font-size:11.5px;">(Farmer #${item.farmer_id})</span></td>
                                    <td><strong>${Number(item.quantity_kg).toLocaleString()} kg</strong></td>
                                    <td><strong style="color:#15803d;">₹${Number(item.price_per_kg).toFixed(2)} / kg</strong></td>
                                    <td><strong>₹${Number(item.subtotal).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</strong></td>
                                    <td><span class="badge badge-success" style="font-size:10px;">Contract Agreed</span></td>
                                </tr>
                            `).join("")}
                        </tbody>
                        <tfoot>
                            <tr style="background:#f1f5f9; font-weight:700;">
                                <td colspan="3" style="text-align:right;">Subtotal Produce Procurement:</td>
                                <td colspan="2">₹${Number(order.total_procurement_cost).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                            </tr>
                            <tr style="background:#f8fafc; font-weight:600;">
                                <td colspan="3" style="text-align:right;">Logistics Transit (${order.logistics_distance_km} km):</td>
                                <td colspan="2">₹${Number(order.logistics_cost).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                            </tr>
                            <tr style="background:#ecfdf5; font-weight:800; font-size:14px; color:#15803d;">
                                <td colspan="3" style="text-align:right;">Grand Total Order Bill:</td>
                                <td colspan="2">₹${Number(order.grand_total).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                            </tr>
                        </tfoot>
                    </table>
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
                <span class="text-muted" style="font-size:12.5px;">🔒 Cryptographically Signed Procurement Manifest via FarmBuy AI Supply Intelligence</span>
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
        let ordersUrl = `${API_BASE}/api/orders`;
        if (state.currentUser && state.currentUser.role === "buyer" && state.currentUser.name) {
            ordersUrl += `?buyer_name=${encodeURIComponent(state.currentUser.name)}`;
        }
        const res = await fetch(ordersUrl);
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
            
            const cancelBtn = !isCancelled
                ? `<button class="btn-cancel-order" onclick="cancelOrder(${o.id}, '${o.order_number}')">Cancel & Return Stock</button>`
                : `<span class="text-muted" style="font-size:12px;">Stock Returned</span>`;
            
            const deleteBtn = `<button class="btn-delete-order" style="padding:4px 8px; font-size:11px; margin-left:6px; background:#fff1f2; color:#be123c; border:1px solid #fecdd3; border-radius:4px; cursor:pointer;" onclick="deleteBuyerOrder(${o.id}, '${o.order_number}')" title="Delete from order history">🗑️</button>`;

            const actionCell = `<div style="display:flex; align-items:center;">${cancelBtn}${deleteBtn}</div>`;

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
                    <td>${actionCell}</td>
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

// 18. Delete Single Buyer Order from History
async function deleteBuyerOrder(orderId, orderNum) {
    if (!confirm(`Remove order #${orderNum} from platform history?`)) {
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/orders/${orderId}`, { method: "DELETE" });
        const data = await res.json();
        if (res.ok) {
            showNotification(data.message || `Order #${orderNum} removed from history.`);
            await loadOrderHistory();
            if (state.currentUser && state.currentUser.role === "farmer") {
                loadFarmerProduceList();
            }
        } else {
            alert(data.detail || "Could not delete order");
        }
    } catch (err) {
        console.error("Delete order error:", err);
        alert("Failed to delete order.");
    }
}

// 19. Clear All Buyer Order History
async function clearBuyerOrderHistory() {
    if (!confirm("Are you sure you want to clear all platform order history? This keeps the dashboard tidy.")) {
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/orders`, { method: "DELETE" });
        const data = await res.json();
        if (res.ok) {
            showNotification(data.message || "Order history cleared.");
            await loadOrderHistory();
            if (state.currentUser && state.currentUser.role === "farmer") {
                loadFarmerProduceList();
            }
        } else {
            alert(data.detail || "Could not clear order history");
        }
    } catch (err) {
        console.error("Clear order history error:", err);
        alert("Failed to clear order history.");
    }
}

// 20. Toast Notification Helper
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
window.deleteBuyerOrder = deleteBuyerOrder;
window.clearBuyerOrderHistory = clearBuyerOrderHistory;
window.restockSupplies = restockSupplies;
window.runCompleteAnalysis = runCompleteAnalysis;
window.onDemandParamsChange = onDemandParamsChange;
window.onProductChange = onProductChange;
window.switchTab = switchTab;
window.generateProcurementContract = generateProcurementContract;
window.simulateNegotiationOffer = simulateNegotiationOffer;
window.applyAndGoToOrder = applyAndGoToOrder;
window.clearNegotiatedPrice = clearNegotiatedPrice;
window.applyNegotiatedPriceUI = applyNegotiatedPriceUI;
window.openEditProduceModal = openEditProduceModal;
window.closeEditProduceModal = closeEditProduceModal;
window.submitFarmerProduceUpdate = submitFarmerProduceUpdate;
window.onIndividualFarmerRateChange = onIndividualFarmerRateChange;
window.loadFarmerDemandForecast = loadFarmerDemandForecast;
window.onFarmerForecastCropChange = onFarmerForecastCropChange;
window.toggleFarmerTechnicalChart = toggleFarmerTechnicalChart;
window.openEditFarmerModal = openEditFarmerModal;
window.closeEditFarmerModal = closeEditFarmerModal;
window.handleEditFarmerSubmit = handleEditFarmerSubmit;
window.deleteFarmerRecord = deleteFarmerRecord;
window.openEditBuyerModal = openEditBuyerModal;
window.closeEditBuyerModal = closeEditBuyerModal;
window.handleEditBuyerSubmit = handleEditBuyerSubmit;
window.deleteBuyerRecord = deleteBuyerRecord;