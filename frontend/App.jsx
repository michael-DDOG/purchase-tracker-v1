const { useState, useEffect, useCallback, useRef } = React;
const { Camera, Upload, DollarSign, TrendingUp, Package, AlertTriangle, CheckCircle, Clock, X, Plus, Search, Filter, ChevronRight, RefreshCw, LogOut, BarChart3, ShoppingCart, Home, Users, Lightbulb, ExternalLink, ChevronDown, ArrowUpRight, ArrowDownRight, Moon, Sun, Download, FileText, AlertCircle, Truck, Eye, Star, RotateCcw, Archive, Percent, Shield, Calendar, Trash2 } = lucideReact;

// API Configuration - relative path for production, respects proxy in dev
const API_BASE = '/api';

// Auth helpers
const getToken = () => localStorage.getItem('auth_token');
const setToken = (t) => localStorage.setItem('auth_token', t);
const clearToken = () => localStorage.removeItem('auth_token');

// Utility function for API calls with auth
const api = async (endpoint, options = {}) => {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...options.headers,
  };
  const response = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
  if (response.status === 401) {
    clearToken();
    window.dispatchEvent(new Event('auth-expired'));
    throw new Error('Unauthorized');
  }
  if (!response.ok) throw new Error(`API Error: ${response.status}`);
  return response.json();
};

// Download file (for CSV export) with auth
const downloadFile = async (endpoint) => {
  const token = getToken();
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
  });
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition');
  const filename = disposition ? disposition.split('filename=')[1] : 'export.csv';
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
};

// Format currency
const formatCurrency = (amount) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount || 0);

// Format date
const formatDate = (dateStr) => {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

// ==================== DARK MODE ====================
const useDarkMode = () => {
  const [dark, setDark] = useState(() => localStorage.getItem('dark_mode') === 'true');

  useEffect(() => {
    const styleId = 'dark-mode-style';
    let style = document.getElementById(styleId);
    if (dark) {
      if (!style) {
        style = document.createElement('style');
        style.id = styleId;
        document.head.appendChild(style);
      }
      style.textContent = `
        body, .min-h-screen { background-color: #111827 !important; }
        .bg-gray-50 { background-color: #111827 !important; }
        .bg-white { background-color: #1f2937 !important; }
        .text-gray-900 { color: #f9fafb !important; }
        .text-gray-800 { color: #f3f4f6 !important; }
        .text-gray-700 { color: #e5e7eb !important; }
        .text-gray-600 { color: #d1d5db !important; }
        .text-gray-500 { color: #9ca3af !important; }
        .text-gray-400 { color: #6b7280 !important; }
        .border-gray-100 { border-color: #374151 !important; }
        .border-gray-200 { border-color: #374151 !important; }
        .border-gray-300 { border-color: #4b5563 !important; }
        .border-b { border-color: #374151 !important; }
        .bg-gray-100 { background-color: #374151 !important; }
        .divide-y > * + * { border-color: #374151 !important; }
        .hover\\:bg-gray-50:hover { background-color: #374151 !important; }
        .hover\\:bg-gray-100:hover { background-color: #4b5563 !important; }
        input, select, textarea { background-color: #1f2937 !important; color: #f3f4f6 !important; border-color: #4b5563 !important; }
        .border { border-color: #374151 !important; }
        .shadow-sm { box-shadow: 0 1px 2px rgba(0,0,0,0.3) !important; }
        .bg-blue-50 { background-color: #1e3a5f !important; }
        .bg-green-50 { background-color: #1a3a2a !important; }
        .bg-yellow-50 { background-color: #3a2f1a !important; }
        .bg-red-50 { background-color: #3a1a1a !important; }
      `;
    } else if (style) {
      style.remove();
    }
    localStorage.setItem('dark_mode', String(dark));
  }, [dark]);

  return [dark, () => setDark(d => !d)];
};

// ==================== LOGIN SCREEN ====================
const LoginScreen = ({ onLogin }) => {
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!pin) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin }),
      });
      if (!res.ok) {
        setError('Invalid PIN');
        setLoading(false);
        return;
      }
      const data = await res.json();
      setToken(data.token);
      onLogin();
    } catch {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-600 to-blue-800 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl p-8 w-full max-w-sm shadow-xl">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <ShoppingCart size={32} className="text-blue-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Apple Tree</h1>
          <p className="text-gray-500 mt-1">Purchase Tracker</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Enter PIN</label>
            <input
              type="password"
              inputMode="numeric"
              pattern="[0-9]*"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              className="w-full p-4 text-center text-2xl tracking-[0.5em] border-2 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="----"
              autoFocus
              style={{ minHeight: '56px' }}
            />
          </div>
          {error && (
            <div className="text-red-600 text-sm text-center bg-red-50 p-2 rounded-lg">{error}</div>
          )}
          <button
            type="submit"
            disabled={loading || !pin}
            className="w-full py-4 bg-blue-600 text-white rounded-xl font-semibold disabled:opacity-50 hover:bg-blue-700 transition-colors"
            style={{ minHeight: '48px' }}
          >
            {loading ? 'Verifying...' : 'Unlock'}
          </button>
        </form>
      </div>
    </div>
  );
};

// ==================== SUMMARY CARD ====================
const SummaryCard = ({ title, value, icon: Icon, trend, color = 'blue' }) => {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    red: 'bg-red-50 text-red-600',
  };
  return (
    <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
      <div className="flex items-center justify-between mb-2">
        <span className="text-gray-500 text-sm font-medium">{title}</span>
        <div className={`p-2 rounded-lg ${colorClasses[color]}`}>
          <Icon size={18} />
        </div>
      </div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      {trend && <div className="text-sm text-gray-500 mt-1">{trend}</div>}
    </div>
  );
};

// ==================== BUDGET CARD ====================
const BudgetCard = ({ category, targetPercent, targetAmount, actualAmount, monthlyTotal }) => {
  const percentage = targetAmount > 0 ? (actualAmount / targetAmount) * 100 : 0;
  const isOver = percentage > 100;
  const actualPercent = monthlyTotal > 0 ? (actualAmount / monthlyTotal) * 100 : 0;
  return (
    <div className="bg-white rounded-lg p-4 border border-gray-100">
      <div className="flex justify-between items-start mb-2">
        <span className="font-medium text-gray-800">{category}</span>
        <span className={`text-sm font-medium ${isOver ? 'text-red-600' : 'text-green-600'}`}>
          {actualPercent.toFixed(1)}% of sales
        </span>
      </div>
      <div className="flex justify-between text-sm text-gray-500 mb-2">
        <span>{formatCurrency(actualAmount)} spent</span>
        <span>Target: {targetPercent}%</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all ${isOver ? 'bg-red-500' : 'bg-green-500'}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
    </div>
  );
};

// ==================== INVOICE ROW ====================
const InvoiceRow = ({ invoice, onClick }) => {
  const statusColors = {
    pending: 'bg-yellow-100 text-yellow-700',
    verified: 'bg-blue-100 text-blue-700',
    paid: 'bg-green-100 text-green-700',
    disputed: 'bg-red-100 text-red-700',
  };
  return (
    <div
      className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg cursor-pointer transition-colors"
      onClick={onClick}
      style={{ minHeight: '48px' }}
    >
      <div className="flex-1">
        <div className="font-medium text-gray-800 flex items-center gap-1.5">
          {invoice.vendor_name}
          {invoice.has_shortage && <Truck size={14} className="text-orange-500" />}
          {invoice.dispute_status === 'open' && <AlertCircle size={14} className="text-red-500" />}
        </div>
        <div className="text-sm text-gray-500">
          {invoice.invoice_number} &bull; {formatDate(invoice.invoice_date)}
        </div>
      </div>
      <div className="text-right">
        <div className="font-medium text-gray-900">{formatCurrency(invoice.total)}</div>
        <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[invoice.status]}`}>
          {invoice.status}
        </span>
      </div>
      <ChevronRight className="ml-2 text-gray-400" size={18} />
    </div>
  );
};

// ==================== SMART INSIGHTS (Recommendations) ====================
const SmartInsights = ({ recommendations, onDismiss, onAct }) => {
  if (!recommendations || recommendations.length === 0) return null;

  const typeStyles = {
    price_increase: { bg: 'bg-red-50', border: 'border-red-200', icon: ArrowUpRight, iconColor: 'text-red-500' },
    cheaper_vendor: { bg: 'bg-green-50', border: 'border-green-200', icon: DollarSign, iconColor: 'text-green-500' },
    regional_price: { bg: 'bg-green-50', border: 'border-green-200', icon: DollarSign, iconColor: 'text-green-500' },
    volume_anomaly: { bg: 'bg-yellow-50', border: 'border-yellow-200', icon: AlertTriangle, iconColor: 'text-yellow-500' },
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Lightbulb size={18} className="text-yellow-500" />
        <h2 className="text-lg font-semibold text-gray-800">Smart Insights</h2>
        <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{recommendations.length}</span>
      </div>
      {recommendations.slice(0, 5).map((rec) => {
        const style = typeStyles[rec.type] || typeStyles.volume_anomaly;
        const IconComp = style.icon;
        return (
          <div key={rec.id} className={`${style.bg} ${style.border} border rounded-xl p-4`}>
            <div className="flex items-start gap-3">
              <div className={`p-2 rounded-lg bg-white ${style.iconColor}`}>
                <IconComp size={18} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-gray-900 text-sm">{rec.title}</div>
                <div className="text-sm text-gray-600 mt-0.5">{rec.description}</div>
                {rec.potential_savings > 0 && (
                  <div className="text-sm font-medium text-green-700 mt-1">
                    Potential savings: {formatCurrency(rec.potential_savings)}
                  </div>
                )}
              </div>
            </div>
            <div className="flex gap-2 mt-3 ml-11">
              <button
                onClick={() => onAct(rec.id)}
                className="px-3 py-1.5 bg-white border rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"
                style={{ minHeight: '36px' }}
              >
                Act on it
              </button>
              <button
                onClick={() => onDismiss(rec.id)}
                className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700"
                style={{ minHeight: '36px' }}
              >
                Dismiss
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ==================== PRICE HISTORY CHART (Canvas-based) ====================
const PriceHistoryChart = ({ data }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || !data || data.length === 0) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    const pad = { top: 20, right: 20, bottom: 30, left: 50 };
    const plotW = w - pad.left - pad.right;
    const plotH = h - pad.top - pad.bottom;

    ctx.clearRect(0, 0, w, h);

    // Group by vendor
    const vendors = {};
    data.forEach((d) => {
      if (!vendors[d.vendor_name]) vendors[d.vendor_name] = [];
      vendors[d.vendor_name].push(d);
    });

    const allPrices = data.map((d) => d.price);
    const minPrice = Math.min(...allPrices) * 0.95;
    const maxPrice = Math.max(...allPrices) * 1.05;
    const allDates = data.map((d) => new Date(d.date).getTime());
    const minDate = Math.min(...allDates);
    const maxDate = Math.max(...allDates);
    const dateRange = maxDate - minDate || 1;

    const xScale = (t) => pad.left + ((t - minDate) / dateRange) * plotW;
    const yScale = (p) => pad.top + plotH - ((p - minPrice) / (maxPrice - minPrice || 1)) * plotH;

    // Grid
    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + (plotH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(w - pad.right, y);
      ctx.stroke();
      const price = maxPrice - ((maxPrice - minPrice) / 4) * i;
      ctx.fillStyle = '#6b7280';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(`$${price.toFixed(2)}`, pad.left - 5, y + 4);
    }

    // Lines per vendor
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];
    let ci = 0;
    Object.entries(vendors).forEach(([name, points]) => {
      const color = colors[ci % colors.length];
      ci++;
      points.sort((a, b) => new Date(a.date) - new Date(b.date));

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      points.forEach((p, i) => {
        const x = xScale(new Date(p.date).getTime());
        const y = yScale(p.price);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Dots
      points.forEach((p) => {
        const x = xScale(new Date(p.date).getTime());
        const y = yScale(p.price);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fill();
      });
    });

    // Legend
    ci = 0;
    let legendX = pad.left;
    ctx.font = '11px sans-serif';
    Object.keys(vendors).forEach((name) => {
      const color = colors[ci % colors.length];
      ci++;
      ctx.fillStyle = color;
      ctx.fillRect(legendX, h - 12, 12, 8);
      ctx.fillStyle = '#374151';
      ctx.textAlign = 'left';
      ctx.fillText(name, legendX + 16, h - 4);
      legendX += ctx.measureText(name).width + 30;
    });
  }, [data]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '200px' }}
      className="rounded-lg"
    />
  );
};

// ==================== VOLUME CHART (Horizontal bars) ====================
const VolumeChart = ({ data }) => {
  if (!data || data.length === 0) return <div className="text-gray-400 text-sm p-4">No volume data</div>;
  const maxVol = Math.max(...data.map((d) => d.recent_volume));

  return (
    <div className="space-y-2">
      {data.slice(0, 15).map((item) => {
        const pct = maxVol > 0 ? (item.recent_volume / maxVol) * 100 : 0;
        return (
          <div key={item.id} className="flex items-center gap-2">
            <div className="w-32 text-sm text-gray-700 truncate">{item.name}</div>
            <div className="flex-1 bg-gray-100 rounded-full h-5 relative">
              <div
                className="h-5 rounded-full bg-blue-500 transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="w-12 text-xs text-gray-600 text-right">{item.recent_volume}</div>
            <div className="w-6">
              {item.trend === 'up' && <ArrowUpRight size={14} className="text-red-500" />}
              {item.trend === 'down' && <ArrowDownRight size={14} className="text-green-500" />}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ==================== SCORE BAR ====================
const ScoreBar = ({ label, score, color = 'blue' }) => {
  const colorClass = score >= 80 ? 'bg-green-500' : score >= 50 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium text-gray-800">{score}/100</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2.5">
        <div className={`h-2.5 rounded-full ${colorClass} transition-all`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
};

// ==================== INVOICE DETAIL MODAL ====================
const InvoiceDetailModal = ({ invoice, onClose, onRefresh }) => {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [shortageMode, setShortageMode] = useState(false);
  const [receivedQtys, setReceivedQtys] = useState({});
  const [disputeReason, setDisputeReason] = useState('');
  const [showDispute, setShowDispute] = useState(false);
  const [imageUrl, setImageUrl] = useState(null);
  const [saving, setSaving] = useState(false);
  const [showResolve, setShowResolve] = useState(false);
  const [creditAmount, setCreditAmount] = useState('');

  useEffect(() => {
    if (!invoice) return;
    setLoading(true);
    Promise.all([
      api(`/invoices/${invoice.id}`),
      api(`/invoices/${invoice.id}/image`).catch(() => null),
    ]).then(([inv, img]) => {
      setDetail(inv);
      if (img?.image_path) setImageUrl(`/uploads/${img.image_path.split('/').pop()}`);
      // Initialize received quantities
      const qtys = {};
      inv.items?.forEach(item => {
        qtys[item.id] = item.received_quantity !== null ? item.received_quantity : item.quantity;
      });
      setReceivedQtys(qtys);
    }).finally(() => setLoading(false));
  }, [invoice]);

  const saveShortages = async () => {
    setSaving(true);
    try {
      const items = Object.entries(receivedQtys).map(([item_id, received_quantity]) => ({
        item_id: parseInt(item_id),
        received_quantity: parseFloat(received_quantity),
      }));
      await api(`/invoices/${invoice.id}/shortages`, {
        method: 'PUT',
        body: JSON.stringify({ items }),
      });
      setShortageMode(false);
      onRefresh();
    } catch (err) {
      alert('Failed to save shortages');
    } finally {
      setSaving(false);
    }
  };

  const submitDispute = async () => {
    if (!disputeReason.trim()) return;
    setSaving(true);
    try {
      const disputedItemIds = detail.items
        ?.filter(item => item.is_disputed)
        .map(item => item.id) || [];
      await api('/invoices/dispute', {
        method: 'POST',
        body: JSON.stringify({
          invoice_id: invoice.id,
          reason: disputeReason,
          item_ids: disputedItemIds,
        }),
      });
      setShowDispute(false);
      setDisputeReason('');
      onRefresh();
    } catch (err) {
      alert('Failed to create dispute');
    } finally {
      setSaving(false);
    }
  };

  const updateStatus = async (status) => {
    try {
      await api(`/invoices/${invoice.id}/status?status=${status}`, { method: 'PUT' });
      onRefresh();
    } catch (err) {
      alert('Failed to update status');
    }
  };

  const resolveDispute = async () => {
    setSaving(true);
    try {
      const credit = parseFloat(creditAmount) || 0;
      await api(`/invoices/${invoice.id}/dispute/resolve?credit_amount=${credit}`, { method: 'PUT' });
      setShowResolve(false);
      setCreditAmount('');
      onRefresh();
    } catch (err) {
      alert('Failed to resolve dispute');
    } finally {
      setSaving(false);
    }
  };

  if (!invoice) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center">
      <div className="bg-white rounded-t-2xl sm:rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b sticky top-0 bg-white z-10">
          <h3 className="font-semibold text-lg">Invoice Detail</h3>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-full" style={{ minHeight: '44px', minWidth: '44px' }}>
            <X size={20} />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <RefreshCw className="animate-spin text-blue-600" size={28} />
          </div>
        ) : detail ? (
          <div className="p-4 space-y-4">
            {/* Header info */}
            <div className="flex justify-between items-start">
              <div>
                <div className="font-semibold text-gray-900 text-lg">{detail.vendor_name}</div>
                <div className="text-sm text-gray-500">{detail.invoice_number || 'No number'}</div>
                <div className="text-sm text-gray-500">{formatDate(detail.invoice_date)}</div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-gray-900">{formatCurrency(detail.total)}</div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  detail.status === 'paid' ? 'bg-green-100 text-green-700' :
                  detail.status === 'disputed' ? 'bg-red-100 text-red-700' :
                  detail.status === 'verified' ? 'bg-blue-100 text-blue-700' :
                  'bg-yellow-100 text-yellow-700'
                }`}>{detail.status}</span>
              </div>
            </div>

            {/* Shortage banner */}
            {detail.has_shortage && (
              <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 flex items-center gap-2">
                <Truck size={18} className="text-orange-500" />
                <span className="text-sm text-orange-700 font-medium">
                  Shortage: {formatCurrency(detail.shortage_total)} missing
                </span>
              </div>
            )}

            {/* Dispute banner with resolve */}
            {detail.dispute_status === 'open' && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <AlertCircle size={18} className="text-red-500" />
                    <span className="text-sm text-red-700 font-medium">Dispute open</span>
                  </div>
                  {!showResolve && (
                    <button
                      onClick={() => setShowResolve(true)}
                      className="text-xs px-3 py-1.5 bg-white border border-red-200 text-red-600 rounded-lg font-medium"
                      style={{ minHeight: '32px' }}
                    >
                      Resolve
                    </button>
                  )}
                </div>
                {detail.dispute_reason && (
                  <div className="text-xs text-red-600 mt-1">Reason: {detail.dispute_reason}</div>
                )}
                {showResolve && (
                  <div className="mt-3 space-y-2">
                    <div>
                      <label className="text-xs text-gray-600">Credit Amount (0 if no credit)</label>
                      <div className="relative mt-1">
                        <span className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
                        <input
                          type="number"
                          step="0.01"
                          value={creditAmount}
                          onChange={(e) => setCreditAmount(e.target.value)}
                          placeholder="0.00"
                          className="w-full pl-6 p-2 border rounded-lg text-sm"
                        />
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => setShowResolve(false)} className="flex-1 py-2 border rounded-lg text-xs" style={{ minHeight: '36px' }}>Cancel</button>
                      <button onClick={resolveDispute} disabled={saving} className="flex-1 py-2 bg-green-600 text-white rounded-lg text-xs disabled:opacity-50" style={{ minHeight: '36px' }}>
                        {saving ? 'Resolving...' : creditAmount ? `Resolve + Credit ${formatCurrency(parseFloat(creditAmount) || 0)}` : 'Resolve (No Credit)'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Invoice photo */}
            {imageUrl && (
              <div>
                <div className="text-sm font-medium text-gray-700 mb-1">Invoice Photo</div>
                <img src={imageUrl} alt="Invoice" className="w-full rounded-lg border max-h-60 object-contain" />
              </div>
            )}

            {/* Line items */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">Items ({detail.items?.length || 0})</span>
                {!shortageMode && (
                  <button
                    onClick={() => setShortageMode(true)}
                    className="text-xs text-blue-600 font-medium flex items-center gap-1"
                    style={{ minHeight: '36px' }}
                  >
                    <Truck size={14} /> Mark Shortages
                  </button>
                )}
              </div>
              <div className="border rounded-lg divide-y">
                {detail.items?.map((item) => {
                  const shortage = item.received_quantity !== null
                    ? Math.max(0, item.quantity - item.received_quantity) : 0;
                  return (
                    <div key={item.id} className="p-3">
                      <div className="flex justify-between items-start">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-800 truncate">
                            {item.product_name}
                            {item.is_disputed && <span className="ml-1 text-xs text-red-500">(disputed)</span>}
                          </div>
                          <div className="text-xs text-gray-500">
                            {item.quantity} {item.unit || 'ea'} x {formatCurrency(item.unit_price)}
                          </div>
                        </div>
                        <div className="text-sm font-medium text-gray-900 ml-2">
                          {formatCurrency(item.total_price)}
                        </div>
                      </div>
                      {shortageMode && (
                        <div className="mt-2 flex items-center gap-2">
                          <label className="text-xs text-gray-500">Received:</label>
                          <input
                            type="number"
                            step="0.01"
                            value={receivedQtys[item.id] ?? item.quantity}
                            onChange={(e) => setReceivedQtys(prev => ({ ...prev, [item.id]: e.target.value }))}
                            className="w-20 px-2 py-1 text-sm border rounded"
                          />
                          <span className="text-xs text-gray-500">/ {item.quantity}</span>
                        </div>
                      )}
                      {!shortageMode && shortage > 0 && (
                        <div className="text-xs text-orange-600 mt-1">
                          Short: {shortage} {item.unit || 'ea'} ({formatCurrency(shortage * item.unit_price)})
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Shortage save button */}
            {shortageMode && (
              <div className="flex gap-2">
                <button onClick={() => setShortageMode(false)} className="flex-1 py-2.5 border rounded-xl text-sm font-medium" style={{ minHeight: '44px' }}>Cancel</button>
                <button onClick={saveShortages} disabled={saving} className="flex-1 py-2.5 bg-orange-500 text-white rounded-xl text-sm font-medium disabled:opacity-50" style={{ minHeight: '44px' }}>
                  {saving ? 'Saving...' : 'Save Shortages'}
                </button>
              </div>
            )}

            {/* Dispute form */}
            {showDispute && (
              <div className="border rounded-lg p-3 space-y-2">
                <div className="text-sm font-medium text-gray-700">Dispute Reason</div>
                <textarea
                  value={disputeReason}
                  onChange={(e) => setDisputeReason(e.target.value)}
                  placeholder="Describe the issue..."
                  className="w-full p-2 border rounded-lg text-sm"
                  rows={3}
                />
                <div className="flex gap-2">
                  <button onClick={() => setShowDispute(false)} className="flex-1 py-2 border rounded-lg text-sm" style={{ minHeight: '40px' }}>Cancel</button>
                  <button onClick={submitDispute} disabled={saving || !disputeReason.trim()} className="flex-1 py-2 bg-red-500 text-white rounded-lg text-sm disabled:opacity-50" style={{ minHeight: '40px' }}>
                    {saving ? 'Submitting...' : 'Submit Dispute'}
                  </button>
                </div>
              </div>
            )}

            {/* Action buttons */}
            {!shortageMode && !showDispute && (
              <div className="flex flex-wrap gap-2">
                {detail.status === 'pending' && (
                  <button onClick={() => updateStatus('verified')} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium" style={{ minHeight: '40px' }}>
                    <CheckCircle size={14} className="inline mr-1" /> Verify
                  </button>
                )}
                {(detail.status === 'pending' || detail.status === 'verified') && (
                  <button onClick={() => updateStatus('paid')} className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium" style={{ minHeight: '40px' }}>
                    <DollarSign size={14} className="inline mr-1" /> Mark Paid
                  </button>
                )}
                {detail.status !== 'disputed' && (
                  <button onClick={() => setShowDispute(true)} className="px-4 py-2 border border-red-300 text-red-600 rounded-lg text-sm font-medium" style={{ minHeight: '40px' }}>
                    <AlertCircle size={14} className="inline mr-1" /> Dispute
                  </button>
                )}
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
};

// ==================== VENDOR SCORECARD MODAL ====================
const VendorScorecardModal = ({ vendorId, onClose }) => {
  const [scorecard, setScorecard] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!vendorId) return;
    api(`/vendors/${vendorId}/scorecard`)
      .then(setScorecard)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [vendorId]);

  if (!vendorId) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center">
      <div className="bg-white rounded-t-2xl sm:rounded-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b sticky top-0 bg-white">
          <h3 className="font-semibold text-lg">Vendor Scorecard</h3>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-full" style={{ minHeight: '44px', minWidth: '44px' }}>
            <X size={20} />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <RefreshCw className="animate-spin text-blue-600" size={28} />
          </div>
        ) : scorecard ? (
          <div className="p-4 space-y-4">
            <div className="text-center">
              <div className="text-xl font-bold text-gray-900">{scorecard.vendor?.name}</div>
              <div className="text-sm text-gray-500">Last {scorecard.period_days} days</div>
            </div>

            {/* Overall score */}
            <div className="flex items-center justify-center">
              <div className={`w-20 h-20 rounded-full flex items-center justify-center text-white text-2xl font-bold ${
                scorecard.scores.overall >= 80 ? 'bg-green-500' :
                scorecard.scores.overall >= 50 ? 'bg-yellow-500' : 'bg-red-500'
              }`}>
                {scorecard.scores.overall}
              </div>
            </div>

            {/* Score bars */}
            <div className="space-y-3">
              <ScoreBar label="Reliability" score={scorecard.scores.reliability} />
              <ScoreBar label="Price Stability" score={scorecard.scores.price_stability} />
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-blue-50 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-blue-700">{scorecard.total_invoices}</div>
                <div className="text-xs text-blue-600">Invoices</div>
              </div>
              <div className="bg-green-50 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-green-700">{formatCurrency(scorecard.total_spent)}</div>
                <div className="text-xs text-green-600">Total Spent</div>
              </div>
              <div className="bg-gray-50 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-gray-700">{scorecard.product_count}</div>
                <div className="text-xs text-gray-600">Products</div>
              </div>
              <div className="bg-purple-50 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-purple-700">{scorecard.active_contracts}</div>
                <div className="text-xs text-purple-600">Contracts</div>
              </div>
            </div>

            {/* Issues */}
            {(scorecard.shortage_count > 0 || scorecard.disputed_count > 0 || scorecard.price_increases > 0) && (
              <div className="space-y-2">
                <div className="text-sm font-medium text-gray-700">Issues</div>
                {scorecard.shortage_count > 0 && (
                  <div className="flex items-center gap-2 text-sm text-orange-600">
                    <Truck size={14} /> {scorecard.shortage_count} delivery shortages
                  </div>
                )}
                {scorecard.disputed_count > 0 && (
                  <div className="flex items-center gap-2 text-sm text-red-600">
                    <AlertCircle size={14} /> {scorecard.disputed_count} disputes
                  </div>
                )}
                {scorecard.price_increases > 0 && (
                  <div className="flex items-center gap-2 text-sm text-yellow-600">
                    <ArrowUpRight size={14} /> {scorecard.price_increases} price increases
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="p-8 text-center text-gray-500">Failed to load scorecard</div>
        )}
      </div>
    </div>
  );
};

// ==================== PAYMENTS DUE SECTION ====================
const PaymentsDueSection = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    api('/payments/due').then(setData).catch(console.error);
  }, []);

  if (!data || (data.overdue.length === 0 && data.due_this_week.length === 0)) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Calendar size={18} className="text-blue-500" />
        <h2 className="text-lg font-semibold text-gray-800">Payments Due</h2>
      </div>

      {data.overdue.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <AlertCircle size={16} className="text-red-500" />
            <span className="text-sm font-medium text-red-700">
              {data.overdue.length} overdue ({formatCurrency(data.overdue_total)})
            </span>
          </div>
          {data.overdue.slice(0, 3).map((inv) => (
            <div key={inv.id} className="flex justify-between text-sm text-red-600 mt-1">
              <span>{inv.vendor_name}</span>
              <span>{formatCurrency(inv.total)} ({Math.abs(inv.days_until_due)}d late)</span>
            </div>
          ))}
        </div>
      )}

      {data.due_this_week.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <Clock size={16} className="text-yellow-600" />
            <span className="text-sm font-medium text-yellow-700">
              {data.due_this_week.length} due this week ({formatCurrency(data.due_this_week_total)})
            </span>
          </div>
          {data.due_this_week.slice(0, 3).map((inv) => (
            <div key={inv.id} className="flex justify-between text-sm text-yellow-700 mt-1">
              <span>{inv.vendor_name}</span>
              <span>{formatCurrency(inv.total)} (in {inv.days_until_due}d)</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ==================== CASH FLOW CHART ====================
const CashFlowChart = () => {
  const [forecast, setForecast] = useState(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    api('/analytics/cash-flow?days=30').then(setForecast).catch(console.error);
  }, []);

  useEffect(() => {
    if (!canvasRef.current || !forecast || !forecast.by_week || forecast.by_week.length === 0) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    const pad = { top: 15, right: 15, bottom: 30, left: 50 };
    const plotW = w - pad.left - pad.right;
    const plotH = h - pad.top - pad.bottom;

    ctx.clearRect(0, 0, w, h);

    const weeks = forecast.by_week;
    const maxVal = Math.max(...weeks.map(w => w.total), 1);
    const barWidth = Math.min(40, (plotW / weeks.length) * 0.7);
    const gap = (plotW - barWidth * weeks.length) / (weeks.length + 1);

    // Grid
    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 3; i++) {
      const y = pad.top + (plotH / 3) * i;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(w - pad.right, y);
      ctx.stroke();
      const val = maxVal - (maxVal / 3) * i;
      ctx.fillStyle = '#6b7280';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(`$${Math.round(val)}`, pad.left - 5, y + 4);
    }

    // Bars
    weeks.forEach((week, i) => {
      const x = pad.left + gap + i * (barWidth + gap);
      const barH = (week.total / maxVal) * plotH;
      const y = pad.top + plotH - barH;

      ctx.fillStyle = '#3b82f6';
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth, barH, 3);
      ctx.fill();

      // Label
      ctx.fillStyle = '#6b7280';
      ctx.font = '9px sans-serif';
      ctx.textAlign = 'center';
      const label = new Date(week.week_start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      ctx.fillText(label, x + barWidth / 2, h - 5);
    });
  }, [forecast]);

  if (!forecast || !forecast.by_week || forecast.by_week.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <DollarSign size={18} className="text-blue-500" />
          <h2 className="text-lg font-semibold text-gray-800">Cash Flow (30 days)</h2>
        </div>
        <span className="text-sm font-medium text-gray-600">{formatCurrency(forecast.total_due)} due</span>
      </div>
      <div className="bg-white rounded-xl p-3 border border-gray-100">
        <canvas ref={canvasRef} style={{ width: '100%', height: '150px' }} className="rounded-lg" />
      </div>
    </div>
  );
};

// ==================== REORDER ALERTS SECTION ====================
const ReorderAlerts = () => {
  const [suggestions, setSuggestions] = useState([]);

  useEffect(() => {
    api('/analytics/reorder-suggestions').then(data => {
      setSuggestions(data.filter(s => s.urgency !== 'ok').slice(0, 5));
    }).catch(console.error);
  }, []);

  if (suggestions.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <RotateCcw size={18} className="text-purple-500" />
        <h2 className="text-lg font-semibold text-gray-800">Reorder Alerts</h2>
        <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">{suggestions.length}</span>
      </div>
      {suggestions.map((s, i) => (
        <div key={i} className={`rounded-xl p-3 border ${s.urgency === 'overdue' ? 'bg-red-50 border-red-200' : 'bg-yellow-50 border-yellow-200'}`}>
          <div className="flex justify-between items-start">
            <div>
              <div className="text-sm font-medium text-gray-800">{s.product_name}</div>
              <div className="text-xs text-gray-500">
                Every ~{s.avg_order_interval_days}d from {s.last_vendor}
              </div>
            </div>
            <div className="text-right">
              <div className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                s.urgency === 'overdue' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'
              }`}>
                {s.days_overdue > 0 ? `${s.days_overdue}d overdue` : 'Due soon'}
              </div>
              {s.last_price && <div className="text-xs text-gray-500 mt-1">{formatCurrency(s.last_price)}</div>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// ==================== UPLOAD MODAL (Multi-page) ====================
const UploadModal = ({ isOpen, onClose, onSuccess }) => {
  const [files, setFiles] = useState([]);
  const [previews, setPreviews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [ocrResult, setOcrResult] = useState(null);
  const [vendors, setVendors] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selectedVendor, setSelectedVendor] = useState('');
  const [formData, setFormData] = useState({
    invoice_number: '',
    invoice_date: new Date().toISOString().split('T')[0],
    total: '',
  });
  const [editingItems, setEditingItems] = useState([]);
  const cameraRef = useRef(null);
  const galleryRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      api('/vendors').then(setVendors).catch(console.error);
      api('/categories').then(setCategories).catch(console.error);
    }
  }, [isOpen]);

  const addFiles = (newFiles) => {
    const fileArray = Array.from(newFiles);
    const total = files.length + fileArray.length;
    if (total > 10) {
      alert('Maximum 10 pages allowed');
      return;
    }
    if (total >= 5 && files.length < 5) {
      alert('Note: Large invoices may take longer to process');
    }
    const updated = [...files, ...fileArray];
    const newPreviews = fileArray.map(f => URL.createObjectURL(f));
    setFiles(updated);
    setPreviews(prev => [...prev, ...newPreviews]);
  };

  const handleCameraCapture = (e) => {
    if (e.target.files?.length) addFiles(e.target.files);
    e.target.value = '';
  };

  const handleGallerySelect = (e) => {
    if (e.target.files?.length) addFiles(e.target.files);
    e.target.value = '';
  };

  const removePage = (index) => {
    URL.revokeObjectURL(previews[index]);
    setFiles(f => f.filter((_, i) => i !== index));
    setPreviews(p => p.filter((_, i) => i !== index));
    if (files.length <= 1) setOcrResult(null);
  };

  const handleOCR = async () => {
    if (files.length === 0) return;
    setLoading(true);
    try {
      const fd = new FormData();
      const token = getToken();
      let endpoint, headers;

      if (files.length === 1) {
        fd.append('file', files[0]);
        endpoint = '/ocr/process';
      } else {
        files.forEach(f => fd.append('files', f));
        endpoint = '/ocr/process-multi';
      }
      headers = token ? { 'Authorization': `Bearer ${token}` } : {};

      const result = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers,
        body: fd,
      }).then((r) => r.json());

      setOcrResult(result);
      setEditingItems((result.line_items || []).map(item => ({ ...item, category_id: '' })));
      setFormData({
        invoice_number: result.invoice_number || '',
        invoice_date: result.invoice_date || new Date().toISOString().split('T')[0],
        total: result.total || '',
      });
      if (result.suggested_vendor_id) setSelectedVendor(result.suggested_vendor_id.toString());
    } catch (err) {
      console.error('OCR Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const updateLineItem = (index, field, value) => {
    setEditingItems(items => items.map((item, i) => i === index ? { ...item, [field]: value } : item));
  };

  const handleSubmit = async () => {
    if (!selectedVendor || !formData.total) {
      alert('Please select a vendor and enter the total');
      return;
    }
    setLoading(true);
    try {
      const items = editingItems.length > 0 ? editingItems.map(item => ({
        product_name: item.product_name,
        quantity: parseFloat(item.quantity) || 1,
        unit_price: parseFloat(item.unit_price) || 0,
        total_price: parseFloat(item.total_price) || 0,
        category_override: item.category_id ? parseInt(item.category_id) : undefined,
      })) : (ocrResult?.line_items || []);

      await api('/invoices', {
        method: 'POST',
        body: JSON.stringify({
          vendor_id: parseInt(selectedVendor),
          invoice_number: formData.invoice_number,
          invoice_date: formData.invoice_date,
          total: parseFloat(formData.total),
          items,
        }),
      });
      onSuccess();
      handleClose();
    } catch (err) {
      const msg = err.message.includes('409') ? 'Duplicate invoice detected!' : 'Failed to save invoice';
      alert(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    previews.forEach(p => URL.revokeObjectURL(p));
    setFiles([]);
    setPreviews([]);
    setOcrResult(null);
    setEditingItems([]);
    setSelectedVendor('');
    setFormData({ invoice_number: '', invoice_date: new Date().toISOString().split('T')[0], total: '' });
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">Add Invoice</h2>
          <button onClick={handleClose} className="p-2 hover:bg-gray-100 rounded-full" style={{ minHeight: '44px', minWidth: '44px' }}>
            <X size={20} />
          </button>
        </div>
        <div className="p-4 space-y-4">
          {/* Photo capture / upload area */}
          {files.length === 0 ? (
            <div className="space-y-3">
              <label className="flex flex-col items-center justify-center w-full h-36 border-2 border-dashed border-gray-300 rounded-xl cursor-pointer hover:bg-gray-50 transition-colors">
                <Camera size={36} className="text-gray-400 mb-2" />
                <span className="text-gray-600 font-medium">Take Photo</span>
                <span className="text-gray-400 text-xs mt-1">Camera capture</span>
                <input ref={cameraRef} type="file" accept="image/*" capture="environment" onChange={handleCameraCapture} className="hidden" />
              </label>
              <label className="flex flex-col items-center justify-center w-full h-24 border-2 border-dashed border-blue-200 rounded-xl cursor-pointer hover:bg-blue-50 transition-colors">
                <Upload size={24} className="text-blue-400 mb-1" />
                <span className="text-blue-600 font-medium text-sm">Choose from Gallery</span>
                <span className="text-blue-400 text-xs">Select multiple pages</span>
                <input ref={galleryRef} type="file" accept="image/*" multiple onChange={handleGallerySelect} className="hidden" />
              </label>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Thumbnail strip */}
              <div className="flex gap-2 overflow-x-auto pb-2">
                {previews.map((src, i) => (
                  <div key={i} className="relative flex-shrink-0 w-20 h-20 rounded-lg overflow-hidden border-2 border-gray-200">
                    <img src={src} alt={`Page ${i + 1}`} className="w-full h-full object-cover" />
                    <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[10px] text-center py-0.5">
                      Page {i + 1}
                    </div>
                    <button
                      onClick={() => removePage(i)}
                      className="absolute top-0 right-0 w-5 h-5 bg-red-500 text-white rounded-bl-lg flex items-center justify-center"
                    >
                      <X size={10} />
                    </button>
                  </div>
                ))}
                {files.length < 10 && (
                  <label className="flex-shrink-0 w-20 h-20 rounded-lg border-2 border-dashed border-gray-300 flex flex-col items-center justify-center cursor-pointer hover:bg-gray-50">
                    <Plus size={20} className="text-gray-400" />
                    <span className="text-[10px] text-gray-400">Add</span>
                    <input type="file" accept="image/*" capture="environment" onChange={handleCameraCapture} className="hidden" />
                  </label>
                )}
              </div>

              {/* Extract button */}
              {!ocrResult && (
                <button
                  onClick={handleOCR}
                  disabled={loading}
                  className="w-full py-3 bg-blue-600 text-white rounded-xl font-medium disabled:opacity-50 hover:bg-blue-700"
                  style={{ minHeight: '48px' }}
                >
                  {loading ? 'Extracting...' : `Extract Data (${files.length} page${files.length > 1 ? 's' : ''})`}
                </button>
              )}
            </div>
          )}

          {ocrResult && (
            <div className={`flex items-center gap-2 p-3 rounded-lg ${ocrResult.confidence_score > 0.7 ? 'bg-green-50 text-green-700' : 'bg-yellow-50 text-yellow-700'}`}>
              {ocrResult.confidence_score > 0.7 ? <CheckCircle size={18} /> : <AlertTriangle size={18} />}
              <span>Extraction confidence: {(ocrResult.confidence_score * 100).toFixed(0)}%</span>
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Vendor *</label>
              <select value={selectedVendor} onChange={(e) => setSelectedVendor(e.target.value)} className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500" style={{ minHeight: '48px' }}>
                <option value="">Select vendor...</option>
                {vendors.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Invoice #</label>
                <input type="text" value={formData.invoice_number} onChange={(e) => setFormData({ ...formData, invoice_number: e.target.value })} className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500" placeholder="INV-001" style={{ minHeight: '48px' }} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Date *</label>
                <input type="date" value={formData.invoice_date} onChange={(e) => setFormData({ ...formData, invoice_date: e.target.value })} className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500" style={{ minHeight: '48px' }} />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Total *</label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">$</span>
                <input type="number" step="0.01" value={formData.total} onChange={(e) => setFormData({ ...formData, total: e.target.value })} className="w-full p-3 pl-8 border rounded-lg focus:ring-2 focus:ring-blue-500" placeholder="0.00" style={{ minHeight: '48px' }} />
              </div>
            </div>
            {editingItems.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Extracted Items ({editingItems.length})</label>
                <div className="max-h-60 overflow-y-auto border rounded-lg divide-y">
                  {editingItems.map((item, i) => (
                    <div key={i} className="p-2 space-y-1">
                      <div className="flex justify-between text-sm">
                        <span className="truncate flex-1 font-medium text-gray-800">{item.product_name}</span>
                        <span className="ml-2 text-gray-600">{formatCurrency(item.total_price)}</span>
                      </div>
                      <select
                        value={item.category_id || ''}
                        onChange={(e) => updateLineItem(i, 'category_id', e.target.value)}
                        className="w-full p-1.5 border rounded text-xs"
                      >
                        <option value="">Auto-categorize</option>
                        {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                      </select>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        <div className="p-4 border-t flex gap-3">
          <button onClick={handleClose} className="flex-1 py-3 border rounded-xl font-medium hover:bg-gray-50" style={{ minHeight: '48px' }}>Cancel</button>
          <button onClick={handleSubmit} disabled={loading || !selectedVendor || !formData.total} className="flex-1 py-3 bg-blue-600 text-white rounded-xl font-medium disabled:opacity-50 hover:bg-blue-700" style={{ minHeight: '48px' }}>
            {loading ? 'Saving...' : 'Save Invoice'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ==================== VENDOR MODAL ====================
const VendorModal = ({ isOpen, onClose, onSuccess }) => {
  const [categories, setCategories] = useState([]);
  const [formData, setFormData] = useState({ name: '', category_id: '', phone: '', email: '', payment_terms: '', default_due_days: '' });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) api('/categories').then(setCategories).catch(console.error);
  }, [isOpen]);

  const handleSubmit = async () => {
    if (!formData.name) { alert('Please enter vendor name'); return; }
    setLoading(true);
    try {
      await api('/vendors', {
        method: 'POST',
        body: JSON.stringify({
          ...formData,
          category_id: formData.category_id ? parseInt(formData.category_id) : null,
          default_due_days: formData.default_due_days ? parseInt(formData.default_due_days) : null,
        }),
      });
      onSuccess();
      onClose();
      setFormData({ name: '', category_id: '', phone: '', email: '', payment_terms: '', default_due_days: '' });
    } catch (err) { console.error('Submit Error:', err); alert('Failed to create vendor'); }
    finally { setLoading(false); }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">Add Vendor</h2>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-full" style={{ minHeight: '44px', minWidth: '44px' }}><X size={20} /></button>
        </div>
        <div className="p-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
            <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className="w-full p-3 border rounded-lg" placeholder="Vendor name" style={{ minHeight: '48px' }} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
            <select value={formData.category_id} onChange={(e) => setFormData({ ...formData, category_id: e.target.value })} className="w-full p-3 border rounded-lg" style={{ minHeight: '48px' }}>
              <option value="">Select category...</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
              <input type="tel" value={formData.phone} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} className="w-full p-3 border rounded-lg" placeholder="Phone" style={{ minHeight: '48px' }} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} className="w-full p-3 border rounded-lg" placeholder="Email" style={{ minHeight: '48px' }} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Payment Terms</label>
              <select value={formData.payment_terms} onChange={(e) => setFormData({ ...formData, payment_terms: e.target.value })} className="w-full p-3 border rounded-lg" style={{ minHeight: '48px' }}>
                <option value="">Select...</option>
                <option value="COD">COD</option>
                <option value="NET7">NET 7</option>
                <option value="NET15">NET 15</option>
                <option value="NET30">NET 30</option>
                <option value="NET60">NET 60</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Due Days</label>
              <input type="number" value={formData.default_due_days} onChange={(e) => setFormData({ ...formData, default_due_days: e.target.value })} className="w-full p-3 border rounded-lg" placeholder="30" style={{ minHeight: '48px' }} />
            </div>
          </div>
        </div>
        <div className="p-4 border-t flex gap-3">
          <button onClick={onClose} className="flex-1 py-3 border rounded-xl font-medium hover:bg-gray-50" style={{ minHeight: '48px' }}>Cancel</button>
          <button onClick={handleSubmit} disabled={loading || !formData.name} className="flex-1 py-3 bg-blue-600 text-white rounded-xl font-medium disabled:opacity-50" style={{ minHeight: '48px' }}>
            {loading ? 'Creating...' : 'Create Vendor'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ==================== CONTRACTS SECTION ====================
const ContractsSection = () => {
  const [contracts, setContracts] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [vendors, setVendors] = useState([]);
  const [products, setProducts] = useState([]);
  const [form, setForm] = useState({ vendor_id: '', product_id: '', agreed_price: '', start_date: '', end_date: '', notes: '' });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadContracts();
  }, []);

  const loadContracts = () => {
    api('/contracts').then(setContracts).catch(console.error);
  };

  const openAdd = async () => {
    const [v, p] = await Promise.all([
      api('/vendors').catch(() => []),
      api('/analytics/products?limit=100').catch(() => []),
    ]);
    setVendors(v);
    setProducts(p);
    setShowAdd(true);
  };

  const handleCreate = async () => {
    if (!form.vendor_id || !form.product_id || !form.agreed_price || !form.start_date || !form.end_date) {
      alert('Fill all required fields');
      return;
    }
    setLoading(true);
    try {
      await api('/contracts', {
        method: 'POST',
        body: JSON.stringify({
          vendor_id: parseInt(form.vendor_id),
          product_id: parseInt(form.product_id),
          agreed_price: parseFloat(form.agreed_price),
          start_date: form.start_date,
          end_date: form.end_date,
          notes: form.notes || null,
        }),
      });
      setShowAdd(false);
      setForm({ vendor_id: '', product_id: '', agreed_price: '', start_date: '', end_date: '', notes: '' });
      loadContracts();
    } catch (err) { alert('Failed to create contract'); }
    finally { setLoading(false); }
  };

  const handleDelete = async (id) => {
    if (!confirm('Deactivate this contract?')) return;
    await api(`/contracts/${id}`, { method: 'DELETE' }).catch(console.error);
    loadContracts();
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield size={18} className="text-indigo-500" />
          <h3 className="font-semibold text-gray-800">Price Contracts</h3>
        </div>
        <button onClick={openAdd} className="text-sm text-blue-600 font-medium flex items-center gap-1" style={{ minHeight: '44px' }}>
          <Plus size={16} /> Add
        </button>
      </div>

      {contracts.map((c) => (
        <div key={c.id} className={`bg-white rounded-xl p-3 border ${c.is_violated ? 'border-red-300' : 'border-gray-100'}`}>
          <div className="flex justify-between items-start">
            <div>
              <div className="text-sm font-medium text-gray-800">{c.product_name}</div>
              <div className="text-xs text-gray-500">{c.vendor_name}</div>
            </div>
            <div className="text-right flex items-center gap-2">
              <div>
                <div className="text-sm font-bold text-gray-900">{formatCurrency(c.agreed_price)}</div>
                {c.current_price && (
                  <div className={`text-xs ${c.is_violated ? 'text-red-600 font-medium' : 'text-gray-500'}`}>
                    Now: {formatCurrency(c.current_price)}
                    {c.is_violated && ' !'}
                  </div>
                )}
              </div>
              <button onClick={() => handleDelete(c.id)} className="p-1 hover:bg-gray-100 rounded" style={{ minHeight: '32px', minWidth: '32px' }}>
                <Trash2 size={14} className="text-gray-400" />
              </button>
            </div>
          </div>
          <div className="text-xs text-gray-400 mt-1">
            {c.days_left > 0 ? `${c.days_left} days left` : 'Expired'} &bull; {c.start_date} to {c.end_date}
          </div>
        </div>
      ))}

      {contracts.length === 0 && !showAdd && (
        <div className="text-sm text-gray-400 text-center py-4">No active contracts</div>
      )}

      {/* Add contract form */}
      {showAdd && (
        <div className="bg-white rounded-xl p-4 border border-blue-200 space-y-3">
          <div className="text-sm font-medium text-gray-700">New Price Contract</div>
          <select value={form.vendor_id} onChange={e => setForm({ ...form, vendor_id: e.target.value })} className="w-full p-2.5 border rounded-lg text-sm" style={{ minHeight: '44px' }}>
            <option value="">Select vendor...</option>
            {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
          </select>
          <select value={form.product_id} onChange={e => setForm({ ...form, product_id: e.target.value })} className="w-full p-2.5 border rounded-lg text-sm" style={{ minHeight: '44px' }}>
            <option value="">Select product...</option>
            {products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <div className="grid grid-cols-3 gap-2">
            <input type="number" step="0.01" placeholder="Price" value={form.agreed_price} onChange={e => setForm({ ...form, agreed_price: e.target.value })} className="p-2.5 border rounded-lg text-sm" style={{ minHeight: '44px' }} />
            <input type="date" value={form.start_date} onChange={e => setForm({ ...form, start_date: e.target.value })} className="p-2.5 border rounded-lg text-sm" style={{ minHeight: '44px' }} />
            <input type="date" value={form.end_date} onChange={e => setForm({ ...form, end_date: e.target.value })} className="p-2.5 border rounded-lg text-sm" style={{ minHeight: '44px' }} />
          </div>
          <div className="flex gap-2">
            <button onClick={() => setShowAdd(false)} className="flex-1 py-2 border rounded-lg text-sm" style={{ minHeight: '40px' }}>Cancel</button>
            <button onClick={handleCreate} disabled={loading} className="flex-1 py-2 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-50" style={{ minHeight: '40px' }}>
              {loading ? 'Creating...' : 'Create'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// ==================== OCR CORRECTIONS SECTION ====================
const OCRCorrectionsSection = () => {
  const [corrections, setCorrections] = useState([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    api('/ocr/corrections').then(setCorrections).catch(console.error);
  }, []);

  const deleteCorrection = async (id) => {
    await api(`/ocr/corrections/${id}`, { method: 'DELETE' }).catch(console.error);
    setCorrections(prev => prev.filter(c => c.id !== id));
  };

  if (corrections.length === 0) return null;

  return (
    <div className="space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full"
        style={{ minHeight: '44px' }}
      >
        <div className="flex items-center gap-2">
          <Eye size={18} className="text-gray-500" />
          <h3 className="font-semibold text-gray-800">OCR Corrections</h3>
          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{corrections.length}</span>
        </div>
        <ChevronDown size={18} className={`text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>

      {expanded && (
        <div className="space-y-2">
          {corrections.map(c => (
            <div key={c.id} className="bg-white rounded-lg p-3 border border-gray-100 flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <div className="text-sm">
                  <span className="text-red-500 line-through">{c.original_text}</span>
                  <span className="text-gray-400 mx-2">&#8594;</span>
                  <span className="text-green-600 font-medium">{c.corrected_text}</span>
                </div>
                <div className="text-xs text-gray-400 mt-0.5">Used {c.use_count}x &bull; {c.field_type}</div>
              </div>
              <button onClick={() => deleteCorrection(c.id)} className="p-1.5 hover:bg-red-50 rounded ml-2" style={{ minHeight: '32px', minWidth: '32px' }}>
                <Trash2 size={14} className="text-gray-400" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ==================== SELL PRICE EDITOR ====================
const SellPriceEditor = ({ product, onUpdate }) => {
  const [editing, setEditing] = useState(false);
  const [sellPrice, setSellPrice] = useState(product?.sell_price || '');
  const [unitsPerCase, setUnitsPerCase] = useState(product?.units_per_case || '');
  const [targetMargin, setTargetMargin] = useState(product?.target_margin || '');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setSellPrice(product?.sell_price || '');
    setUnitsPerCase(product?.units_per_case || '');
    setTargetMargin(product?.target_margin || '');
  }, [product]);

  const save = async () => {
    if (!sellPrice) return;
    setSaving(true);
    try {
      await api(`/products/${product.id}/sell-price`, {
        method: 'PUT',
        body: JSON.stringify({
          sell_price: parseFloat(sellPrice),
          units_per_case: unitsPerCase ? parseInt(unitsPerCase) : null,
          target_margin: targetMargin ? parseFloat(targetMargin) : null,
        }),
      });
      onUpdate({
        id: product.id,
        sell_price: parseFloat(sellPrice),
        units_per_case: unitsPerCase ? parseInt(unitsPerCase) : null,
        target_margin: targetMargin ? parseFloat(targetMargin) : null,
      });
      setEditing(false);
    } catch (err) {
      alert('Failed to save');
    } finally {
      setSaving(false);
    }
  };

  // Calculate margin
  const buyPrice = product?.last_price;
  const sp = parseFloat(sellPrice) || 0;
  const units = parseInt(unitsPerCase) || 1;
  const revenue = sp * units;
  const margin = revenue > 0 && buyPrice ? (((revenue - buyPrice) / revenue) * 100).toFixed(1) : null;

  return (
    <div className="bg-white rounded-xl p-3 border border-gray-100">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-medium text-gray-800 text-sm">Profit Margin</h4>
        {!editing && (
          <button onClick={() => setEditing(true)} className="text-xs text-blue-600 font-medium" style={{ minHeight: '32px' }}>
            {product?.sell_price ? 'Edit' : 'Set Price'}
          </button>
        )}
      </div>

      {!editing && product?.sell_price ? (
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <div className="text-xs text-gray-500">Sell</div>
            <div className="text-sm font-bold text-gray-800">{formatCurrency(product.sell_price)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Units/Case</div>
            <div className="text-sm font-bold text-gray-800">{product.units_per_case || 1}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Margin</div>
            <div className={`text-sm font-bold ${margin >= 30 ? 'text-green-600' : margin >= 15 ? 'text-yellow-600' : 'text-red-600'}`}>
              {margin !== null ? `${margin}%` : '--'}
            </div>
          </div>
        </div>
      ) : !editing ? (
        <div className="text-xs text-gray-400">No sell price set</div>
      ) : null}

      {editing && (
        <div className="space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-[10px] text-gray-500">Sell Price</label>
              <input type="number" step="0.01" value={sellPrice} onChange={e => setSellPrice(e.target.value)} className="w-full p-2 border rounded text-sm" placeholder="0.00" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Units/Case</label>
              <input type="number" value={unitsPerCase} onChange={e => setUnitsPerCase(e.target.value)} className="w-full p-2 border rounded text-sm" placeholder="1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Target %</label>
              <input type="number" step="0.1" value={targetMargin} onChange={e => setTargetMargin(e.target.value)} className="w-full p-2 border rounded text-sm" placeholder="30" />
            </div>
          </div>
          {margin !== null && (
            <div className={`text-xs font-medium ${margin >= 30 ? 'text-green-600' : margin >= 15 ? 'text-yellow-600' : 'text-red-600'}`}>
              Calculated margin: {margin}%
            </div>
          )}
          <div className="flex gap-2">
            <button onClick={() => setEditing(false)} className="flex-1 py-1.5 border rounded text-xs" style={{ minHeight: '32px' }}>Cancel</button>
            <button onClick={save} disabled={saving || !sellPrice} className="flex-1 py-1.5 bg-blue-600 text-white rounded text-xs disabled:opacity-50" style={{ minHeight: '32px' }}>
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// ==================== ANALYTICS TAB ====================
const AnalyticsTab = () => {
  const [subView, setSubView] = useState('products');
  const [products, setProducts] = useState([]);
  const [volumeData, setVolumeData] = useState([]);
  const [vendorData, setVendorData] = useState([]);
  const [spendingData, setSpendingData] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [priceHistory, setPriceHistory] = useState([]);
  const [productVendors, setProductVendors] = useState([]);
  const [seasonalData, setSeasonalData] = useState([]);
  const [savings, setSavings] = useState(null);
  const [competitors, setCompetitors] = useState([]);
  const [margins, setMargins] = useState([]);
  const [deadStock, setDeadStock] = useState([]);
  const [reorderData, setReorderData] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [catData, setCatData] = useState(null);
  const [uncategorized, setUncategorized] = useState([]);
  const [allCategories, setAllCategories] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api('/analytics/products?sort_by=spend').catch(() => []),
      api('/analytics/volume-trends').catch(() => []),
      api('/analytics/vendor-comparison').catch(() => []),
      api('/analytics/spending-by-product').catch(() => []),
      api('/analytics/savings-opportunities').catch(() => ({ total_potential_savings: 0, opportunities: [] })),
      api('/competitors').catch(() => []),
      api('/analytics/margins').catch(() => []),
      api('/analytics/dead-stock').catch(() => []),
      api('/analytics/reorder-suggestions').catch(() => []),
      api('/categories/with-products').catch(() => ({ categories: [], uncategorized_count: 0 })),
      api('/products/uncategorized').catch(() => []),
      api('/categories').catch(() => []),
    ]).then(([p, v, vc, s, sav, comp, m, ds, ro, cd, unc, cats]) => {
      setProducts(p);
      setVolumeData(v);
      setVendorData(vc);
      setSpendingData(s);
      setSavings(sav);
      setCompetitors(comp);
      setMargins(m);
      setDeadStock(ds);
      setReorderData(ro);
      setCatData(cd);
      setUncategorized(unc);
      setAllCategories(cats);
    }).finally(() => setLoading(false));
  }, []);

  const openProductDetail = async (product) => {
    setSelectedProduct(product);
    const [history, vendors, seasonal] = await Promise.all([
      api(`/analytics/products/${product.id}/price-history`).catch(() => []),
      api(`/analytics/products/${product.id}/vendors`).catch(() => []),
      api(`/analytics/seasonal/${product.id}`).catch(() => []),
    ]);
    setPriceHistory(history);
    setProductVendors(vendors);
    setSeasonalData(seasonal);
  };

  const filteredProducts = searchQuery
    ? products.filter((p) => p.name.toLowerCase().includes(searchQuery.toLowerCase()))
    : products;

  const subViews = [
    { id: 'products', label: 'Products' },
    { id: 'categories', label: 'Categories' },
    { id: 'vendors', label: 'Vendors' },
    { id: 'volume', label: 'Volume' },
    { id: 'savings', label: 'Savings' },
    { id: 'margins', label: 'Margins' },
    { id: 'reorder', label: 'Reorder' },
  ];

  if (loading) return <div className="flex items-center justify-center py-20"><RefreshCw className="animate-spin text-blue-600" size={32} /></div>;

  return (
    <div className="space-y-4">
      {/* Sub-view tabs - scrollable */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl overflow-x-auto">
        {subViews.map((sv) => (
          <button
            key={sv.id}
            onClick={() => setSubView(sv.id)}
            className={`flex-shrink-0 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${subView === sv.id ? 'bg-white shadow-sm text-blue-600' : 'text-gray-500'}`}
            style={{ minHeight: '44px' }}
          >
            {sv.label}
          </button>
        ))}
      </div>

      {/* Product detail slide-up */}
      {selectedProduct && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-end justify-center">
          <div className="bg-white rounded-t-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b sticky top-0 bg-white">
              <h3 className="font-semibold text-lg">{selectedProduct.name}</h3>
              <button onClick={() => setSelectedProduct(null)} className="p-2 hover:bg-gray-100 rounded-full" style={{ minHeight: '44px', minWidth: '44px' }}><X size={20} /></button>
            </div>
            <div className="p-4 space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-blue-50 rounded-lg p-3 text-center">
                  <div className="text-lg font-bold text-blue-700">{formatCurrency(selectedProduct.last_price)}</div>
                  <div className="text-xs text-blue-600">Last Price</div>
                </div>
                <div className="bg-green-50 rounded-lg p-3 text-center">
                  <div className="text-lg font-bold text-green-700">{formatCurrency(selectedProduct.avg_price)}</div>
                  <div className="text-xs text-green-600">Avg Price</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3 text-center">
                  <div className="text-lg font-bold text-gray-700">{selectedProduct.vendor_count}</div>
                  <div className="text-xs text-gray-600">Vendors</div>
                </div>
              </div>

              {priceHistory.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-800 mb-2">Price History</h4>
                  <PriceHistoryChart data={priceHistory} />
                </div>
              )}

              {productVendors.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-800 mb-2">Vendor Comparison</h4>
                  <div className="space-y-2">
                    {productVendors.map((v, i) => (
                      <div key={v.vendor_id} className={`flex items-center justify-between p-3 rounded-lg border ${i === 0 ? 'bg-green-50 border-green-200' : 'border-gray-100'}`}>
                        <div>
                          <div className="font-medium text-gray-800">{v.vendor_name}</div>
                          <div className="text-xs text-gray-500">{v.purchase_count} purchases</div>
                        </div>
                        <div className="text-right">
                          <div className="font-bold text-gray-900">{formatCurrency(v.avg_price)}</div>
                          <div className="text-xs text-gray-500">{formatCurrency(v.min_price)} - {formatCurrency(v.max_price)}</div>
                        </div>
                        {i === 0 && <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full ml-2">Best</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Sell Price / Margin */}
              <SellPriceEditor product={selectedProduct} onUpdate={(updated) => {
                setSelectedProduct(prev => ({ ...prev, ...updated }));
                setProducts(prev => prev.map(p => p.id === updated.id ? { ...p, ...updated } : p));
              }} />

              {/* Seasonal patterns */}
              {seasonalData.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-800 mb-2">Seasonal Price Pattern</h4>
                  <div className="grid grid-cols-6 gap-1">
                    {seasonalData.map((m) => {
                      const allPrices = seasonalData.map(s => s.avg_price);
                      const minP = Math.min(...allPrices);
                      const maxP = Math.max(...allPrices);
                      const pct = maxP > minP ? ((m.avg_price - minP) / (maxP - minP)) : 0.5;
                      const bg = pct > 0.7 ? 'bg-red-200' : pct > 0.3 ? 'bg-yellow-200' : 'bg-green-200';
                      return (
                        <div key={m.month} className={`${bg} rounded p-1.5 text-center`}>
                          <div className="text-[10px] text-gray-600">{m.month_name}</div>
                          <div className="text-xs font-bold text-gray-800">${m.avg_price}</div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex justify-between text-[10px] text-gray-400 mt-1">
                    <span>Green = cheaper</span>
                    <span>Red = more expensive</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* BY PRODUCT */}
      {subView === 'products' && (
        <div className="space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
            <input
              type="text"
              placeholder="Search products..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 bg-white border rounded-xl focus:ring-2 focus:ring-blue-500"
              style={{ minHeight: '44px' }}
            />
          </div>
          <div className="space-y-2">
            {filteredProducts.map((p) => (
              <div
                key={p.id}
                onClick={() => openProductDetail(p)}
                className="bg-white rounded-xl p-4 border border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors"
                style={{ minHeight: '48px' }}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-800 truncate">{p.name}</div>
                    <div className="text-sm text-gray-500 mt-0.5">
                      {p.category_name && <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded mr-1">{p.category_name}</span>}
                      {p.vendor_count} vendor{p.vendor_count !== 1 ? 's' : ''} &bull; {p.total_volume} units
                    </div>
                  </div>
                  <div className="text-right ml-3">
                    <div className="font-bold text-gray-900">{formatCurrency(p.total_spend)}</div>
                    <div className="text-sm text-gray-500">{formatCurrency(p.last_price)}/ea</div>
                  </div>
                </div>
              </div>
            ))}
            {filteredProducts.length === 0 && (
              <div className="text-center py-8 text-gray-400">No products found</div>
            )}
          </div>
        </div>
      )}

      {/* CATEGORIES */}
      {subView === 'categories' && (
        <div className="space-y-4">
          {catData && (
            <div className="space-y-3">
              {catData.categories?.map((cat) => (
                <div key={cat.id} className="bg-white rounded-xl p-4 border border-gray-100">
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="font-medium text-gray-800">{cat.name}</div>
                      {cat.description && <div className="text-xs text-gray-500">{cat.description}</div>}
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold text-gray-900">{cat.product_count}</div>
                      <div className="text-xs text-gray-500">products</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Uncategorized products */}
          {uncategorized.length > 0 && (
            <div className="bg-yellow-50 rounded-xl p-4 border border-yellow-200">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={16} className="text-yellow-600" />
                <span className="font-medium text-yellow-800">{catData?.uncategorized_count || uncategorized.length} Uncategorized Products</span>
              </div>
              <div className="space-y-2">
                {uncategorized.map((p) => (
                  <div key={p.id} className="flex items-center justify-between bg-white rounded-lg p-2 border border-yellow-100">
                    <div className="text-sm text-gray-800 flex-1 truncate">{p.name}</div>
                    <select
                      className="ml-2 text-xs p-1.5 border rounded"
                      defaultValue=""
                      onChange={async (e) => {
                        if (!e.target.value) return;
                        await api(`/products/${p.id}/category?category_id=${e.target.value}`, { method: 'PUT' }).catch(console.error);
                        setUncategorized(prev => prev.filter(x => x.id !== p.id));
                      }}
                    >
                      <option value="">Assign...</option>
                      {allCategories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* BY VENDOR */}
      {subView === 'vendors' && (
        <div className="space-y-3">
          {vendorData.map((v) => (
            <div key={v.vendor_id} className="bg-white rounded-xl p-4 border border-gray-100">
              <div className="flex justify-between items-start">
                <div>
                  <div className="font-medium text-gray-800">{v.vendor_name}</div>
                  <div className="text-sm text-gray-500 mt-0.5">
                    {v.invoice_count} invoices &bull; {v.product_count} products
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-bold text-gray-900">{formatCurrency(v.total_spend)}</div>
                  <div className="text-sm text-gray-500">avg {formatCurrency(v.avg_unit_price)}/item</div>
                </div>
              </div>
            </div>
          ))}
          {vendorData.length === 0 && <div className="text-center py-8 text-gray-400">No vendor data</div>}
        </div>
      )}

      {/* VOLUME */}
      {subView === 'volume' && (
        <div className="bg-white rounded-xl p-4 border border-gray-100">
          <h3 className="font-medium text-gray-800 mb-3">Top Products by Volume (30 days)</h3>
          <VolumeChart data={volumeData} />
        </div>
      )}

      {/* SAVINGS */}
      {subView === 'savings' && (
        <div className="space-y-4">
          {savings && savings.total_potential_savings > 0 && (
            <div className="bg-green-50 rounded-xl p-4 border border-green-200">
              <div className="text-sm text-green-700 font-medium">Total Potential Savings</div>
              <div className="text-3xl font-bold text-green-800">{formatCurrency(savings.total_potential_savings)}</div>
              <div className="text-sm text-green-600 mt-1">{savings.opportunities.length} opportunities found</div>
            </div>
          )}

          {savings?.opportunities?.map((o, i) => (
            <div key={i} className="bg-white rounded-xl p-4 border border-gray-100">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="font-medium text-gray-800">{o.product_name}</div>
                  <div className="text-sm text-gray-500 mt-0.5">Available at {o.competitor_store}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm text-gray-500 line-through">{formatCurrency(o.our_price)}</div>
                  <div className="font-bold text-green-600">{formatCurrency(o.competitor_price)}</div>
                  <div className="text-xs text-green-600">-{o.savings_percent}%</div>
                </div>
              </div>
            </div>
          ))}

          <div className="border-t pt-4">
            <h3 className="font-medium text-gray-800 mb-3">Competitor Stores</h3>
            {competitors.map((c) => (
              <div key={c.id} className="bg-white rounded-xl p-4 border border-gray-100 mb-2 flex justify-between items-center">
                <div>
                  <div className="font-medium text-gray-800">{c.name}</div>
                  <div className="text-xs text-gray-500">{c.last_scraped_at ? `Last scraped: ${formatDate(c.last_scraped_at)}` : 'Manual entry'}</div>
                </div>
                <div className="text-sm text-blue-600">{c.scraper_type}</div>
              </div>
            ))}
            {competitors.length === 0 && (
              <div className="text-sm text-gray-400 text-center py-4">No competitor stores added yet</div>
            )}
          </div>
        </div>
      )}

      {/* MARGINS */}
      {subView === 'margins' && (
        <div className="space-y-3">
          <div className="bg-white rounded-xl p-4 border border-gray-100">
            <div className="flex items-center gap-2 mb-3">
              <Percent size={18} className="text-blue-500" />
              <h3 className="font-medium text-gray-800">Profit Margins</h3>
            </div>
            {margins.length === 0 ? (
              <div className="text-sm text-gray-400 text-center py-6">
                No products with sell prices set. Set sell prices in product details to see margins.
              </div>
            ) : (
              <div className="space-y-2">
                {margins.map((m) => (
                  <div key={m.id} className={`flex items-center justify-between p-3 rounded-lg border ${
                    m.margin_status === 'below' ? 'border-red-200 bg-red-50' : 'border-gray-100'
                  }`}>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-800 truncate">{m.name}</div>
                      <div className="text-xs text-gray-500">
                        Buy: {formatCurrency(m.buy_price)} &bull; Sell: {formatCurrency(m.sell_price)}
                        {m.units_per_case > 1 && ` x ${m.units_per_case}/case`}
                      </div>
                    </div>
                    <div className="text-right ml-2">
                      <div className={`text-sm font-bold ${
                        m.margin_percent >= 30 ? 'text-green-600' :
                        m.margin_percent >= 15 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        {m.margin_percent}%
                      </div>
                      {m.target_margin && (
                        <div className="text-xs text-gray-400">Target: {m.target_margin}%</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Dead stock */}
          {deadStock.length > 0 && (
            <div className="bg-white rounded-xl p-4 border border-gray-100">
              <div className="flex items-center gap-2 mb-3">
                <Archive size={18} className="text-gray-500" />
                <h3 className="font-medium text-gray-800">Dead Stock</h3>
              </div>
              <div className="text-sm text-gray-500 mb-2">Products you used to buy but stopped ordering:</div>
              <div className="space-y-2">
                {deadStock.map((d) => (
                  <div key={d.id} className="flex justify-between items-center p-2 rounded border border-gray-100">
                    <div>
                      <div className="text-sm font-medium text-gray-800">{d.name}</div>
                      <div className="text-xs text-gray-500">Last ordered {d.days_since_last_order} days ago</div>
                    </div>
                    <div className="text-xs text-gray-400">{d.total_purchases} prev orders</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* REORDER */}
      {subView === 'reorder' && (
        <div className="space-y-3">
          <div className="bg-white rounded-xl p-4 border border-gray-100">
            <div className="flex items-center gap-2 mb-3">
              <RotateCcw size={18} className="text-purple-500" />
              <h3 className="font-medium text-gray-800">Reorder Suggestions</h3>
            </div>
            {reorderData.length === 0 ? (
              <div className="text-sm text-gray-400 text-center py-6">
                Not enough purchase history to generate suggestions yet.
              </div>
            ) : (
              <div className="space-y-2">
                {reorderData.map((s, i) => (
                  <div key={i} className={`p-3 rounded-lg border ${
                    s.urgency === 'overdue' ? 'border-red-200 bg-red-50' :
                    s.urgency === 'due_soon' ? 'border-yellow-200 bg-yellow-50' : 'border-gray-100'
                  }`}>
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="text-sm font-medium text-gray-800">{s.product_name}</div>
                        <div className="text-xs text-gray-500">
                          Order every ~{s.avg_order_interval_days} days &bull; Last from {s.last_vendor || 'N/A'}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                          s.urgency === 'overdue' ? 'bg-red-100 text-red-700' :
                          s.urgency === 'due_soon' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-green-100 text-green-700'
                        }`}>
                          {s.urgency === 'overdue' ? `${s.days_overdue}d overdue` :
                           s.urgency === 'due_soon' ? 'Due soon' : 'OK'}
                        </div>
                        {s.last_price && <div className="text-xs text-gray-500 mt-1">{formatCurrency(s.last_price)}</div>}
                      </div>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      Last ordered {s.days_since_last_order} days ago
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// ==================== DELI TAB ====================
const DeliTab = () => {
  const [subView, setSubView] = useState('inventory');
  const [inventory, setInventory] = useState([]);
  const [deliVendors, setDeliVendors] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [allVendors, setAllVendors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddItem, setShowAddItem] = useState(false);
  const [newItem, setNewItem] = useState({ product_name: '', par_level: '', current_quantity: '', unit: 'ea' });

  const loadData = () => {
    setLoading(true);
    Promise.all([
      api('/deli/inventory').catch(() => []),
      api('/deli/vendors').catch(() => []),
      api('/deli/delivery-schedule').catch(() => []),
      api('/vendors').catch(() => []),
    ]).then(([inv, dv, sch, av]) => {
      setInventory(inv);
      setDeliVendors(dv);
      setSchedules(sch);
      setAllVendors(av);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, []);

  const addItem = async () => {
    if (!newItem.product_name) return;
    await api('/deli/inventory', {
      method: 'POST',
      body: JSON.stringify({
        product_name: newItem.product_name,
        par_level: parseFloat(newItem.par_level) || 0,
        current_quantity: parseFloat(newItem.current_quantity) || 0,
        unit: newItem.unit,
      }),
    }).catch(err => alert('Failed to add item'));
    setNewItem({ product_name: '', par_level: '', current_quantity: '', unit: 'ea' });
    setShowAddItem(false);
    loadData();
  };

  const updateCount = async (itemId, qty) => {
    await api(`/deli/inventory/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify({ current_quantity: parseFloat(qty) }),
    }).catch(console.error);
    loadData();
  };

  const deleteItem = async (itemId) => {
    await api(`/deli/inventory/${itemId}`, { method: 'DELETE' }).catch(console.error);
    loadData();
  };

  const deliSubViews = [
    { id: 'inventory', label: 'Inventory' },
    { id: 'orders', label: 'Order Sheets' },
    { id: 'deliveries', label: 'Deliveries' },
  ];

  if (loading) return <div className="flex items-center justify-center py-20"><RefreshCw className="animate-spin text-blue-600" size={32} /></div>;

  return (
    <div className="space-y-4">
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl overflow-x-auto">
        {deliSubViews.map(sv => (
          <button
            key={sv.id}
            onClick={() => setSubView(sv.id)}
            className={`flex-shrink-0 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${subView === sv.id ? 'bg-white shadow-sm text-blue-600' : 'text-gray-500'}`}
            style={{ minHeight: '44px' }}
          >
            {sv.label}
          </button>
        ))}
      </div>

      {/* INVENTORY */}
      {subView === 'inventory' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-gray-600 text-sm">{inventory.length} items tracked</span>
            <button onClick={() => setShowAddItem(true)} className="text-sm text-blue-600 font-medium flex items-center gap-1" style={{ minHeight: '44px' }}>
              <Plus size={16} /> Add Item
            </button>
          </div>

          {showAddItem && (
            <div className="bg-white rounded-xl p-4 border border-blue-200 space-y-3">
              <input type="text" placeholder="Product name" value={newItem.product_name} onChange={e => setNewItem({ ...newItem, product_name: e.target.value })} className="w-full p-2.5 border rounded-lg text-sm" style={{ minHeight: '44px' }} />
              <div className="grid grid-cols-3 gap-2">
                <input type="number" step="0.1" placeholder="Par level" value={newItem.par_level} onChange={e => setNewItem({ ...newItem, par_level: e.target.value })} className="p-2.5 border rounded-lg text-sm" style={{ minHeight: '44px' }} />
                <input type="number" step="0.1" placeholder="Current qty" value={newItem.current_quantity} onChange={e => setNewItem({ ...newItem, current_quantity: e.target.value })} className="p-2.5 border rounded-lg text-sm" style={{ minHeight: '44px' }} />
                <select value={newItem.unit} onChange={e => setNewItem({ ...newItem, unit: e.target.value })} className="p-2.5 border rounded-lg text-sm" style={{ minHeight: '44px' }}>
                  <option value="ea">each</option>
                  <option value="lb">lb</option>
                  <option value="case">case</option>
                  <option value="bag">bag</option>
                </select>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setShowAddItem(false)} className="flex-1 py-2 border rounded-lg text-sm" style={{ minHeight: '40px' }}>Cancel</button>
                <button onClick={addItem} className="flex-1 py-2 bg-blue-600 text-white rounded-lg text-sm" style={{ minHeight: '40px' }}>Add</button>
              </div>
            </div>
          )}

          {inventory.length === 0 && !showAddItem ? (
            <div className="bg-white rounded-xl p-8 text-center border border-gray-100">
              <Package size={40} className="mx-auto text-gray-300 mb-3" />
              <div className="text-gray-500 font-medium">No deli items tracked yet</div>
              <div className="text-sm text-gray-400 mt-1">Add items to track inventory and par levels</div>
            </div>
          ) : (
            inventory.map(item => (
              <div key={item.id} className={`bg-white rounded-xl p-4 border ${item.deficit > 0 ? 'border-red-200' : 'border-gray-100'}`}>
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-medium text-gray-800">{item.product_name}</div>
                    <div className="text-xs text-gray-500">Par: {item.par_level} {item.unit}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={() => updateCount(item.id, Math.max(0, item.current_quantity - 1))} className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center text-gray-600 font-bold">
                      -
                    </button>
                    <span className={`text-lg font-bold ${item.deficit > 0 ? 'text-red-600' : 'text-green-600'}`}>
                      {item.current_quantity}
                    </span>
                    <button onClick={() => updateCount(item.id, item.current_quantity + 1)} className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
                      <Plus size={14} />
                    </button>
                    <button onClick={() => deleteItem(item.id)} className="w-8 h-8 hover:bg-red-50 rounded-full flex items-center justify-center ml-1">
                      <Trash2 size={14} className="text-gray-400" />
                    </button>
                  </div>
                </div>
                {item.deficit > 0 && (
                  <div className="text-xs text-red-600 mt-1 font-medium">
                    Need {item.deficit} more {item.unit}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* ORDER SHEETS */}
      {subView === 'orders' && (
        <div className="space-y-3">
          {deliVendors.length === 0 ? (
            <div className="bg-white rounded-xl p-8 text-center border border-gray-100">
              <Package size={40} className="mx-auto text-gray-300 mb-3" />
              <div className="text-gray-500 font-medium">No deli vendors configured</div>
              <div className="text-sm text-gray-400 mt-1">Flag vendors as deli vendors in the Vendors tab</div>
            </div>
          ) : (
            deliVendors.map(vendor => (
              <div key={vendor.id} className="bg-white rounded-xl p-4 border border-gray-100">
                <div className="flex justify-between items-center">
                  <div>
                    <div className="font-medium text-gray-800">{vendor.name}</div>
                    <div className="text-xs text-gray-500">Deli vendor</div>
                  </div>
                  <button
                    onClick={async () => {
                      const sheet = await api(`/deli/order-sheet/${vendor.id}`).catch(() => null);
                      if (sheet && sheet.items.length > 0) {
                        alert(`Order sheet for ${vendor.name}:\n${sheet.items.map(i => `${i.product_name}: ${i.order_qty} ${i.unit}`).join('\n')}`);
                      } else {
                        alert('No items need reordering');
                      }
                    }}
                    className="px-3 py-1.5 bg-blue-50 text-blue-600 rounded-lg text-sm font-medium"
                    style={{ minHeight: '36px' }}
                  >
                    Generate Order
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* DELIVERIES */}
      {subView === 'deliveries' && (
        <div className="space-y-3">
          {schedules.length === 0 ? (
            <div className="bg-white rounded-xl p-8 text-center border border-gray-100">
              <Truck size={40} className="mx-auto text-gray-300 mb-3" />
              <div className="text-gray-500 font-medium">No delivery schedules set</div>
              <div className="text-sm text-gray-400 mt-1">Add delivery schedules for your deli vendors</div>
            </div>
          ) : (
            schedules.map(s => (
              <div key={s.id} className="bg-white rounded-xl p-4 border border-gray-100">
                <div className="font-medium text-gray-800">{s.vendor_name}</div>
                <div className="text-sm text-gray-500 mt-1">
                  Delivers: {s.delivery_days}
                  {s.cutoff_time && ` (cutoff: ${s.cutoff_time})`}
                </div>
                <div className="text-xs text-gray-400 mt-1">Lead time: {s.lead_days} day{s.lead_days > 1 ? 's' : ''}</div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

// ==================== MAIN APP ====================
function PurchaseTracker() {
  const [authenticated, setAuthenticated] = useState(!!getToken());
  const [activeTab, setActiveTab] = useState('dashboard');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showVendorModal, setShowVendorModal] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [selectedVendorId, setSelectedVendorId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [darkMode, toggleDarkMode] = useDarkMode();

  const [summary, setSummary] = useState(null);
  const [budgetStatus, setBudgetStatus] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [disputes, setDisputes] = useState([]);
  const [invoiceSearch, setInvoiceSearch] = useState('');

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  // Listen for auth expiration
  useEffect(() => {
    const handler = () => setAuthenticated(false);
    window.addEventListener('auth-expired', handler);
    return () => window.removeEventListener('auth-expired', handler);
  }, []);

  // Verify token on mount
  useEffect(() => {
    if (!getToken()) return;
    api('/auth/verify').catch(() => setAuthenticated(false));
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    const loadData = async () => {
      setLoading(true);
      try {
        const [summaryData, budgetData, invoiceData, vendorData, recsData, disputeData] = await Promise.all([
          api('/dashboard/summary'),
          api('/dashboard/budget-status'),
          api('/invoices?limit=50'),
          api('/vendors'),
          api('/recommendations').catch(() => []),
          api('/disputes').catch(() => []),
        ]);
        setSummary(summaryData);
        setBudgetStatus(budgetData);
        setInvoices(invoiceData.invoices);
        setVendors(vendorData);
        setRecommendations(recsData);
        setDisputes(disputeData);
      } catch (err) {
        console.error('Load Error:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [refreshKey, authenticated]);

  const handleLogout = () => {
    clearToken();
    setAuthenticated(false);
  };

  const handleDismissRec = async (id) => {
    await api(`/recommendations/${id}/dismiss`, { method: 'PUT' }).catch(console.error);
    setRecommendations((r) => r.filter((x) => x.id !== id));
  };

  const handleActRec = async (id) => {
    await api(`/recommendations/${id}/acted`, { method: 'PUT' }).catch(console.error);
    setRecommendations((r) => r.filter((x) => x.id !== id));
  };

  if (!authenticated) return <LoginScreen onLogin={() => setAuthenticated(true)} />;

  const filteredInvoices = invoiceSearch
    ? invoices.filter(inv =>
        (inv.vendor_name || '').toLowerCase().includes(invoiceSearch.toLowerCase()) ||
        (inv.invoice_number || '').toLowerCase().includes(invoiceSearch.toLowerCase())
      )
    : invoices;

  const renderDashboard = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3">
        <SummaryCard title="Today" value={formatCurrency(summary?.today_purchases)} icon={DollarSign} color="blue" />
        <SummaryCard title="This Week" value={formatCurrency(summary?.week_purchases)} icon={TrendingUp} color="green" />
        <SummaryCard title="This Month" value={formatCurrency(summary?.month_purchases)} icon={Package} color="yellow" />
        <SummaryCard title="Pending" value={summary?.pending_invoices || 0} icon={Clock} trend="invoices to verify" color="red" />
      </div>

      <PaymentsDueSection />

      <CashFlowChart />

      <SmartInsights recommendations={recommendations} onDismiss={handleDismissRec} onAct={handleActRec} />

      <ReorderAlerts />

      {/* Open disputes banner */}
      {disputes.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-center gap-2">
            <AlertCircle size={18} className="text-red-500" />
            <span className="font-medium text-red-700">{disputes.length} Open Dispute{disputes.length > 1 ? 's' : ''}</span>
          </div>
          {disputes.slice(0, 2).map(d => (
            <div key={d.id} className="flex justify-between text-sm text-red-600 mt-1">
              <span>{d.vendor_name} - {d.invoice_number || 'No #'}</span>
              <span>{formatCurrency(d.total)}</span>
            </div>
          ))}
        </div>
      )}

      {budgetStatus && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-gray-800">Budget vs Actual</h2>
            <span className="text-sm text-gray-500">Sales: {formatCurrency(budgetStatus.monthly_sales)}</span>
          </div>
          <div className="space-y-3">
            {budgetStatus.categories?.filter((c) => c.actual_amount > 0).map((cat) => (
              <BudgetCard
                key={cat.category_id}
                category={cat.category_name}
                targetPercent={cat.target_percent}
                targetAmount={cat.target_amount}
                actualAmount={cat.actual_amount}
                monthlyTotal={budgetStatus.monthly_sales}
              />
            ))}
          </div>
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-800">Recent Invoices</h2>
          <button onClick={() => setActiveTab('invoices')} className="text-blue-600 text-sm font-medium" style={{ minHeight: '44px' }}>View All</button>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 divide-y">
          {summary?.recent_invoices?.map((inv) => (
            <InvoiceRow key={inv.id} invoice={inv} onClick={() => setSelectedInvoice(inv)} />
          ))}
          {(!summary?.recent_invoices || summary.recent_invoices.length === 0) && (
            <div className="p-8 text-center text-gray-500">No invoices yet. Add your first invoice!</div>
          )}
        </div>
      </div>
    </div>
  );

  const renderInvoices = () => (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
          <input
            type="text"
            placeholder="Search invoices..."
            value={invoiceSearch}
            onChange={(e) => setInvoiceSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-white border rounded-xl focus:ring-2 focus:ring-blue-500"
            style={{ minHeight: '44px' }}
          />
        </div>
        <button
          onClick={() => downloadFile('/export/invoices')}
          className="p-2.5 bg-white border rounded-xl hover:bg-gray-50 flex items-center gap-1"
          style={{ minHeight: '44px' }}
          title="Export CSV"
        >
          <Download size={18} className="text-gray-600" />
        </button>
      </div>

      {/* Quick filters */}
      <div className="flex gap-2 overflow-x-auto">
        <button
          onClick={() => setInvoiceSearch('')}
          className={`text-xs px-3 py-1.5 rounded-full border whitespace-nowrap ${!invoiceSearch ? 'bg-blue-50 border-blue-200 text-blue-700' : 'border-gray-200 text-gray-500'}`}
          style={{ minHeight: '32px' }}
        >All</button>
        {['pending', 'verified', 'paid', 'disputed'].map(s => (
          <button
            key={s}
            onClick={() => setInvoiceSearch(s)}
            className="text-xs px-3 py-1.5 rounded-full border border-gray-200 text-gray-500 whitespace-nowrap"
            style={{ minHeight: '32px' }}
          >{s}</button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-100 divide-y">
        {filteredInvoices.map((inv) => (
          <InvoiceRow key={inv.id} invoice={inv} onClick={() => setSelectedInvoice(inv)} />
        ))}
        {filteredInvoices.length === 0 && <div className="p-8 text-center text-gray-500">No invoices found</div>}
      </div>

      {/* Export line items */}
      <button
        onClick={() => downloadFile('/export/line-items')}
        className="w-full py-3 border rounded-xl text-sm text-gray-600 font-medium flex items-center justify-center gap-2 hover:bg-gray-50"
        style={{ minHeight: '44px' }}
      >
        <FileText size={16} /> Export Line Items CSV
      </button>
    </div>
  );

  const renderVendors = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-gray-600">{vendors.length} vendors</span>
        <button onClick={() => setShowVendorModal(true)} className="flex items-center gap-1 text-blue-600 font-medium" style={{ minHeight: '44px' }}>
          <Plus size={18} /> Add Vendor
        </button>
      </div>
      <div className="space-y-2">
        {vendors.map((vendor) => (
          <div
            key={vendor.id}
            className="bg-white rounded-xl p-4 border border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors"
            style={{ minHeight: '48px' }}
            onClick={() => setSelectedVendorId(vendor.id)}
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium text-gray-800">{vendor.name}</div>
                <div className="text-sm text-gray-500">
                  {vendor.category_name || 'Uncategorized'}
                  {vendor.payment_terms && ` &bull; ${vendor.payment_terms}`}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Star size={14} className="text-gray-300" />
                <ChevronRight className="text-gray-400" size={18} />
              </div>
            </div>
          </div>
        ))}
        {vendors.length === 0 && (
          <div className="bg-white rounded-xl p-8 text-center text-gray-500 border border-gray-100">No vendors yet. Add your first vendor!</div>
        )}
      </div>

      {/* Price Contracts section */}
      <div className="border-t pt-4">
        <ContractsSection />
      </div>

      {/* OCR Corrections section */}
      <div className="border-t pt-4">
        <OCRCorrectionsSection />
      </div>
    </div>
  );

  const tabs = [
    { id: 'dashboard', label: 'Home', icon: Home },
    { id: 'invoices', label: 'Invoices', icon: Package },
    { id: 'vendors', label: 'Vendors', icon: Users },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'deli', label: 'Deli', icon: ShoppingCart },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 py-3 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Apple Tree</h1>
            <p className="text-sm text-gray-500">Purchase Tracker</p>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={toggleDarkMode} className="p-2 hover:bg-gray-100 rounded-full transition-colors" style={{ minHeight: '44px', minWidth: '44px' }} title={darkMode ? 'Light mode' : 'Dark mode'}>
              {darkMode ? <Sun size={20} className="text-yellow-500" /> : <Moon size={20} className="text-gray-600" />}
            </button>
            <button onClick={refresh} className="p-2 hover:bg-gray-100 rounded-full transition-colors" style={{ minHeight: '44px', minWidth: '44px' }}>
              <RefreshCw size={20} className={loading ? 'animate-spin text-blue-600' : 'text-gray-600'} />
            </button>
            <button onClick={handleLogout} className="p-2 hover:bg-gray-100 rounded-full transition-colors" style={{ minHeight: '44px', minWidth: '44px' }}>
              <LogOut size={20} className="text-gray-600" />
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-lg mx-auto px-4 py-4 pb-28">
        {loading && !summary ? (
          <div className="flex items-center justify-center py-20">
            <RefreshCw className="animate-spin text-blue-600" size={32} />
          </div>
        ) : (
          <>
            {activeTab === 'dashboard' && renderDashboard()}
            {activeTab === 'invoices' && renderInvoices()}
            {activeTab === 'vendors' && renderVendors()}
            {activeTab === 'analytics' && <AnalyticsTab />}
            {activeTab === 'deli' && <DeliTab />}
          </>
        )}
      </main>

      {/* Snap Invoice FAB */}
      <button
        onClick={() => setShowUploadModal(true)}
        className="fixed bottom-24 right-4 bg-blue-600 text-white rounded-2xl shadow-lg flex items-center gap-2 px-5 py-3 hover:bg-blue-700 transition-colors z-30"
        style={{ minHeight: '48px' }}
      >
        <Camera size={22} />
        <span className="font-medium text-sm">Snap Invoice</span>
      </button>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t z-40 safe-area-inset-bottom">
        <div className="max-w-lg mx-auto flex">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 flex flex-col items-center py-2 transition-colors ${isActive ? 'text-blue-600' : 'text-gray-400'}`}
                style={{ minHeight: '56px' }}
              >
                <Icon size={22} />
                <span className="text-xs mt-1 font-medium">{tab.label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      {/* Modals */}
      <UploadModal isOpen={showUploadModal} onClose={() => setShowUploadModal(false)} onSuccess={refresh} />
      <VendorModal isOpen={showVendorModal} onClose={() => setShowVendorModal(false)} onSuccess={refresh} />
      {selectedInvoice && (
        <InvoiceDetailModal
          invoice={selectedInvoice}
          onClose={() => { setSelectedInvoice(null); refresh(); }}
          onRefresh={refresh}
        />
      )}
      {selectedVendorId && (
        <VendorScorecardModal
          vendorId={selectedVendorId}
          onClose={() => setSelectedVendorId(null)}
        />
      )}
    </div>
  );
}

// Mount the app
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(React.createElement(PurchaseTracker));
