// DSE Market Signal - TradingView-Style Interactive Dashboard

let currentSymbol = "GP";
let chartData = [];
let currentLevels = null;

// Initialize dashboard on load
document.addEventListener("DOMContentLoaded", () => {
  setupSidebarToggles();
  fetchSystemHealth();
  fetchMarketStatus();
  fetchMarketSummary();
  loadStockData(currentSymbol);
  fetchPortfolio();

  // Polling intervals
  setInterval(fetchSystemHealth, 30000);
  setInterval(fetchMarketStatus, 60000);
});

// Sidebar Toggle Handlers
function setupSidebarToggles() {
  const toggleLeft = document.getElementById("toggle-left");
  const toggleRight = document.getElementById("toggle-right");
  const leftSidebar = document.getElementById("left-sidebar");
  const rightSidebar = document.getElementById("right-sidebar");

  if (toggleLeft && leftSidebar) {
    toggleLeft.addEventListener("click", () => {
      leftSidebar.classList.toggle("hidden");
      toggleLeft.innerText = leftSidebar.classList.contains("hidden") ? "Show Left" : "Hide Left";
      resizeChart();
    });
  }

  if (toggleRight && rightSidebar) {
    toggleRight.addEventListener("click", () => {
      rightSidebar.classList.toggle("hidden");
      toggleRight.innerText = rightSidebar.classList.contains("hidden") ? "Show Right" : "Hide Right";
      resizeChart();
    });
  }
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
      healthBadge.innerHTML = `<span style="color:#089981">●</span> Backend Healthy`;
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

    const breadthEl = document.getElementById("market-breadth");
    if (breadthEl) {
      breadthEl.innerHTML = `
        <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:6px;">
          <span class="positive">▲ ${data.advancers} Adv</span>
          <span class="negative">▼ ${data.decliners} Dec</span>
          <span>● ${data.unchanged} Unch</span>
        </div>
      `;
    }

    const watchlistEl = document.getElementById("watchlist-items");
    if (watchlistEl && data.top_gainers) {
      watchlistEl.innerHTML = data.top_gainers.map(s => `
        <div class="watchlist-item ${s.symbol === currentSymbol ? 'active' : ''}" onclick="selectSymbol('${s.symbol}')">
          <div>
            <strong>${s.symbol}</strong>
            <div style="font-size:11px; color:var(--text-secondary)">Vol: ${Math.round(s.volume).toLocaleString()}</div>
          </div>
          <div style="text-align:right">
            <div>BDT ${s.close.toFixed(1)}</div>
            <div class="${s.change_pct >= 0 ? 'positive' : 'negative'}" style="font-size:11px">
              ${s.change_pct >= 0 ? '+' : ''}${s.change_pct.toFixed(2)}%
            </div>
          </div>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Market summary fetch error:", err);
  }
}

// Load Stock Data & Chart
async function loadStockData(symbol) {
  currentSymbol = symbol;
  try {
    // Fetch technical analysis & signal
    const [anaRes, sigRes, indRes] = await Promise.all([
      fetch(`/analysis/${symbol}`),
      fetch(`/signals/${symbol}`),
      fetch(`/indicators/${symbol}?limit=60`)
    ]);

    let levels = null;
    if (anaRes.ok) {
      const ana = await anaRes.json();
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
  } catch (err) {
    console.error("Error loading stock:", err);
  }
}

function selectSymbol(sym) {
  loadStockData(sym);
  const items = document.querySelectorAll(".watchlist-item");
  items.forEach(el => el.classList.remove("active"));
}

function updateStockHeader(ana) {
  const symEl = document.getElementById("active-symbol");
  const priceEl = document.getElementById("active-price");
  const changeEl = document.getElementById("active-change");

  if (symEl) symEl.innerText = ana.symbol;
  if (priceEl) priceEl.innerText = `BDT ${ana.price.close.toFixed(1)}`;
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
  if (pivotEl) pivotEl.innerText = ana.levels.pivot.toFixed(1);
  if (s1El) s1El.innerText = ana.levels.support_1.toFixed(1);
  if (r1El) r1El.innerText = ana.levels.resistance_1.toFixed(1);
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
  if (target) target.innerText = `BDT ${sig.target.toFixed(1)}`;
  if (sl) sl.innerText = `BDT ${sig.stop_loss.toFixed(1)}`;
  if (rrr) rrr.innerText = `1:${sig.risk_reward_ratio}`;

  if (reasonsEl && sig.reasons) {
    reasonsEl.innerHTML = sig.reasons.map(r => `<li>${r}</li>`).join("");
  }
}

// Interactive HTML5 Canvas Candlestick & Technical Chart
function renderChart(data, levels = currentLevels) {
  const canvas = document.getElementById("priceChart");
  if (!canvas || !data || data.length === 0) return;

  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * window.devicePixelRatio;
  canvas.height = rect.height * window.devicePixelRatio;
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

  const w = rect.width;
  const h = rect.height;

  // Split canvas: Top 70% Price & MA/Bollinger, Bottom 30% RSI
  const priceH = h * 0.70;
  const rsiH = h * 0.25;
  const rsiTop = h * 0.75;

  ctx.clearRect(0, 0, w, h);

  // Calculate Price Scaling including indicators & support/resistance levels
  const prices = [];
  data.forEach(d => {
    const c = d.close;
    const h = d.high > 0 ? d.high : c;
    const l = d.low > 0 ? d.low : c;
    prices.push(h, l);
    if (d.bb_upper && d.bb_upper > 0) prices.push(d.bb_upper);
    if (d.bb_lower && d.bb_lower > 0) prices.push(d.bb_lower);
  });
  if (levels && levels.resistance_1 && levels.resistance_1 > 0) prices.push(levels.resistance_1);
  if (levels && levels.support_1 && levels.support_1 > 0) prices.push(levels.support_1);
  if (levels && levels.pivot && levels.pivot > 0) prices.push(levels.pivot);

  const validPrices = prices.filter(p => p > 0);
  const minP = validPrices.length ? Math.min(...validPrices) * 0.99 : 100;
  const maxP = validPrices.length ? Math.max(...validPrices) * 1.01 : 300;
  const pRange = maxP - minP || 1;

  const getY = (val) => priceH - ((val - minP) / pRange * (priceH - 20)) - 10;
  const getRsiY = (rsiVal) => rsiTop + rsiH - (rsiVal / 100 * rsiH);

  const n = data.length;
  const candleW = Math.max(3, (w - 60) / n * 0.65);
  const step = (w - 60) / n;

  // Grid lines
  ctx.strokeStyle = "#2a2e39";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = 10 + (priceH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w - 50, y);
    ctx.stroke();

    const priceLabel = (maxP - (pRange / 4) * i).toFixed(1);
    ctx.fillStyle = "#787b86";
    ctx.font = "10px sans-serif";
    ctx.fillText(priceLabel, w - 45, y + 3);
  }

  // Draw Candlesticks
  data.forEach((d, i) => {
    const x = 20 + i * step;
    const close = d.close;
    const open = d.open > 0 ? d.open : close;
    const high = Math.max(d.high > 0 ? d.high : close, Math.max(open, close));
    const low = Math.min(d.low > 0 ? d.low : close, Math.min(open, close));
    const isBull = close >= open;
    const color = isBull ? "#089981" : "#f23645";

    // Wick
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x, getY(high));
    ctx.lineTo(x, getY(low));
    ctx.stroke();

    // Body
    ctx.fillStyle = color;
    const bodyTop = getY(Math.max(open, close));
    const bodyH = Math.max(2, Math.abs(getY(close) - getY(open)));
    ctx.fillRect(x - candleW / 2, bodyTop, candleW, bodyH);
  });

  // Draw EMA Lines (EMA 9: Blue, EMA 21: Orange, EMA 50: Purple)
  drawIndicatorLine(ctx, data, "ema_9", getY, step, "#2962ff");
  drawIndicatorLine(ctx, data, "ema_21", getY, step, "#ff9800");
  drawIndicatorLine(ctx, data, "ema_50", getY, step, "#ab47bc");

  // Draw Support, Resistance & Pivot Reference Lines
  if (levels) {
    // Resistance 1 (R1) - Red dashed line with badge
    if (levels.resistance_1) {
      const rY = getY(levels.resistance_1);
      if (rY >= 5 && rY <= priceH - 5) {
        ctx.save();
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = "#ef5350";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(0, rY);
        ctx.lineTo(w - 60, rY);
        ctx.stroke();

        ctx.fillStyle = "#ef5350";
        ctx.fillRect(w - 60, rY - 7, 56, 14);
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 9px sans-serif";
        ctx.fillText(`R1 ${levels.resistance_1.toFixed(1)}`, w - 57, rY + 4);
        ctx.restore();
      }
    }

    // Support 1 (S1) - Green dashed line with badge
    if (levels.support_1) {
      const sY = getY(levels.support_1);
      if (sY >= 5 && sY <= priceH - 5) {
        ctx.save();
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = "#089981";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(0, sY);
        ctx.lineTo(w - 60, sY);
        ctx.stroke();

        ctx.fillStyle = "#089981";
        ctx.fillRect(w - 60, sY - 7, 56, 14);
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 9px sans-serif";
        ctx.fillText(`S1 ${levels.support_1.toFixed(1)}`, w - 57, sY + 4);
        ctx.restore();
      }
    }

    // Classic Pivot - Gold dashed line with label
    if (levels.pivot) {
      const pY = getY(levels.pivot);
      if (pY >= 5 && pY <= priceH - 5) {
        ctx.save();
        ctx.setLineDash([2, 4]);
        ctx.strokeStyle = "#f0b90b99";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, pY);
        ctx.lineTo(w - 60, pY);
        ctx.stroke();

        ctx.fillStyle = "#f0b90b";
        ctx.font = "9px sans-serif";
        ctx.fillText(`P ${levels.pivot.toFixed(1)}`, w - 50, pY + 3);
        ctx.restore();
      }
    }
  }

  // RSI Subpanel
  ctx.strokeStyle = "#363c4e";
  ctx.beginPath();
  ctx.moveTo(0, rsiTop);
  ctx.lineTo(w, rsiTop);
  ctx.stroke();

  // RSI 70/30 guides
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = "#787b86";
  ctx.beginPath();
  ctx.moveTo(0, getRsiY(70));
  ctx.lineTo(w - 50, getRsiY(70));
  ctx.moveTo(0, getRsiY(30));
  ctx.lineTo(w - 50, getRsiY(30));
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = "#787b86";
  ctx.fillText("70", w - 45, getRsiY(70) + 3);
  ctx.fillText("30", w - 45, getRsiY(30) + 3);

  // RSI Line
  ctx.strokeStyle = "#9c27b0";
  ctx.lineWidth = 1.8;
  ctx.beginPath();
  data.forEach((d, i) => {
    const x = 20 + i * step;
    const y = getRsiY(d.rsi_14 || 50);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function drawIndicatorLine(ctx, data, field, getY, step, color) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  let started = false;
  data.forEach((d, i) => {
    if (d[field] && d[field] > 0) {
      const x = 20 + i * step;
      const y = getY(d[field]);
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
  });
  ctx.stroke();
}

function resizeChart() {
  setTimeout(() => renderChart(chartData, currentLevels), 100);
}
window.addEventListener("resize", resizeChart);

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
      alert(`Order ${side} ${qty} ${currentSymbol} executed successfully!`);
      fetchPortfolio();
    } else {
      alert(`Order failed: ${data.detail || 'Error'}`);
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

    if (cashEl) cashEl.innerText = `BDT ${data.cash_balance.toLocaleString()}`;
    if (equityEl) equityEl.innerText = `BDT ${data.total_equity.toLocaleString()}`;
    if (pnlEl) {
      pnlEl.innerText = `${data.total_pnl >= 0 ? '+' : ''}${data.total_pnl.toFixed(1)} (${data.total_return_pct.toFixed(2)}%)`;
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
      alert(`Telegram Alert dispatched (${data.notification.status}):\n${data.notification.preview || 'Sent!'}`);
    } else {
      alert("Notification failed");
    }
  } catch (err) {
    alert("Alert error: " + err);
  }
}

