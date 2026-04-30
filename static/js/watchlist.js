// Watchlist JavaScript

let watchlistData = [];
let refreshInterval = null;

// Initialize watchlist page
document.addEventListener('DOMContentLoaded', function() {
    loadWatchlist();

    // Refresh watchlist every 30 seconds
    refreshInterval = setInterval(loadWatchlist, 30000);

    // Allow Enter key to add stocks
    document.getElementById('stock-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            addStocks();
        }
    });
});

// Load watchlist data from API
async function loadWatchlist() {
    try {
        const response = await fetch('/api/watchlist');
        const data = await response.json();

        if (response.ok) {
            watchlistData = data.watchlist || [];
            updateWatchlistUI();
        } else {
            showError(data.error || 'Failed to load watchlist');
        }
    } catch (error) {
        console.error('Error loading watchlist:', error);
        showError('Network error while loading watchlist');
    }
}

// Update the watchlist table UI
function updateWatchlistUI() {
    const tbody = document.getElementById('watchlist-tbody');
    const countBadge = document.getElementById('watchlist-count');
    const clearBtn = document.getElementById('clear-btn');

    // Update count
    countBadge.textContent = `${watchlistData.length} stock${watchlistData.length !== 1 ? 's' : ''}`;

    // Show/hide clear button
    clearBtn.style.display = watchlistData.length > 0 ? 'inline-block' : 'none';

    if (watchlistData.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="10" class="text-center text-muted py-4">
                    <i class="fas fa-inbox fa-2x mb-3 d-block"></i>
                    Your watchlist is empty. Add stocks above to get started.
                </td>
            </tr>
        `;
        return;
    }

    // Populate table
    tbody.innerHTML = watchlistData.map(item => {
        const symbol = item.symbol;
        const analysis = item.analysis;
        const error = item.error;

        if (!analysis) {
            return `
                <tr class="table-danger">
                    <td><strong>${symbol}</strong></td>
                    <td colspan="8" class="text-muted">${error || 'Unable to fetch data'}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-danger" onclick="removeStock('${symbol}')">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        }

        // Format recommendation badge
        const rec = analysis.recommendation;
        let recClass = 'rec-hold';
        if (rec.includes('BUY')) recClass = rec.includes('STRONG') ? 'rec-strong-buy' : 'rec-buy';
        else if (rec.includes('SELL')) recClass = rec.includes('STRONG') ? 'rec-strong-sell' : 'rec-sell';

        // Format confidence bar
        const conf = analysis.confidence;
        let confClass = 'conf-medium';
        if (conf >= 7) confClass = 'conf-high';
        else if (conf <= 4) confClass = 'conf-low';

        // Format price change (fetch current vs previous if available)
        const currentPrice = formatCurrency(analysis.current_price);

        // Format entry zone
        const entryZone = analysis.entry_zone;

        // Format levels with colors
        const slClass = analysis.stop_loss_pct > 0 ? 'sell' : 'buy';
        const slValue = `₹${analysis.stop_loss.toFixed(2)} (${Math.abs(analysis.stop_loss_pct).toFixed(1)}%)`;

        const t1Value = `₹${analysis.target1.toFixed(2)} (+${analysis.target1_pct.toFixed(1)}%)`;
        const t2Value = `₹${analysis.target2.toFixed(2)} (+${analysis.target2_pct.toFixed(1)}%)`;

        // Technical signals as tags
        const signalsHtml = analysis.technical_signals
            .slice(0, 4)
            .map(sig => {
                let tagClass = 'primary';
                if (sig.includes('✅') || sig.includes('📈')) tagClass = 'success';
                else if (sig.includes('⚠️') || sig.includes('❌')) tagClass = 'danger';
                else if (sig.includes('🔄') || sig.includes('📊')) tagClass = 'warning';
                return `<span class="signal-tag ${tagClass}">${sig}</span>`;
            })
            .join('');

        return `
            <tr data-symbol="${symbol}">
                <td><strong class="text-primary">${symbol}</strong></td>
                <td class="${analysis.recommendation.includes('BUY') ? 'price-up' : analysis.recommendation.includes('SELL') ? 'price-down' : ''}">
                    ${currentPrice}
                </td>
                <td>
                    <span class="badge recommendation-badge ${recClass}">${rec}</span>
                </td>
                <td>
                    <div class="d-flex align-items-center gap-2">
                        <div class="confidence-bar">
                            <div class="confidence-fill ${confClass}" style="width: ${conf * 10}%"></div>
                        </div>
                        <small>${conf}/10</small>
                    </div>
                </td>
                <td>
                    <div class="level-row">
                        <span class="level-label">Entry:</span>
                        <span class="level-value">${entryZone}</span>
                    </div>
                </td>
                <td>
                    <div class="level-row">
                        <span class="level-label">SL:</span>
                        <span class="level-value ${slClass}">${slValue}</span>
                    </div>
                </td>
                <td>
                    <div class="level-row">
                        <span class="level-label">T1:</span>
                        <span class="level-value buy">${t1Value}</span>
                    </div>
                </td>
                <td>
                    <div class="level-row">
                        <span class="level-label">T2:</span>
                        <span class="level-value buy">${t2Value}</span>
                    </div>
                </td>
                <td class="analysis-section">
                    ${signalsHtml}
                    ${analysis.technical_signals.length > 4 ? `<br><small class="text-muted">+${analysis.technical_signals.length - 4} more</small>` : ''}
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-danger" onclick="removeStock('${symbol}')" title="Remove">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// Add stocks to watchlist
async function addStocks() {
    const input = document.getElementById('stock-input');
    const value = input.value.trim();

    if (!value) {
        alert('Please enter at least one stock symbol');
        return;
    }

    // Parse symbols (comma separated)
    const symbols = value.split(',').map(s => s.trim().toUpperCase()).filter(s => s);

    if (symbols.length === 0) {
        alert('No valid symbols found');
        return;
    }

    // Show loading
    toggleLoading(true);

    try {
        const response = await fetch('/api/watchlist', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ symbols: symbols })
        });

        const data = await response.json();

        if (response.ok) {
            // Clear input
            input.value = '';

            // Show success message
            showToast(`${data.message}`, 'success');

            // Reload watchlist
            await loadWatchlist();
        } else {
            showError(data.error || 'Failed to add stocks');
        }
    } catch (error) {
        console.error('Error adding stocks:', error);
        showError('Network error while adding stocks');
    } finally {
        toggleLoading(false);
    }
}

// Remove stock from watchlist
async function removeStock(symbol) {
    if (!confirm(`Remove ${symbol} from watchlist?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/watchlist/${symbol}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok) {
            showToast(`Removed ${symbol} from watchlist`, 'info');
            await loadWatchlist();
        } else {
            showError(data.error || 'Failed to remove stock');
        }
    } catch (error) {
        console.error('Error removing stock:', error);
        showError('Network error');
    }
}

// Clear entire watchlist
async function clearWatchlist() {
    if (!confirm('Clear entire watchlist? This cannot be undone.')) {
        return;
    }

    // Remove all items one by one (simple approach)
    const items = [...watchlistData];
    for (const item of items) {
        await removeStock(item.symbol);
    }
}

// Refresh watchlist manually
async function refreshWatchlist() {
    const btn = event.target.closest('button');
    const icon = btn.querySelector('i');
    icon.classList.add('fa-spin');

    await loadWatchlist();

    icon.classList.remove('fa-spin');
    showToast('Watchlist refreshed', 'success');
}

// Helper: Format currency
function formatCurrency(value) {
    if (value >= 10000000) {
        return '₹' + (value / 10000000).toFixed(2) + ' Cr';
    } else if (value >= 100000) {
        return '₹' + (value / 100000).toFixed(2) + ' L';
    } else if (value >= 1000) {
        return '₹' + (value / 1000).toFixed(2) + ' K';
    }
    return '₹' + value.toFixed(2);
}

// Helper: Toggle loading spinner
function toggleLoading(show) {
    const spinner = document.getElementById('loading-spinner');
    spinner.style.display = show ? 'block' : 'none';
}

// Helper: Show error message
function showError(message) {
    showToast(message, 'danger');
}

// Helper: Show toast notification
function showToast(message, type = 'info') {
    // Create toast container if not exists
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(container);
    }

    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', toastHtml);

    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
    toast.show();

    // Remove from DOM after hidden
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}
