// DSE Market Signal — StockNow Professional TradingView Architecture

let currentSymbol = "GP";
let currentPrice = 0.0;
let chartData = [];
let currentLevels = null;
let allSharesData = [];

// TradingView Lightweight Charts instances & series
let mainChart = null;
let candleSeries = null;
let volumeSeries = null;
let ema9Series = null;
let ema21Series = null;
let ema50Series = null;
let activePriceLines = [];

let rsiChart = null;
let rsiSeries = null;

let macdChart = null;
let macdLineSeries = null;
let signalLineSeries = null;
let macdHistSeries = null;

let isSyncingRange = false;

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  setupSidebarToggles();
  initLightweightCharts();
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

function setupSidebarToggles() {
  setupUIHandlers();
}

// Setup Clock
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

// UI Handlers (Tabs, Toggles, Drawing Tools, Search)
function setupUIHandlers() {
  // 1. Right Panel Toggle
  const toggleRight = document.getElementById("toggle-right");
  const rightSidebar = document.getElementById("right-sidebar");
  if (toggleRight && rightSidebar) {
    toggleRight.addEventListener("click", () => {
      const isHidden = rightSidebar.classList.toggle("hidden");
      toggleRight.classList.toggle("active", !isHidden);
      triggerSmoothResize();
    });
  }

  // 2. Fullscreen toggle
  const toggleFullscreen = document.getElementById("toggle-fullscreen");
  if (toggleFullscreen && rightSidebar) {
    toggleFullscreen.addEventListener("click", () => {
      const isHidden = rightSidebar.classList.toggle("hidden");
      if (toggleRight) toggleRight.classList.toggle("active", !isHidden);
      toggleFullscreen.classList.toggle("active", isHidden);
      triggerSmoothResize();
    });
  }

  // Hotkey listener
  document.addEventListener("keydown", (e) => {
    if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
    if (e.key === "]" || e.key === "f" || e.key === "F") {
      if (toggleFullscreen) toggleFullscreen.click();
    }
  });

  // 3. Left Drawing Tools Selection
  const drawTools = document.querySelectorAll(".draw-tool");
  drawTools.forEach(btn => {
    btn.addEventListener("click", () => {
      drawTools.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });

  // 4. Timeframe Chips
  const tfBtns = document.querySelectorAll(".tf-btn");
  tfBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tfBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });

  // 5. Symbol Search Bar with Autocomplete Dropdown
  const searchInput = document.getElementById("symbol-search-input");
  const dropdown = document.getElementById("search-autocomplete-dropdown");

  if (searchInput && dropdown) {
    searchInput.addEventListener("input", (e) => {
      const query = e.target.value.trim().toUpperCase();
      if (!query) {
        dropdown.classList.add("hidden");
        return;
      }
      const matches = allSharesData.filter(s => s.symbol.toUpperCase().includes(query)).slice(0, 8);
      if (matches.length === 0) {
        dropdown.innerHTML = `<div style="padding:8px; font-size:11px; color:#787b86">No match for "${query}"</div>`;
      } else {
        dropdown.innerHTML = matches.map(m => `
          <div class="search-item" onclick="selectSymbol('${m.symbol}')">
            <strong>${m.symbol}</strong>
            <span class="${m.change_pct >= 0 ? 'positive' : 'negative'}">৳${m.close.toFixed(1)} (${m.change_pct >= 0 ? '+' : ''}${m.change_pct.toFixed(2)}%)</span>
          </div>
        `).join("");
      }
      dropdown.classList.remove("hidden");
    });

    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const query = searchInput.value.trim().toUpperCase();
        if (query) selectSymbol(query);
        dropdown.classList.add("hidden");
      }
    });

    document.addEventListener("click", (e) => {
      if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.add("hidden");
      }
    });
  }

  // 6. Resize Observer on chart container
  const chartContainer = document.getElementById("chart-container");
  if (chartContainer && window.ResizeObserver) {
    const ro = new ResizeObserver(() => triggerSmoothResize());
    ro.observe(chartContainer);
  }
}

function triggerSmoothResize() {
  resizeCharts();
  setTimeout(resizeCharts, 120);
  setTimeout(resizeCharts, 260);
}

// Right Tab Switcher
function switchRightTab(tabId) {
  document.querySelectorAll(".panel-tab").forEach(tab => {
    tab.classList.toggle("active", tab.dataset.tab === tabId);
  });
  document.querySelectorAll(".tab-content").forEach(content => {
    content.classList.toggle("active", content.id === tabId);
  });
}

// Initialize 3-Pane TradingView Lightweight Charts
function initLightweightCharts() {
  const mainContainer = document.getElementById("priceChart");
  const rsiContainer = document.getElementById("tv-rsi-chart");
  const macdContainer = document.getElementById("tv-macd-chart");

  if (!mainContainer || typeof LightweightCharts === "undefined") {
    console.warn("TradingView Lightweight Charts library not ready.");
    return;
  }

  const commonOptions = {
    layout: {
      background: { type: "solid", color: "#000000" },
      textColor: "#787b86",
      fontSize: 10,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, sans-serif'
    },
    grid: {
      vertLines: { color: "rgba(30, 34, 45, 0.4)", style: LightweightCharts.LineStyle.Solid },
      horzLines: { color: "rgba(30, 34, 45, 0.4)", style: LightweightCharts.LineStyle.Solid }
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: {
        color: "#787b86",
        width: 1,
        style: LightweightCharts.LineStyle.Dashed,
        labelBackgroundColor: "#1e222d"
      },
      horzLine: {
        color: "#787b86",
        width: 1,
        style: LightweightCharts.LineStyle.Dashed,
        labelBackgroundColor: "#1e222d"
      }
    },
    rightPriceScale: {
      borderColor: "#1e222d"
    },
    timeScale: {
      borderColor: "#1e222d",
      timeVisible: true,
      secondsVisible: false
    }
  };

  // 1. PANE 1: Main Candlestick Chart
  mainChart = LightweightCharts.createChart(mainContainer, {
    ...commonOptions,
    rightPriceScale: {
      borderColor: "#1e222d",
      scaleMargins: { top: 0.08, bottom: 0.22 }
    }
  });

  // StockNow Style Candlesticks (Emerald Green & Crimson Red)
  candleSeries = mainChart.addCandlestickSeries({
    upColor: "#26a69a",
    downColor: "#ef5350",
    borderUpColor: "#26a69a",
    borderDownColor: "#ef5350",
    wickUpColor: "#26a69a",
    wickDownColor: "#ef5350"
  });

  // Volume Histogram overlay at the base
  volumeSeries = mainChart.addHistogramSeries({
    priceFormat: { type: "volume" },
    priceScaleId: "", // Overlay mode
    scaleMargins: { top: 0.82, bottom: 0 }
  });

  // Moving Average Lines (EMA 9, EMA 21, EMA 50)
  ema9Series = mainChart.addLineSeries({
    color: "#2196f3",
    lineWidth: 1.5,
    title: "EMA 9",
    priceLineVisible: false,
    lastValueVisible: false
  });

  ema21Series = mainChart.addLineSeries({
    color: "#ff9800",
    lineWidth: 1.5,
    title: "EMA 21",
    priceLineVisible: false,
    lastValueVisible: false
  });

  ema50Series = mainChart.addLineSeries({
    color: "#ab47bc",
    lineWidth: 1.5,
    title: "EMA 50",
    priceLineVisible: false,
    lastValueVisible: false
  });

  // 2. PANE 2: RSI 14 Momentum Chart
  if (rsiContainer) {
    rsiChart = LightweightCharts.createChart(rsiContainer, {
      ...commonOptions,
      timeScale: { borderColor: "#1e222d", visible: false },
      rightPriceScale: { borderColor: "#1e222d", scaleMargins: { top: 0.1, bottom: 0.1 } }
    });

    rsiSeries = rsiChart.addLineSeries({
      color: "#ab47bc",
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: true
    });

    // Reference lines for Overbought (70), Midline (50), Oversold (30)
    rsiSeries.createPriceLine({
      price: 70,
      color: "rgba(239, 83, 80, 0.6)",
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dotted,
      axisLabelVisible: true,
      title: "70"
    });
    rsiSeries.createPriceLine({
      price: 50,
      color: "rgba(120, 123, 134, 0.35)",
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dotted,
      axisLabelVisible: false
    });
    rsiSeries.createPriceLine({
      price: 30,
      color: "rgba(38, 166, 154, 0.6)",
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dotted,
      axisLabelVisible: true,
      title: "30"
    });
  }

  // 3. PANE 3: MACD (12, 26, 9) Oscillator Chart
  if (macdContainer) {
    macdChart = LightweightCharts.createChart(macdContainer, {
      ...commonOptions,
      timeScale: { borderColor: "#1e222d", visible: true },
      rightPriceScale: { borderColor: "#1e222d", scaleMargins: { top: 0.1, bottom: 0.1 } }
    });

    // Histogram Series
    macdHistSeries = macdChart.addHistogramSeries({
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      priceLineVisible: false,
      lastValueVisible: false
    });

    // MACD Line
    macdLineSeries = macdChart.addLineSeries({
      color: "#2196f3",
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: true
    });

    // Signal Line
    signalLineSeries = macdChart.addLineSeries({
      color: "#ff9800",
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: true
    });

    // Zero baseline
    macdHistSeries.createPriceLine({
      price: 0,
      color: "rgba(120, 123, 134, 0.5)",
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Solid,
      axisLabelVisible: true,
      title: "0"
    });
  }

  // Synchronize All 3 Time Scales
  syncTimeScales([mainChart, rsiChart, macdChart]);

  // Dynamic Crosshair Hover Legend
  mainChart.subscribeCrosshairMove(param => updateLegendOnHover(param));

  // Fit Data button
  const fitBtn = document.getElementById("btn-fit-chart");
  if (fitBtn) {
    fitBtn.addEventListener("click", () => fitAllCharts());
  }

  resizeCharts();
}

function syncTimeScales(charts) {
  const validCharts = charts.filter(Boolean);
  validCharts.forEach(sourceChart => {
    sourceChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (isSyncingRange || !range) return;
      isSyncingRange = true;
      validCharts.forEach(targetChart => {
        if (targetChart !== sourceChart) {
          targetChart.timeScale().setVisibleLogicalRange(range);
        }
      });
      isSyncingRange = false;
    });
  });
}

function fitAllCharts() {
  if (mainChart) mainChart.timeScale().fitContent();
  if (rsiChart) rsiChart.timeScale().fitContent();
  if (macdChart) macdChart.timeScale().fitContent();
}

// In-Chart Dynamic Hover Legend
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
  const macdLineEl = document.getElementById("leg-macd-line");
  const signalLineEl = document.getElementById("leg-macd-signal");
  const macdHistEl = document.getElementById("leg-macd-hist");

  if (!param || !param.time || !param.seriesData) {
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

  const e9 = param.seriesData.get(ema9Series);
  if (e9 && ema9El) ema9El.innerText = e9.value ? e9.value.toFixed(1) : "---";

  const e21 = param.seriesData.get(ema21Series);
  if (e21 && ema21El) ema21El.innerText = e21.value ? e21.value.toFixed(1) : "---";

  const e50 = param.seriesData.get(ema50Series);
  if (e50 && ema50El) ema50El.innerText = e50.value ? e50.value.toFixed(1) : "---";

  // RSI and MACD for hovered bar
  if (param.time && chartData.length > 0) {
    const item = chartData.find(d => d.date === param.time);
    if (item) {
      if (rsiEl) rsiEl.innerText = item.rsi_14 ? item.rsi_14.toFixed(1) : "---";
      if (macdLineEl) macdLineEl.innerText = item.macd_line != null ? item.macd_line.toFixed(2) : "---";
      if (signalLineEl) signalLineEl.innerText = item.macd_signal != null ? item.macd_signal.toFixed(2) : "---";
      if (macdHistEl) macdHistEl.innerText = item.macd_histogram != null ? item.macd_histogram.toFixed(2) : "---";
    }
  }
}

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
  const macdLineEl = document.getElementById("leg-macd-line");
  const signalLineEl = document.getElementById("leg-macd-signal");
  const macdHistEl = document.getElementById("leg-macd-hist");

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
  if (macdLineEl) macdLineEl.innerText = last.macd_line != null ? last.macd_line.toFixed(2) : "---";
  if (signalLineEl) signalLineEl.innerText = last.macd_signal != null ? last.macd_signal.toFixed(2) : "---";
  if (macdHistEl) macdHistEl.innerText = last.macd_histogram != null ? last.macd_histogram.toFixed(2) : "---";
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

// Fetch Market Status
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

// Fetch Market Summary & All Shares Table (StockNow Style)
async function fetchMarketSummary() {
  try {
    const res = await fetch("/market/summary");
    if (!res.ok) return;
    const data = await res.json();

    const adv = data.advancers || 0;
    const dec = data.decliners || 0;
    const unch = data.unchanged || 0;

    const breadthEl = document.getElementById("market-breadth");
    if (breadthEl) {
      breadthEl.innerHTML = `
        <span class="positive">▲ ${adv}</span>
        <span class="negative">▼ ${dec}</span>
        <span style="color:#787b86">● ${unch}</span>
      `;
    }

    if (data.top_gainers) {
      allSharesData = data.top_gainers;
      filterWatchlistCategory("all");
    }
  } catch (err) {
    console.error("Market summary fetch error:", err);
  }
}

function filterWatchlistCategory(cat) {
  let list = [...allSharesData];
  if (cat === "gainers") list = list.filter(s => s.change_pct > 0);
  if (cat === "losers") list = list.filter(s => s.change_pct < 0);

  const countPill = document.getElementById("shares-count-pill");
  if (countPill) countPill.innerText = `${list.length} Items`;

  const tbody = document.getElementById("shares-table-body");
  if (!tbody) return;

  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="3" class="loading-td">No tickers in category</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(s => `
    <tr class="shares-row ${s.symbol === currentSymbol ? 'active' : ''}" onclick="selectSymbol('${s.symbol}')">
      <td class="td-code">${s.symbol}</td>
      <td class="td-last">৳${s.close.toFixed(1)}</td>
      <td class="td-chg ${s.change_pct >= 0 ? 'positive' : 'negative'}">
        ${s.change_pct >= 0 ? '+' : ''}${s.change_pct.toFixed(2)}%
      </td>
    </tr>
  `).join("");
}

// Load Stock Data & Feed to Lightweight Charts
async function loadStockData(symbol) {
  currentSymbol = symbol;
  const searchInput = document.getElementById("symbol-search-input");
  if (searchInput) searchInput.value = symbol;

  try {
    const [anaRes, sigRes, indRes] = await Promise.all([
      fetch(`/analysis/${symbol}`),
      fetch(`/signals/${symbol}`),
      fetch(`/indicators/${symbol}?limit=120`)
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
  document.querySelectorAll(".shares-row").forEach(tr => {
    tr.classList.toggle("active", tr.querySelector(".td-code")?.innerText === sym);
  });
}

function updateStockHeader(ana) {
  const symEl = document.getElementById("active-symbol");
  const changeEl = document.getElementById("active-change");

  if (symEl) symEl.innerText = ana.symbol;
  if (changeEl) {
    const chg = ana.price.change;
    const pct = ana.price.change_pct;
    changeEl.className = `legend-change ${pct >= 0 ? 'positive' : 'negative'}`;
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
    trendEl.className = `lvl-val ${ana.trend === 'Bullish' ? 'positive' : (ana.trend === 'Bearish' ? 'negative' : '')}`;
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
    badge.className = `signal-status-badge ${sig.signal.includes('BUY') ? 'signal-buy' : (sig.signal.includes('SELL') ? 'signal-sell' : 'signal-hold')}`;
  }
  if (conf) conf.innerText = `${sig.confidence}%`;
  if (target) target.innerText = `৳${sig.target.toFixed(1)}`;
  if (sl) sl.innerText = `৳${sig.stop_loss.toFixed(1)}`;
  if (rrr) rrr.innerText = `1:${sig.risk_reward_ratio}`;

  if (reasonsEl && sig.reasons) {
    reasonsEl.innerHTML = sig.reasons.map(r => `<li>${r}</li>`).join("");
  }
}

// Render TradingView Candlesticks, Indicators & S&R Price Lines
function renderChart(data, levels = currentLevels) {
  if (!mainChart || !candleSeries || !data || data.length === 0) return;

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
      rsi_14: item.rsi_14,
      macd_line: item.macd_line,
      macd_signal: item.macd_signal,
      macd_histogram: item.macd_histogram
    });
  }

  if (cleanData.length === 0) return;

  // 1. Candlestick Data
  candleSeries.setData(cleanData.map(d => ({
    time: d.date,
    open: d.open,
    high: d.high,
    low: d.low,
    close: d.close
  })));

  // 2. Volume Histogram Overlay
  if (volumeSeries) {
    volumeSeries.setData(cleanData.map(d => ({
      time: d.date,
      value: d.volume,
      color: d.close >= d.open ? "rgba(38, 166, 154, 0.4)" : "rgba(239, 83, 80, 0.4)"
    })));
  }

  // 3. EMA Line series
  if (ema9Series) ema9Series.setData(cleanData.filter(d => d.ema_9).map(d => ({ time: d.date, value: d.ema_9 })));
  if (ema21Series) ema21Series.setData(cleanData.filter(d => d.ema_21).map(d => ({ time: d.date, value: d.ema_21 })));
  if (ema50Series) ema50Series.setData(cleanData.filter(d => d.ema_50).map(d => ({ time: d.date, value: d.ema_50 })));

  // 4. RSI Data
  if (rsiSeries) rsiSeries.setData(cleanData.filter(d => d.rsi_14).map(d => ({ time: d.date, value: d.rsi_14 })));

  // 5. MACD Data (Line, Signal, Histogram)
  if (macdLineSeries) macdLineSeries.setData(cleanData.filter(d => d.macd_line != null).map(d => ({ time: d.date, value: d.macd_line })));
  if (signalLineSeries) signalLineSeries.setData(cleanData.filter(d => d.macd_signal != null).map(d => ({ time: d.date, value: d.macd_signal })));
  if (macdHistSeries) {
    macdHistSeries.setData(cleanData.filter(d => d.macd_histogram != null).map(d => ({
      time: d.date,
      value: d.macd_histogram,
      color: d.macd_histogram >= 0 ? "rgba(38, 166, 154, 0.8)" : "rgba(239, 83, 80, 0.8)"
    })));
  }

  // 6. Native S&R Price Lines with Axis Badges
  activePriceLines.forEach(l => {
    try { candleSeries.removePriceLine(l); } catch (e) {}
  });
  activePriceLines = [];

  if (levels) {
    if (levels.resistance_1) {
      activePriceLines.push(candleSeries.createPriceLine({
        price: levels.resistance_1,
        color: "#ef5350",
        lineWidth: 1.5,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: `R1 ${levels.resistance_1.toFixed(1)}`
      }));
    }
    if (levels.support_1) {
      activePriceLines.push(candleSeries.createPriceLine({
        price: levels.support_1,
        color: "#26a69a",
        lineWidth: 1.5,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: `S1 ${levels.support_1.toFixed(1)}`
      }));
    }
    if (levels.pivot) {
      activePriceLines.push(candleSeries.createPriceLine({
        price: levels.pivot,
        color: "#ff9800",
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dotted,
        axisLabelVisible: true,
        title: `P ${levels.pivot.toFixed(1)}`
      }));
    }
  }

  fitAllCharts();
  setLegendToLatest();
}

function resizeCharts() {
  const p1 = document.getElementById("priceChart");
  if (mainChart && p1) {
    mainChart.applyOptions({ width: p1.clientWidth, height: p1.clientHeight });
  }

  const p2 = document.getElementById("tv-rsi-chart");
  if (rsiChart && p2) {
    rsiChart.applyOptions({ width: p2.clientWidth, height: p2.clientHeight });
  }

  const p3 = document.getElementById("tv-macd-chart");
  if (macdChart && p3) {
    macdChart.applyOptions({ width: p3.clientWidth, height: p3.clientHeight });
  }
}
window.addEventListener("resize", resizeCharts);

// Quick Order Quantity & Cost Calculation
function setQuickQty(qty) {
  const input = document.getElementById("order-qty");
  if (input) {
    input.value = qty;
    calculateEstCost();
  }
}

function calculateEstCost() {
  const qtyInput = document.getElementById("order-qty");
  const costEl = document.getElementById("order-est-cost");
  if (!qtyInput || !costEl) return;

  const qty = parseInt(qtyInput.value) || 0;
  const cost = currentPrice * qty;
  costEl.innerText = `BDT ৳${cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// Paper Trading Order Execution
async function executePaperOrder(side) {
  const qtyInput = document.getElementById("order-qty");
  const qty = parseInt(qtyInput ? qtyInput.value : 10) || 10;

  try {
    const res = await fetch(`/paper/order?account_id=default&symbol=${currentSymbol}&side=${side}&quantity=${qty}`, {
      method: "POST"
    });
    const data = await res.json();
    if (res.ok) {
      alert(`✅ Order ${side} ${qty} ${currentSymbol} executed!\nFill Price: ৳${data.fill_price.toFixed(1)}`);
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
