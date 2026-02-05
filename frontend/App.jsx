import React, { useState, useEffect, useCallback } from 'react';
import { Camera, Upload, DollarSign, TrendingUp, Package, AlertTriangle, CheckCircle, Clock, X, Plus, Search, Filter, ChevronRight, RefreshCw } from 'lucide-react';

// API Configuration
const API_BASE = 'http://localhost:8000/api';

// Utility function for API calls
const api = async (endpoint, options = {}) => {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!response.ok) throw new Error(`API Error: ${response.status}`);
  return response.json();
};

// Format currency
const formatCurrency = (amount) => {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount || 0);
};

// Format date
const formatDate = (dateStr) => {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

// Dashboard Summary Cards
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

// Category Budget Card
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

// Recent Invoice Row
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
    >
      <div className="flex-1">
        <div className="font-medium text-gray-800">{invoice.vendor_name}</div>
        <div className="text-sm text-gray-500">
          {invoice.invoice_number} • {formatDate(invoice.invoice_date)}
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

// Invoice Upload Modal
const UploadModal = ({ isOpen, onClose, onSuccess }) => {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [ocrResult, setOcrResult] = useState(null);
  const [vendors, setVendors] = useState([]);
  const [selectedVendor, setSelectedVendor] = useState('');
  const [formData, setFormData] = useState({
    invoice_number: '',
    invoice_date: new Date().toISOString().split('T')[0],
    total: '',
  });

  useEffect(() => {
    if (isOpen) {
      api('/vendors').then(setVendors).catch(console.error);
    }
  }, [isOpen]);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setPreview(URL.createObjectURL(selectedFile));
    }
  };

  const handleOCR = async () => {
    if (!file) return;
    
    setLoading(true);
    try {
      const formDataUpload = new FormData();
      formDataUpload.append('file', file);
      
      const result = await fetch(`${API_BASE}/ocr/process`, {
        method: 'POST',
        body: formDataUpload,
      }).then(r => r.json());
      
      setOcrResult(result);
      setFormData({
        invoice_number: result.invoice_number || '',
        invoice_date: result.invoice_date || new Date().toISOString().split('T')[0],
        total: result.total || '',
      });
      if (result.suggested_vendor_id) {
        setSelectedVendor(result.suggested_vendor_id.toString());
      }
    } catch (err) {
      console.error('OCR Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!selectedVendor || !formData.total) {
      alert('Please select a vendor and enter the total');
      return;
    }
    
    setLoading(true);
    try {
      const invoiceData = {
        vendor_id: parseInt(selectedVendor),
        invoice_number: formData.invoice_number,
        invoice_date: formData.invoice_date,
        total: parseFloat(formData.total),
        items: ocrResult?.line_items || [],
      };
      
      await api('/invoices', {
        method: 'POST',
        body: JSON.stringify(invoiceData),
      });
      
      onSuccess();
      handleClose();
    } catch (err) {
      console.error('Submit Error:', err);
      alert('Failed to save invoice');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setFile(null);
    setPreview(null);
    setOcrResult(null);
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
          <button onClick={handleClose} className="p-1 hover:bg-gray-100 rounded-full">
            <X size={20} />
          </button>
        </div>
        
        <div className="p-4 space-y-4">
          {!preview ? (
            <label className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-gray-300 rounded-xl cursor-pointer hover:bg-gray-50 transition-colors">
              <Camera size={40} className="text-gray-400 mb-2" />
              <span className="text-gray-500">Tap to take photo or upload</span>
              <input
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleFileChange}
                className="hidden"
              />
            </label>
          ) : (
            <div className="relative">
              <img src={preview} alt="Invoice" className="w-full rounded-xl" />
              <button
                onClick={() => { setPreview(null); setFile(null); }}
                className="absolute top-2 right-2 p-1 bg-black/50 rounded-full text-white"
              >
                <X size={16} />
              </button>
              {!ocrResult && (
                <button
                  onClick={handleOCR}
                  disabled={loading}
                  className="absolute bottom-2 right-2 px-4 py-2 bg-blue-600 text-white rounded-lg font-medium disabled:opacity-50"
                >
                  {loading ? 'Processing...' : 'Extract Data'}
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
              <select
                value={selectedVendor}
                onChange={(e) => setSelectedVendor(e.target.value)}
                className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Select vendor...</option>
                {vendors.map(v => (
                  <option key={v.id} value={v.id}>{v.name}</option>
                ))}
              </select>
            </div>
            
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Invoice #</label>
                <input
                  type="text"
                  value={formData.invoice_number}
                  onChange={(e) => setFormData({...formData, invoice_number: e.target.value})}
                  className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="INV-001"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Date *</label>
                <input
                  type="date"
                  value={formData.invoice_date}
                  onChange={(e) => setFormData({...formData, invoice_date: e.target.value})}
                  className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Total *</label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">$</span>
                <input
                  type="number"
                  step="0.01"
                  value={formData.total}
                  onChange={(e) => setFormData({...formData, total: e.target.value})}
                  className="w-full p-3 pl-8 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="0.00"
                />
              </div>
            </div>
            
            {ocrResult?.line_items?.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Extracted Items ({ocrResult.line_items.length})
                </label>
                <div className="max-h-40 overflow-y-auto border rounded-lg">
                  {ocrResult.line_items.map((item, i) => (
                    <div key={i} className="flex justify-between p-2 border-b last:border-b-0 text-sm">
                      <span className="truncate flex-1">{item.product_name}</span>
                      <span className="ml-2 text-gray-600">{formatCurrency(item.total_price)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        
        <div className="p-4 border-t flex gap-3">
          <button
            onClick={handleClose}
            className="flex-1 py-3 border rounded-xl font-medium hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || !selectedVendor || !formData.total}
            className="flex-1 py-3 bg-blue-600 text-white rounded-xl font-medium disabled:opacity-50 hover:bg-blue-700 transition-colors"
          >
            {loading ? 'Saving...' : 'Save Invoice'}
          </button>
        </div>
      </div>
    </div>
  );
};

// Vendor Quick Add Modal
const VendorModal = ({ isOpen, onClose, onSuccess }) => {
  const [categories, setCategories] = useState([]);
  const [formData, setFormData] = useState({
    name: '',
    category_id: '',
    phone: '',
    email: '',
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      api('/categories').then(setCategories).catch(console.error);
    }
  }, [isOpen]);

  const handleSubmit = async () => {
    if (!formData.name) {
      alert('Please enter vendor name');
      return;
    }
    
    setLoading(true);
    try {
      await api('/vendors', {
        method: 'POST',
        body: JSON.stringify({
          ...formData,
          category_id: formData.category_id ? parseInt(formData.category_id) : null,
        }),
      });
      onSuccess();
      onClose();
      setFormData({ name: '', category_id: '', phone: '', email: '' });
    } catch (err) {
      console.error('Submit Error:', err);
      alert('Failed to create vendor');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-md">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">Add Vendor</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-full">
            <X size={20} />
          </button>
        </div>
        
        <div className="p-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({...formData, name: e.target.value})}
              className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="Vendor name"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
            <select
              value={formData.category_id}
              onChange={(e) => setFormData({...formData, category_id: e.target.value})}
              className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select category...</option>
              {categories.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
            <input
              type="tel"
              value={formData.phone}
              onChange={(e) => setFormData({...formData, phone: e.target.value})}
              className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="Phone number"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({...formData, email: e.target.value})}
              className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="Email address"
            />
          </div>
        </div>
        
        <div className="p-4 border-t flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-3 border rounded-xl font-medium hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || !formData.name}
            className="flex-1 py-3 bg-blue-600 text-white rounded-xl font-medium disabled:opacity-50"
          >
            {loading ? 'Creating...' : 'Create Vendor'}
          </button>
        </div>
      </div>
    </div>
  );
};

// Main App Component
export default function PurchaseTracker() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showVendorModal, setShowVendorModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  
  const [summary, setSummary] = useState(null);
  const [budgetStatus, setBudgetStatus] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [vendors, setVendors] = useState([]);

  const refresh = useCallback(() => setRefreshKey(k => k + 1), []);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [summaryData, budgetData, invoiceData, vendorData] = await Promise.all([
          api('/dashboard/summary'),
          api('/dashboard/budget-status'),
          api('/invoices?limit=20'),
          api('/vendors'),
        ]);
        setSummary(summaryData);
        setBudgetStatus(budgetData);
        setInvoices(invoiceData.invoices);
        setVendors(vendorData);
      } catch (err) {
        console.error('Load Error:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [refreshKey]);

  const renderDashboard = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3">
        <SummaryCard
          title="Today"
          value={formatCurrency(summary?.today_purchases)}
          icon={DollarSign}
          color="blue"
        />
        <SummaryCard
          title="This Week"
          value={formatCurrency(summary?.week_purchases)}
          icon={TrendingUp}
          color="green"
        />
        <SummaryCard
          title="This Month"
          value={formatCurrency(summary?.month_purchases)}
          icon={Package}
          color="yellow"
        />
        <SummaryCard
          title="Pending"
          value={summary?.pending_invoices || 0}
          icon={Clock}
          trend="invoices to verify"
          color="red"
        />
      </div>
      
      {budgetStatus && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-gray-800">Budget vs Actual</h2>
            <span className="text-sm text-gray-500">
              Sales: {formatCurrency(budgetStatus.monthly_sales)}
            </span>
          </div>
          <div className="space-y-3">
            {budgetStatus.categories?.filter(c => c.actual_amount > 0).map((cat) => (
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
          <button 
            onClick={() => setActiveTab('invoices')}
            className="text-blue-600 text-sm font-medium"
          >
            View All
          </button>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 divide-y">
          {summary?.recent_invoices?.map((inv) => (
            <InvoiceRow key={inv.id} invoice={inv} onClick={() => {}} />
          ))}
          {(!summary?.recent_invoices || summary.recent_invoices.length === 0) && (
            <div className="p-8 text-center text-gray-500">
              No invoices yet. Add your first invoice!
            </div>
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
            className="w-full pl-10 pr-4 py-2.5 bg-white border rounded-xl focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <button className="p-2.5 bg-white border rounded-xl hover:bg-gray-50">
          <Filter size={18} className="text-gray-600" />
        </button>
      </div>
      
      <div className="bg-white rounded-xl border border-gray-100 divide-y">
        {invoices.map((inv) => (
          <InvoiceRow key={inv.id} invoice={inv} onClick={() => {}} />
        ))}
        {invoices.length === 0 && (
          <div className="p-8 text-center text-gray-500">No invoices found</div>
        )}
      </div>
    </div>
  );

  const renderVendors = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-gray-600">{vendors.length} vendors</span>
        <button
          onClick={() => setShowVendorModal(true)}
          className="flex items-center gap-1 text-blue-600 font-medium"
        >
          <Plus size={18} /> Add Vendor
        </button>
      </div>
      
      <div className="space-y-2">
        {vendors.map((vendor) => (
          <div key={vendor.id} className="bg-white rounded-xl p-4 border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium text-gray-800">{vendor.name}</div>
                <div className="text-sm text-gray-500">{vendor.category_name || 'Uncategorized'}</div>
              </div>
              <ChevronRight className="text-gray-400" size={18} />
            </div>
          </div>
        ))}
        {vendors.length === 0 && (
          <div className="bg-white rounded-xl p-8 text-center text-gray-500 border border-gray-100">
            No vendors yet. Add your first vendor!
          </div>
        )}
      </div>
    </div>
  );

  const tabs = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'invoices', label: 'Invoices' },
    { id: 'vendors', label: 'Vendors' },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 py-3 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Apple Tree</h1>
            <p className="text-sm text-gray-500">Purchase Tracker</p>
          </div>
          <button
            onClick={refresh}
            className="p-2 hover:bg-gray-100 rounded-full transition-colors"
          >
            <RefreshCw size={20} className={loading ? 'animate-spin text-blue-600' : 'text-gray-600'} />
          </button>
        </div>
        
        <div className="max-w-lg mx-auto px-4">
          <div className="flex gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 py-4 pb-24">
        {loading && !summary ? (
          <div className="flex items-center justify-center py-20">
            <RefreshCw className="animate-spin text-blue-600" size={32} />
          </div>
        ) : (
          <>
            {activeTab === 'dashboard' && renderDashboard()}
            {activeTab === 'invoices' && renderInvoices()}
            {activeTab === 'vendors' && renderVendors()}
          </>
        )}
      </main>

      <button
        onClick={() => setShowUploadModal(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-blue-600 text-white rounded-full shadow-lg flex items-center justify-center hover:bg-blue-700 transition-colors z-30"
      >
        <Camera size={24} />
      </button>

      <UploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onSuccess={refresh}
      />
      <VendorModal
        isOpen={showVendorModal}
        onClose={() => setShowVendorModal(false)}
        onSuccess={refresh}
      />
    </div>
  );
}
