// DSE Market Signal — Professional TradingView Interactive Dashboard

let currentSymbol = "GP";
let currentPrice = 0.0;
let chartData = [];
let currentLevels = null;
let allWatchlistTickers = [];

// Lightweight Charts instances & series
let mainChart = null;
let candleSeries = null;
let volumeSeries = null;
let ema9Series = null;
let ema21Series = null;
let ema50Series = null;
let activePriceLines = [];

let rsiChart = null;
let rsiSeries = null;
let isSyncingRange = false;

// Initialize dashboard on DOM load
document.addEventListener("DOMContentLoaded", () => {
  setupSidebarToggles();
  initLightweightCharts();
  setupSearchFilter();
  setupClock();

  fetchSystemHealth();
  fetchMarketStatus();
  fetchMarketSummary();
  loadStockData(currentSymbol);
  fetchPortfolio();

  // Polling intervals
  setInterval(fetchSystemHealth, 30000);
  setInterval(fetchMarketStatus, 60000);
});

// Setup Real-time Header Clock
function setupClock() {
  const clockEl = document.getElementById("clock-display");
  function tick() {
    if (!clockEl) return;
    const now = new Date();
    clockEl.innerText = now.toLocaleTimeString("en-GB", { timeZone: "Asia/Dhaka" }) + " BST";
  }
  tick();
  setInterval(tick, 1000);
}

// Initialize TradingView Lightweight Charts
function initLightweightCharts() {
  const mainContainer = document.getElementById("priceChart");
  const rsiContainer = document.getElementById("tv-rsi-chart");

  if (!mainContainer || typeof LightweightCharts === "undefined") {
    console.warn("LightweightCharts not loaded or container missing; using fallback.");
    return;
  }

  // 1. Create Main Candlestick Chart
  mainChart = LightweightCharts.createChart(mainContainer, {
    autoSize: true,
    layout: {
      background: { type: "solid", color: "#1e222d" },
      textColor: "#d1d4dc",
      fontSize: 11,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    },
    grid: {
      vertLines: { color: "rgba(54, 60, 78, 0.35)", style: LightweightCharts.LineStyle.Solid },
      horzLines: { color: "rgba(54, 60, 78, 0.35)", style: LightweightCharts.LineStyle.Solid }
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: {
        color: "#787b86",
        width: 1,
        style: LightweightCharts.LineStyle.Dashed,
        labelBackgroundColor: "#2a2e39"
      },
      horzLine: {
        color: "#787b86",
        width: 1,
        style: LightweightCharts.LineStyle.Dashed,
        labelBackgroundColor: "#2a2e39"
      }
    },
    rightPriceScale: {
      borderColor: "#363c4e",
      scaleMargins: {
        top: 0.08,
        bottom: 0.22 // Room for volume overlay
      }
    },
    timeScale: {
      borderColor: "#363c4e",
      timeVisible: true,
      secondsVisible: false
    }
  });

  // Candlestick Series
  candleSeries = mainChart.addCandlestickSeries({
    upColor: "#089981",
    downColor: "#f23645",
    borderUpColor: "#089981",
    borderDownColor: "#f23645",
    wickUpColor: "#089981",
    wickDownColor: "#f23645"
  });

  // Volume Overlay Series
  volumeSeries = mainChart.addHistogramSeries({
    priceFormat: { type: "volume" },
    priceScaleId: "", // Overlay mode
    scaleMargins: {
      top: 0.8,
      bottom: 0
    }
  });

  // EMA Series
  ema9Series = mainChart.addLineSeries({
    color: "#2962ff",
    lineWidth: 2,
    title: "EMA 9",
    priceLineVisible: false,
    lastValueVisible: false
  });

  ema21Series = mainChart.addLineSeries({
    color: "#ff9800",
    lineWidth: 2,
    title: "EMA 21",
    priceLineVisible: false,
    lastValueVisible: false
  });

  ema50Series = mainChart.addLineSeries({
    color: "#ab47bc",
    lineWidth: 2,
    title: "EMA 50",
    priceLineVisible: false,
    lastValueVisible: false
  });

  // 2. Create Synchronized RSI Chart
  if (rsiContainer) {
    rsiChart = LightweightCharts.createChart(rsiContainer, {
      autoSize: true,
      layout: {
        background: { type: "solid", color: "#1e222d" },
        textColor: "#787b86",
        fontSize: 10
      },
      grid: {
        vertLines: { color: "rgba(54, 60, 78, 0.25)" },
        horzLines: { color: "rgba(54, 60, 78, 0.25)" }
      },
      rightPriceScale: {
        borderColor: "#363c4e",
        scaleMargins: { top: 0.1, bottom: 0.1 }
      },
      timeScale: {
        borderColor: "#363c4e",
        visible: false // Hidden on subpane for seamless look
      }
    });

    rsiSeries = rsiChart.addLineSeries({
      color: "#ab47bc",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true
    });

    // Reference lines for Overbought (70) and Oversold (30)
    rsiSeries.createPriceLine({
      price: 70,
      color: "rgba(242, 54, 69, 0.7)",
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      axisLabelVisible: true,
      title: "OB 70"
    });

    rsiSeries.createPriceLine({
      price: 30,
      color: "rgba(8, 153, 129, 0.7)",
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      axisLabelVisible: true,
      title: "OS 30"
    });

    // Synchronize TimeScales
    mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (isSyncingRange || !range || !rsiChart) return;
      isSyncingRange = true;
      rsiChart.timeScale().setVisibleLogicalRange(range);
      isSyncingRange = false;
    });

    rsiChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (isSyncingRange || !range || !mainChart) return;
      isSyncingRange = true;
      mainChart.timeScale().setVisibleLogicalRange(range);
      isSyncingRange = false;
    });
  }

  // Crosshair hover legend listener
  mainChart.subscribeCrosshairMove(param => {
    updateLegendOnHover(param);
  });

  // Fit Data button
  const fitBtn = document.getElementById("btn-fit-chart");
  if (fitBtn) {
    fitBtn.addEventListener("click", () => {
      if (mainChart) mainChart.timeScale().fitContent();
      if (rsiChart) rsiChart.timeScale().fitContent();
    });
  }
}

// Update Top Legend during Crosshair movement
function updateLegendOnHover(param) {
  const oEl = document.getElementById("leg-open");
  const hEl = document.getElementById("leg-high");
  const lEl = document.getElementById("leg-low");
  const cEl = document.getElementById("leg-close");
  const vEl = document.getElementById("leg-vol");
  const ema9El = document.getElementById("leg-ema9");
  const ema21El = document.getElementById("leg-ema21");
  const ema50El = document.getElementById("leg-ema50");
  const rsiEl = document.getElementById("leg-rsi");

  if (!param || !param.time || !param.seriesData) {
    // Reset to latest data point when cursor leaves
    setLegendToLatest();
    return;
  }

  const cData = param.seriesData.get(candleSeries);
  if (cData) {
    if (oEl) oEl.innerText = cData.open ? cData.open.toFixed(1) : "---";
    if (hEl) hEl.innerText = cData.high ? cData.high.toFixed(1) : "---";
    if (lEl) lEl.innerText = cData.low ? cData.low.toFixed(1) : "---";
    if (cEl) {
      cEl.innerText = cData.close ? cData.close.toFixed(1) : "---";
      cEl.style.color = (cData.close >= cData.open) ? "var(--accent-green)" : "var(--accent-red)";
    }
  }

  const vData = param.seriesData.get(volumeSeries);
  if (vData && vEl) {
    vEl.innerText = Math.round(vData.value).toLocaleString();
  }

  const ema9Val = param.seriesData.get(ema9Series);
  if (ema9Val && ema9El) ema9El.innerText = ema9Val.value ? ema9Val.value.toFixed(1) : "---";

  const ema21Val = param.seriesData.get(ema21Series);
  if (ema21Val && ema21El) ema21El.innerText = ema21Val.value ? ema21Val.value.toFixed(1) : "---";

  const ema50Val = param.seriesData.get(ema50Series);
  if (ema50Val && ema50El) ema50El.innerText = ema50Val.value ? ema50Val.value.toFixed(1) : "---";

  // RSI for hovered date
  if (param.time && chartData.length > 0) {
    const item = chartData.find(d => d.date === param.time);
    if (item && rsiEl) {
      rsiEl.innerText = item.rsi_14 ? item.rsi_14.toFixed(1) : "---";
    }
  }
}

// Reset Legend to latest available bar
function setLegendToLatest() {
  if (!chartData || chartData.length === 0) return;
  const last = chartData[chartData.length - 1];

  const oEl = document.getElementById("leg-open");
  const hEl = document.getElementById("leg-high");
  const lEl = document.getElementById("leg-low");
  const cEl = document.getElementById("leg-close");
  const vEl = document.getElementById("leg-vol");
  const ema9El = document.getElementById("leg-ema9");
  const ema21El = document.getElementById("leg-ema21");
  const ema50El = document.getElementById("leg-ema50");
  const rsiEl = document.getElementById("leg-rsi");

  if (oEl) oEl.innerText = last.open ? last.open.toFixed(1) : "---";
  if (hEl) hEl.innerText = last.high ? last.high.toFixed(1) : "---";
  if (lEl) lEl.innerText = last.low ? last.low.toFixed(1) : "---";
  if (cEl) {
    cEl.innerText = last.close ? last.close.toFixed(1) : "---";
    cEl.style.color = (last.close >= last.open) ? "var(--accent-green)" : "var(--accent-red)";
  }
  if (vEl) vEl.innerText = last.volume ? Math.round(last.volume).toLocaleString() : "---";
  if (ema9El) ema9El.innerText = last.ema_9 ? last.ema_9.toFixed(1) : "---";
  if (ema21El) ema21El.innerText = last.ema_21 ? last.ema_21.toFixed(1) : "---";
  if (ema50El) ema50El.innerText = last.ema_50 ? last.ema_50.toFixed(1) : "---";
  if (rsiEl) rsiEl.innerText = last.rsi_14 ? last.rsi_14.toFixed(1) : "---";
}

// Sidebar Toggle Handlers
function setupSidebarToggles() {
  const toggleLeft = document.getElementById("toggle-left");
  const toggleRight = document.getElementById("toggle-right");
  const toggleFullscreen = document.getElementById("toggle-fullscreen");
  const handleLeft = document.getElementById("handle-left");
  const handleRight = document.getElementById("handle-right");
  const leftSidebar = document.getElementById("left-sidebar");
  const rightSidebar = document.getElementById("right-sidebar");

  function setLeftState(hidden) {
    if (!leftSidebar) return;
    leftSidebar.classList.toggle("hidden", hidden);
    if (toggleLeft) {
      toggleLeft.innerText = hidden ? "▶ Watchlist" : "◀ Watchlist";
      toggleLeft.classList.toggle("active", !hidden);
    }
    if (handleLeft) {
      handleLeft.innerText = hidden ? "▶" : "◀";
      handleLeft.classList.toggle("collapsed", hidden);
      handleLeft.title = hidden ? "Show Watchlist (Hotkey: [)" : "Hide Watchlist (Hotkey: [)";
    }
    localStorage.setItem("dse_sidebar_left", hidden ? "0" : "1");
    triggerSmoothResize();
  }

  function setRightState(hidden) {
    if (!rightSidebar) return;
    rightSidebar.classList.toggle("hidden", hidden);
    if (toggleRight) {
      toggleRight.innerText = hidden ? "◀ Signals & Orders" : "Signals & Orders ▶";
      toggleRight.classList.toggle("active", !hidden);
    }
    if (handleRight) {
      handleRight.innerText = hidden ? "◀" : "▶";
      handleRight.classList.toggle("collapsed", hidden);
      handleRight.title = hidden ? "Show Orders (Hotkey: ])" : "Hide Orders (Hotkey: ])";
    }
    localStorage.setItem("dse_sidebar_right", hidden ? "0" : "1");
    triggerSmoothResize();
  }

  function triggerSmoothResize() {
    resizeChart();
    setTimeout(resizeChart, 150);
    setTimeout(resizeChart, 280);
  }

  // Restore saved preferences
  if (localStorage.getItem("dse_sidebar_left") === "0") setLeftState(true);
  if (localStorage.getItem("dse_sidebar_right") === "0") setRightState(true);

  if (toggleLeft) toggleLeft.addEventListener("click", () => setLeftState(!leftSidebar.classList.contains("hidden")));
  if (handleLeft) handleLeft.addEventListener("click", () => setLeftState(!leftSidebar.classList.contains("hidden")));

  if (toggleRight) toggleRight.addEventListener("click", () => setRightState(!rightSidebar.classList.contains("hidden")));
  if (handleRight) handleRight.addEventListener("click", () => setRightState(!rightSidebar.classList.contains("hidden")));

  // Fullscreen / Maximize Chart View
  if (toggleFullscreen) {
    toggleFullscreen.addEventListener("click", () => {
      const bothHidden = leftSidebar && rightSidebar && leftSidebar.classList.contains("hidden") && rightSidebar.classList.contains("hidden");
      if (bothHidden) {
        setLeftState(false);
        setRightState(false);
        toggleFullscreen.innerText = "⛶ Full Chart";
        toggleFullscreen.classList.remove("active");
      } else {
        setLeftState(true);
        setRightState(true);
        toggleFullscreen.innerText = "🗗 Standard View";
        toggleFullscreen.classList.add("active");
      }
    });
  }

  // Global Keyboard Shortcuts
  document.addEventListener("keydown", (e) => {
    if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
    if (e.key === "[") {
      setLeftState(!leftSidebar.classList.contains("hidden"));
    } else if (e.key === "]") {
      setRightState(!rightSidebar.classList.contains("hidden"));
    } else if (e.key === "f" || e.key === "F") {
      if (toggleFullscreen) toggleFullscreen.click();
    }
  });

  // Attach ResizeObserver to container
  const chartCard = document.getElementById("chart-container");
  if (chartCard && window.ResizeObserver) {
    const ro = new ResizeObserver(() => {
      resizeChart();
    });
    ro.observe(chartCard);
  }
}

// Watchlist Live Search Filter
function setupSearchFilter() {
  const searchInput = document.getElementById("search-symbol");
  if (!searchInput) return;

  searchInput.addEventListener("input", (e) => {
    const query = e.target.value.trim().toUpperCase();
    renderFilteredWatchlist(query);
  });
}

function renderFilteredWatchlist(query) {
  const watchlistEl = document.getElementById("watchlist-items");
  if (!watchlistEl) return;

  const filtered = query
    ? allWatchlistTickers.filter(s => s.symbol.toUpperCase().includes(query))
    : allWatchlistTickers;

  if (filtered.length === 0) {
    watchlistEl.innerHTML = `<div class="loading-state">No symbols match "${query}"</div>`;
    return;
  }

  watchlistEl.innerHTML = filtered.map(s => `
    <div class="watchlist-item ${s.symbol === currentSymbol ? 'active' : ''}" onclick="selectSymbol('${s.symbol}')">
      <div>
        <div class="ticker-sym">${s.symbol}</div>
        <div class="ticker-vol">Vol: ${Math.round(s.volume).toLocaleString()}</div>
      </div>
      <div>
        <div class="ticker-price">৳${s.close.toFixed(1)}</div>
        <div class="change-chip ${s.change_pct >= 0 ? 'positive' : 'negative'}">
          ${s.change_pct >= 0 ? '+' : ''}${s.change_pct.toFixed(2)}%
        </div>
      </div>
    </div>
  `).join("");
}

// Fetch System Health
async function fetchSystemHealth() {
  try {
    const res = await fetch("/health");
    if (!res.ok) return;
    const data = await res.json();
    const healthBadge = document.getElementById("health-badge");
    const schedulerInfo = document.getElementById("scheduler-info");

    if (healthBadge) {
      healthBadge.innerHTML = `<span style="color:var(--accent-green)">●</span> Backend Healthy`;
    }
    if (schedulerInfo) {
      schedulerInfo.innerText = `Scheduler: ${data.scheduler_running ? 'Active (16:30 BST)' : 'Standby'}`;
    }
  } catch (err) {
    console.error("Health fetch error:", err);
  }
}

// Fetch DSE Market Status
async function fetchMarketStatus() {
  try {
    const res = await fetch("/dse/market-status");
    if (!res.ok) return;
    const data = await res.json();
    const statusBadge = document.getElementById("market-status");
    if (statusBadge) {
      statusBadge.className = `badge ${data.status === 'OPEN' ? 'badge-open' : 'badge-closed'}`;
      statusBadge.innerText = `DSE: ${data.status} (${data.session})`;
    }
  } catch (err) {
    console.error("Market status fetch error:", err);
  }
}

// Fetch Market Summary & Breadth
async function fetchMarketSummary() {
  try {
    const res = await fetch("/market/summary");
    if (!res.ok) return;
    const data = await res.json();

    const adv = data.advancers || 0;
    const dec = data.decliners || 0;
    const unch = data.unchanged || 0;
    const total = adv + dec + unch || 1;

    const advPct = ((adv / total) * 100).toFixed(1);
    const decPct = ((dec / total) * 100).toFixed(1);
    const unchPct = ((unch / total) * 100).toFixed(1);

    const countBadge = document.getElementById("breadth-total-count");
    if (countBadge) countBadge.innerText = `${total} Issues`;

    const breadthEl = document.getElementById("market-breadth");
    if (breadthEl) {
      breadthEl.innerHTML = `
        <div class="breadth-meter-bar">
          <div class="breadth-seg-adv" style="width: ${advPct}%" title="Advancers: ${adv} (${advPct}%)"></div>
          <div class="breadth-seg-dec" style="width: ${decPct}%" title="Decliners: ${dec} (${decPct}%)"></div>
          <div class="breadth-seg-unch" style="width: ${unchPct}%" title="Unchanged: ${unch} (${unchPct}%)"></div>
        </div>
        <div class="breadth-stats-row">
          <div class="breadth-pill adv">
            <span class="count">▲ ${adv}</span>
            <span>Adv (${advPct}%)</span>
          </div>
          <div class="breadth-pill dec">
            <span class="count">▼ ${dec}</span>
            <span>Dec (${decPct}%)</span>
          </div>
          <div class="breadth-pill unch">
            <span class="count">● ${unch}</span>
            <span>Unch (${unchPct}%)</span>
          </div>
        </div>
      `;
    }

    if (data.top_gainers) {
      allWatchlistTickers = data.top_gainers;
      renderFilteredWatchlist("");
    }
  } catch (err) {
    console.error("Market summary fetch error:", err);
  }
}

// Load Stock Data & Chart
async function loadStockData(symbol) {
  currentSymbol = symbol;
  try {
    const [anaRes, sigRes, indRes] = await Promise.all([
      fetch(`/analysis/${symbol}`),
      fetch(`/signals/${symbol}`),
      fetch(`/indicators/${symbol}?limit=90`)
    ]);

    let levels = null;
    if (anaRes.ok) {
      const ana = await anaRes.json();
      currentPrice = ana.price.close;
      updateStockHeader(ana);
      updateTechnicalLevels(ana);
      levels = ana.levels;
    }

    if (sigRes.ok) {
      const sig = await sigRes.json();
      updateSignalCard(sig);
    }

    if (indRes.ok) {
      const ind = await indRes.json();
      chartData = ind.data || [];
      if (!levels && ind.levels) {
        levels = ind.levels;
      }
      currentLevels = levels;
      renderChart(chartData, currentLevels);
    }

    calculateEstCost();
  } catch (err) {
    console.error("Error loading stock:", err);
  }
}

function selectSymbol(sym) {
  loadStockData(sym);
  const items = document.querySelectorAll(".watchlist-item");
  items.forEach(el => el.classList.remove("active"));
  const searchInput = document.getElementById("search-symbol");
  renderFilteredWatchlist(searchInput ? searchInput.value.trim().toUpperCase() : "");
}

function updateStockHeader(ana) {
  const symEl = document.getElementById("active-symbol");
  const priceEl = document.getElementById("active-price");
  const changeEl = document.getElementById("active-change");

  if (symEl) symEl.innerText = ana.symbol;
  if (priceEl) priceEl.innerText = `BDT ৳${ana.price.close.toFixed(1)}`;
  if (changeEl) {
    const chg = ana.price.change;
    const pct = ana.price.change_pct;
    changeEl.className = `stock-change ${pct >= 0 ? 'positive' : 'negative'}`;
    changeEl.innerText = `${pct >= 0 ? '+' : ''}${chg.toFixed(1)} (${pct.toFixed(2)}%)`;
  }
}

function updateTechnicalLevels(ana) {
  const rsiEl = document.getElementById("val-rsi");
  const macdEl = document.getElementById("val-macd");
  const trendEl = document.getElementById("val-trend");
  const pivotEl = document.getElementById("val-pivot");
  const s1El = document.getElementById("val-s1");
  const r1El = document.getElementById("val-r1");

  if (rsiEl) rsiEl.innerText = ana.indicators.rsi_14.toFixed(1);
  if (macdEl) macdEl.innerText = ana.indicators.macd.histogram.toFixed(2);
  if (trendEl) {
    trendEl.innerText = ana.trend;
    trendEl.className = `stat-value ${ana.trend === 'Bullish' ? 'positive' : (ana.trend === 'Bearish' ? 'negative' : '')}`;
  }
  if (pivotEl) pivotEl.innerText = `৳${ana.levels.pivot.toFixed(1)}`;
  if (s1El) s1El.innerText = `৳${ana.levels.support_1.toFixed(1)}`;
  if (r1El) r1El.innerText = `৳${ana.levels.resistance_1.toFixed(1)}`;
}

function updateSignalCard(sig) {
  const badge = document.getElementById("signal-badge");
  const conf = document.getElementById("signal-confidence");
  const target = document.getElementById("signal-target");
  const sl = document.getElementById("signal-stop-loss");
  const rrr = document.getElementById("signal-rrr");
  const reasonsEl = document.getElementById("signal-reasons");

  if (badge) {
    badge.innerText = sig.signal;
    badge.className = `signal-tag ${sig.signal.includes('BUY') ? 'signal-buy' : (sig.signal.includes('SELL') ? 'signal-sell' : 'signal-hold')}`;
  }
  if (conf) conf.innerText = `${sig.confidence}%`;
  if (target) target.innerText = `৳${sig.target.toFixed(1)}`;
  if (sl) sl.innerText = `৳${sig.stop_loss.toFixed(1)}`;
  if (rrr) rrr.innerText = `1:${sig.risk_reward_ratio}`;

  if (reasonsEl && sig.reasons) {
    reasonsEl.innerHTML = sig.reasons.map(r => `<li>${r}</li>`).join("");
  }
}

// Render TradingView Candlestick Chart, Overlays, and S&R Levels
function renderChart(data, levels = currentLevels) {
  if (!mainChart || !candleSeries || !data || data.length === 0) return;

  // Clean and deduplicate data sorted by date ascending
  const cleanData = [];
  const seenDates = new Set();

  const sorted = [...data].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  for (const item of sorted) {
    if (!item.date || seenDates.has(item.date) || !item.close || item.close <= 0) continue;
    seenDates.add(item.date);

    const close = item.close;
    const open = (item.open && item.open > 0) ? item.open : close;
    const high = (item.high && item.high > 0) ? Math.max(item.high, open, close) : Math.max(open, close);
    const low = (item.low && item.low > 0) ? Math.min(item.low, open, close) : Math.min(open, close);

    cleanData.push({
      date: item.date,
      open,
      high,
      low,
      close,
      volume: item.volume || 0,
      ema_9: item.ema_9,
      ema_21: item.ema_21,
      ema_50: item.ema_50,
      rsi_14: item.rsi_14
    });
  }

  if (cleanData.length === 0) return;

  // 1. Candlestick series
  const candlePoints = cleanData.map(d => ({
    time: d.date,
    open: d.open,
    high: d.high,
    low: d.low,
    close: d.close
  }));
  candleSeries.setData(candlePoints);

  // 2. Volume series
  if (volumeSeries) {
    const volumePoints = cleanData.map(d => ({
      time: d.date,
      value: d.volume,
      color: d.close >= d.open ? "rgba(8, 153, 129, 0.4)" : "rgba(242, 54, 69, 0.4)"
    }));
    volumeSeries.setData(volumePoints);
  }

  // 3. EMA lines
  if (ema9Series) {
    const ema9Points = cleanData.filter(d => d.ema_9 && d.ema_9 > 0).map(d => ({ time: d.date, value: d.ema_9 }));
    ema9Series.setData(ema9Points);
  }
  if (ema21Series) {
    const ema21Points = cleanData.filter(d => d.ema_21 && d.ema_21 > 0).map(d => ({ time: d.date, value: d.ema_21 }));
    ema21Series.setData(ema21Points);
  }
  if (ema50Series) {
    const ema50Points = cleanData.filter(d => d.ema_50 && d.ema_50 > 0).map(d => ({ time: d.date, value: d.ema_50 }));
    ema50Series.setData(ema50Points);
  }

  // 4. RSI Series
  if (rsiSeries) {
    const rsiPoints = cleanData.filter(d => d.rsi_14 && d.rsi_14 > 0).map(d => ({ time: d.date, value: d.rsi_14 }));
    rsiSeries.setData(rsiPoints);
  }

  // 5. Support & Resistance Native Price Lines
  activePriceLines.forEach(line => {
    try { candleSeries.removePriceLine(line); } catch (e) {}
  });
  activePriceLines = [];

  if (levels) {
    // Resistance 1
    if (levels.resistance_1 && levels.resistance_1 > 0) {
      activePriceLines.push(candleSeries.createPriceLine({
        price: levels.resistance_1,
        color: "#ef5350",
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: `R1 ${levels.resistance_1.toFixed(1)}`
      }));
    }

    // Support 1
    if (levels.support_1 && levels.support_1 > 0) {
      activePriceLines.push(candleSeries.createPriceLine({
        price: levels.support_1,
        color: "#089981",
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: `S1 ${levels.support_1.toFixed(1)}`
      }));
    }

    // Classic Pivot
    if (levels.pivot && levels.pivot > 0) {
      activePriceLines.push(candleSeries.createPriceLine({
        price: levels.pivot,
        color: "#f0b90b",
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dotted,
        axisLabelVisible: true,
        title: `P ${levels.pivot.toFixed(1)}`
      }));
    }
  }

  // Fit view & update legend
  mainChart.timeScale().fitContent();
  if (rsiChart) rsiChart.timeScale().fitContent();
  setLegendToLatest();
}

function resizeChart() {
  if (mainChart) {
    const mainContainer = document.getElementById("priceChart");
    if (mainContainer) {
      mainChart.applyOptions({ width: mainContainer.clientWidth, height: mainContainer.clientHeight });
    }
  }
  if (rsiChart) {
    const rsiContainer = document.getElementById("tv-rsi-chart");
    if (rsiContainer) {
      rsiChart.applyOptions({ width: rsiContainer.clientWidth, height: rsiContainer.clientHeight });
    }
  }
}
window.addEventListener("resize", resizeChart);

// Quick Quantity Buttons & Est. Cost Calculation
function setQuickQty(qty) {
  const qtyInput = document.getElementById("order-qty");
  if (qtyInput) {
    qtyInput.value = qty;
    calculateEstCost();
  }
}

function calculateEstCost() {
  const qtyInput = document.getElementById("order-qty");
  const costEl = document.getElementById("order-est-cost");
  if (!qtyInput || !costEl) return;

  const qty = parseInt(qtyInput.value) || 0;
  const totalCost = (currentPrice * qty);
  costEl.innerText = `BDT ৳${totalCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// Paper Trading Order Submission
async function executePaperOrder(side) {
  const qtyInput = document.getElementById("order-qty");
  const qty = parseInt(qtyInput ? qtyInput.value : 10) || 10;

  try {
    const res = await fetch(`/paper/order?account_id=default&symbol=${currentSymbol}&side=${side}&quantity=${qty}`, {
      method: "POST"
    });
    const data = await res.json();
    if (res.ok) {
      alert(`✅ Order ${side} ${qty} ${currentSymbol} executed successfully!\nFill Price: ৳${data.fill_price.toFixed(1)}`);
      fetchPortfolio();
    } else {
      alert(`❌ Order failed: ${data.detail || 'Error'}`);
    }
  } catch (err) {
    alert("Order execution error: " + err);
  }
}

// Fetch Portfolio
async function fetchPortfolio() {
  try {
    const res = await fetch("/paper/portfolio?account_id=default");
    if (!res.ok) return;
    const data = await res.json();

    const cashEl = document.getElementById("port-cash");
    const equityEl = document.getElementById("port-equity");
    const pnlEl = document.getElementById("port-pnl");

    if (cashEl) cashEl.innerText = `৳${data.cash_balance.toLocaleString()}`;
    if (equityEl) equityEl.innerText = `৳${data.total_equity.toLocaleString()}`;
    if (pnlEl) {
      pnlEl.innerText = `${data.total_pnl >= 0 ? '+' : ''}৳${data.total_pnl.toFixed(1)} (${data.total_return_pct.toFixed(2)}%)`;
      pnlEl.className = data.total_pnl >= 0 ? 'positive' : 'negative';
    }
  } catch (err) {
    console.error("Portfolio fetch error:", err);
  }
}

// Telegram Alert Action
async function triggerTelegramAlert() {
  try {
    const res = await fetch(`/signals/notify/${currentSymbol}`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      alert(`📲 Telegram Alert dispatched (${data.notification.status}):\n${data.notification.preview || 'Sent!'}`);
    } else {
      alert("Notification failed");
    }
  } catch (err) {
    alert("Alert error: " + err);
  }
}
