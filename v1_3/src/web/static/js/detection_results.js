/**
 * AI Camera v1.3 - Detection Results JavaScript
 * 
 * Handles the detection results table with pagination, search, filter, sort,
 * and detail view functionality.
 */

// Detection Results state management
const DetectionResultsManager = {
    currentPage: 1,
    perPage: 20,
    totalPages: 0,
    currentSort: { by: 'created_at', order: 'desc' },
    currentFilters: {
        search: '',
        dateFrom: '',
        dateTo: '',
        hasVehicles: '',
        hasPlates: ''
    },
    isLoading: false,

    /**
     * Initialize detection results manager
     */
    init: function() {
        this.setupEventHandlers();
        this.loadResults();
        this.loadStatistics();
        console.log('DetectionResultsManager initialized');
    },

    /**
     * Setup event handlers for UI interactions
     */
    setupEventHandlers: function() {
        // Search input with debounce
        let searchTimeout;
        document.getElementById('search-input').addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                this.currentFilters.search = e.target.value;
                this.currentPage = 1;
                this.loadResults();
            }, 500);
        });

        // Date filters
        document.getElementById('date-from').addEventListener('change', (e) => {
            this.currentFilters.dateFrom = e.target.value;
            this.currentPage = 1;
            this.loadResults();
        });

        document.getElementById('date-to').addEventListener('change', (e) => {
            this.currentFilters.dateTo = e.target.value;
            this.currentPage = 1;
            this.loadResults();
        });

        // Vehicle filter
        document.getElementById('has-vehicles').addEventListener('change', (e) => {
            this.currentFilters.hasVehicles = e.target.value;
            this.currentPage = 1;
            this.loadResults();
        });

        // Plates filter
        document.getElementById('has-plates').addEventListener('change', (e) => {
            this.currentFilters.hasPlates = e.target.value;
            this.currentPage = 1;
            this.loadResults();
        });

        // Per page selector
        document.getElementById('per-page-select').addEventListener('change', (e) => {
            this.perPage = parseInt(e.target.value);
            this.currentPage = 1;
            this.loadResults();
        });

        // Clear filters button
        document.getElementById('clear-filters-btn').addEventListener('click', () => {
            this.clearFilters();
        });

        // Refresh button
        document.getElementById('refresh-results-btn').addEventListener('click', () => {
            this.loadResults();
            this.loadStatistics();
        });

        // Export button
        document.getElementById('export-results-btn').addEventListener('click', () => {
            this.showExportModal();
        });

        // Export confirmation
        document.getElementById('confirm-export-btn').addEventListener('click', () => {
            this.exportResults();
        });

        // Table sorting
        document.querySelectorAll('.sortable').forEach(header => {
            header.addEventListener('click', () => {
                const sortBy = header.dataset.sort;
                this.handleSort(sortBy);
            });
        });
    },

    /**
     * Load detection results with current parameters
     */
    loadResults: function() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading();

        // Build query parameters
        const params = new URLSearchParams({
            page: this.currentPage,
            per_page: this.perPage,
            sort_by: this.currentSort.by,
            sort_order: this.currentSort.order
        });

        // Add filters
        if (this.currentFilters.search) {
            params.append('search', this.currentFilters.search);
        }
        if (this.currentFilters.dateFrom) {
            params.append('date_from', this.currentFilters.dateFrom);
        }
        if (this.currentFilters.dateTo) {
            params.append('date_to', this.currentFilters.dateTo);
        }
        if (this.currentFilters.hasVehicles) {
            params.append('has_vehicles', this.currentFilters.hasVehicles);
        }
        if (this.currentFilters.hasPlates) {
            params.append('has_plates', this.currentFilters.hasPlates);
        }

        // Make API request
        AICameraUtils.apiRequest(`/detection_results/api/results?${params.toString()}`)
            .then(data => {
                if (data && data.success) {
                    this.displayResults(data.results, data.pagination);
                } else {
                    this.showError(data?.error || 'Failed to load results');
                }
            })
            .catch(error => {
                console.error('Error loading detection results:', error);
                this.showError('Network error occurred while loading results');
            })
            .finally(() => {
                this.isLoading = false;
            });
    },

    /**
     * Display results in the table
     */
    displayResults: function(results, pagination) {
        const tableBody = document.getElementById('results-table-body');
        const tableContainer = document.getElementById('results-table-container');
        const emptyState = document.getElementById('empty-state');
        const errorState = document.getElementById('error-state');
        const loadingSpinner = document.getElementById('loading-spinner');
        const paginationContainer = document.getElementById('pagination-container');

        // Hide loading and error states
        loadingSpinner.style.display = 'none';
        errorState.style.display = 'none';

        if (results.length === 0) {
            // Show empty state
            tableContainer.style.display = 'none';
            paginationContainer.style.display = 'none';
            emptyState.style.display = 'block';
            this.updateResultsCount(0, 0);
            return;
        }

        // Show table
        emptyState.style.display = 'none';
        tableContainer.style.display = 'block';
        paginationContainer.style.display = 'block';

        // Clear existing rows
        tableBody.innerHTML = '';

        // Populate table rows
        results.forEach(result => {
            const row = this.createTableRow(result);
            tableBody.appendChild(row);
        });

        // Update pagination
        this.updatePagination(pagination);
        this.updateResultsCount(pagination.total, results.length);
        this.updateSortIndicators();
    },

    /**
     * Create a table row for a detection result
     */
    createTableRow: function(result) {
        const row = document.createElement('tr');
        row.className = 'table-row-clickable';
        
        const formatDate = (dateStr) => {
            const date = new Date(dateStr);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        };

        const truncateText = (text, maxLength = 50) => {
            if (text.length <= maxLength) return text;
            return text.substring(0, maxLength) + '...';
        };

        row.innerHTML = `
            <td class="fw-bold">#${result.id}</td>
            <td>${formatDate(result.created_at)}</td>
            <td>
                <span class="badge ${result.has_vehicles ? 'bg-success' : 'bg-secondary'}">
                    ${result.vehicles_count} ${result.vehicles_count === 1 ? 'vehicle' : 'vehicles'}
                </span>
            </td>
            <td>
                <span class="badge ${result.has_plates ? 'bg-info' : 'bg-secondary'}">
                    ${result.plates_count} ${result.plates_count === 1 ? 'plate' : 'plates'}
                </span>
            </td>
            <td>
                <div class="ocr-results">
                    ${result.ocr_text ? 
                        `<span class="text-primary fw-bold">${truncateText(result.ocr_text)}</span>
                         ${result.confidence_avg > 0 ? `<small class="text-muted">(${result.confidence_avg}%)</small>` : ''}` 
                        : '<span class="text-muted">No text detected</span>'}
                </div>
            </td>
            <td>${result.processing_time_ms.toFixed(1)}ms</td>
            <td>
                <button type="button" class="btn btn-sm btn-outline-primary" 
                        onclick="DetectionResultsManager.showDetail(${result.id})" 
                        title="View Details">
                    <i class="fas fa-eye"></i>
                </button>
            </td>
        `;

        return row;
    },

    /**
     * Update pagination controls
     */
    updatePagination: function(pagination) {
        this.totalPages = pagination.total_pages;
        const paginationNav = document.getElementById('pagination-nav');
        const paginationInfo = document.getElementById('pagination-info');

        // Update pagination info
        const start = ((pagination.page - 1) * pagination.per_page) + 1;
        const end = Math.min(pagination.page * pagination.per_page, pagination.total);
        paginationInfo.textContent = `Showing ${start}-${end} of ${pagination.total} results`;

        // Clear existing pagination buttons
        paginationNav.innerHTML = '';

        if (pagination.total_pages <= 1) return;

        // Previous button
        const prevBtn = document.createElement('li');
        prevBtn.className = `page-item ${!pagination.has_prev ? 'disabled' : ''}`;
        prevBtn.innerHTML = `
            <a class="page-link" href="#" onclick="DetectionResultsManager.goToPage(${pagination.page - 1}); return false;">
                <i class="fas fa-chevron-left"></i> Previous
            </a>
        `;
        paginationNav.appendChild(prevBtn);

        // Page numbers
        const startPage = Math.max(1, pagination.page - 2);
        const endPage = Math.min(pagination.total_pages, pagination.page + 2);

        if (startPage > 1) {
            const firstBtn = document.createElement('li');
            firstBtn.className = 'page-item';
            firstBtn.innerHTML = `<a class="page-link" href="#" onclick="DetectionResultsManager.goToPage(1); return false;">1</a>`;
            paginationNav.appendChild(firstBtn);

            if (startPage > 2) {
                const ellipsis = document.createElement('li');
                ellipsis.className = 'page-item disabled';
                ellipsis.innerHTML = '<span class="page-link">...</span>';
                paginationNav.appendChild(ellipsis);
            }
        }

        for (let i = startPage; i <= endPage; i++) {
            const pageBtn = document.createElement('li');
            pageBtn.className = `page-item ${i === pagination.page ? 'active' : ''}`;
            pageBtn.innerHTML = `<a class="page-link" href="#" onclick="DetectionResultsManager.goToPage(${i}); return false;">${i}</a>`;
            paginationNav.appendChild(pageBtn);
        }

        if (endPage < pagination.total_pages) {
            if (endPage < pagination.total_pages - 1) {
                const ellipsis = document.createElement('li');
                ellipsis.className = 'page-item disabled';
                ellipsis.innerHTML = '<span class="page-link">...</span>';
                paginationNav.appendChild(ellipsis);
            }

            const lastBtn = document.createElement('li');
            lastBtn.className = 'page-item';
            lastBtn.innerHTML = `<a class="page-link" href="#" onclick="DetectionResultsManager.goToPage(${pagination.total_pages}); return false;">${pagination.total_pages}</a>`;
            paginationNav.appendChild(lastBtn);
        }

        // Next button
        const nextBtn = document.createElement('li');
        nextBtn.className = `page-item ${!pagination.has_next ? 'disabled' : ''}`;
        nextBtn.innerHTML = `
            <a class="page-link" href="#" onclick="DetectionResultsManager.goToPage(${pagination.page + 1}); return false;">
                Next <i class="fas fa-chevron-right"></i>
            </a>
        `;
        paginationNav.appendChild(nextBtn);
    },

    /**
     * Go to specific page
     */
    goToPage: function(page) {
        if (page < 1 || page > this.totalPages || page === this.currentPage) return;
        this.currentPage = page;
        this.loadResults();
    },

    /**
     * Handle column sorting
     */
    handleSort: function(sortBy) {
        if (this.currentSort.by === sortBy) {
            // Toggle sort order
            this.currentSort.order = this.currentSort.order === 'asc' ? 'desc' : 'asc';
        } else {
            // New sort column
            this.currentSort.by = sortBy;
            this.currentSort.order = 'desc';
        }
        
        this.currentPage = 1;
        this.loadResults();
    },

    /**
     * Update sort indicators in table headers
     */
    updateSortIndicators: function() {
        // Reset all sort icons
        document.querySelectorAll('.sort-icon').forEach(icon => {
            icon.className = 'fas fa-sort sort-icon';
        });

        // Update active sort icon
        const activeHeader = document.querySelector(`[data-sort="${this.currentSort.by}"]`);
        if (activeHeader) {
            const icon = activeHeader.querySelector('.sort-icon');
            if (icon) {
                icon.className = `fas fa-sort-${this.currentSort.order === 'asc' ? 'up' : 'down'} sort-icon active`;
            }
        }
    },

    /**
     * Clear all filters
     */
    clearFilters: function() {
        // Reset filter inputs
        document.getElementById('search-input').value = '';
        document.getElementById('date-from').value = '';
        document.getElementById('date-to').value = '';
        document.getElementById('has-vehicles').value = '';
        document.getElementById('has-plates').value = '';

        // Reset filter state
        this.currentFilters = {
            search: '',
            dateFrom: '',
            dateTo: '',
            hasVehicles: '',
            hasPlates: ''
        };

        this.currentPage = 1;
        this.loadResults();
    },

    /**
     * Show loading state
     */
    showLoading: function() {
        document.getElementById('loading-spinner').style.display = 'block';
        document.getElementById('results-table-container').style.display = 'none';
        document.getElementById('empty-state').style.display = 'none';
        document.getElementById('error-state').style.display = 'none';
        document.getElementById('pagination-container').style.display = 'none';
    },

    /**
     * Show error state
     */
    showError: function(message) {
        document.getElementById('loading-spinner').style.display = 'none';
        document.getElementById('results-table-container').style.display = 'none';
        document.getElementById('empty-state').style.display = 'none';
        document.getElementById('pagination-container').style.display = 'none';
        
        const errorState = document.getElementById('error-state');
        const errorMessage = document.getElementById('error-message');
        errorMessage.textContent = message;
        errorState.style.display = 'block';
    },

    /**
     * Update results count display
     */
    updateResultsCount: function(total, showing) {
        const resultsCount = document.getElementById('results-count');
        if (total === 0) {
            resultsCount.textContent = 'No results found';
        } else {
            resultsCount.textContent = `${total} total results`;
        }
    },

    /**
     * Show detail modal for a specific result
     */
    showDetail: function(resultId) {
        const modal = new bootstrap.Modal(document.getElementById('detail-modal'));
        const modalBody = document.getElementById('detail-modal-body');
        
        // Show loading in modal
        modalBody.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div class="mt-2">Loading detection details...</div>
            </div>
        `;
        
        modal.show();

        // Load detailed data
        AICameraUtils.apiRequest(`/detection_results/api/results/${resultId}`)
            .then(data => {
                if (data && data.success) {
                    this.displayDetailModal(data.result);
                } else {
                    modalBody.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            Error loading details: ${data?.error || 'Unknown error'}
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error loading detail:', error);
                modalBody.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        Network error occurred while loading details.
                    </div>
                `;
            });
    },

    /**
     * Display detailed result in modal
     */
    displayDetailModal: function(result) {
        const modalBody = document.getElementById('detail-modal-body');
        
        const formatDate = (dateStr) => {
            const date = new Date(dateStr);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        };

        const renderDetections = (detections, type) => {
            if (!detections || detections.length === 0) {
                return `<p class="text-muted">No ${type} detected</p>`;
            }

            return detections.map(detection => `
                <div class="detection-item mb-2 p-2 border rounded">
                    <div class="row">
                        <div class="col-md-6">
                            <strong>Confidence:</strong> ${(detection.confidence * 100 || detection.score * 100 || 0).toFixed(1)}%
                        </div>
                        <div class="col-md-6">
                            <strong>Label:</strong> ${detection.label || detection.class_name || 'Unknown'}
                        </div>
                        <div class="col-12 mt-1">
                            <strong>Bounding Box:</strong> 
                            [${detection.bbox ? detection.bbox.map(b => Math.round(b)).join(', ') : 'N/A'}]
                        </div>
                    </div>
                </div>
            `).join('');
        };

        const renderOCRResults = (ocrResults) => {
            if (!ocrResults || ocrResults.length === 0) {
                return `<p class="text-muted">No OCR results available</p>`;
            }

            return ocrResults.map(ocr => `
                <div class="ocr-item mb-2 p-2 border rounded">
                    <div class="row">
                        <div class="col-md-8">
                            <strong class="text-primary">${ocr.text || 'N/A'}</strong>
                        </div>
                        <div class="col-md-4 text-end">
                            <span class="badge bg-info">${(ocr.confidence || 0).toFixed(1)}%</span>
                        </div>
                    </div>
                </div>
            `).join('');
        };

        modalBody.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <div class="card mb-3">
                        <div class="card-header">
                            <h6 class="mb-0"><i class="fas fa-info-circle me-2"></i>Basic Information</h6>
                        </div>
                        <div class="card-body">
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>ID:</strong></td>
                                    <td>#${result.id}</td>
                                </tr>
                                <tr>
                                    <td><strong>Date/Time:</strong></td>
                                    <td>${formatDate(result.created_at)}</td>
                                </tr>
                                <tr>
                                    <td><strong>Processing Time:</strong></td>
                                    <td>${result.processing_time_ms.toFixed(1)}ms</td>
                                </tr>
                                <tr>
                                    <td><strong>Vehicles Found:</strong></td>
                                    <td><span class="badge ${result.vehicles_count > 0 ? 'bg-success' : 'bg-secondary'}">${result.vehicles_count}</span></td>
                                </tr>
                                <tr>
                                    <td><strong>Plates Found:</strong></td>
                                    <td><span class="badge ${result.plates_count > 0 ? 'bg-info' : 'bg-secondary'}">${result.plates_count}</span></td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card mb-3">
                        <div class="card-header">
                            <h6 class="mb-0"><i class="fas fa-font me-2"></i>OCR Results</h6>
                        </div>
                        <div class="card-body">
                            ${renderOCRResults(result.ocr_results)}
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-6">
                    <div class="card mb-3">
                        <div class="card-header">
                            <h6 class="mb-0"><i class="fas fa-car me-2"></i>Vehicle Detections</h6>
                        </div>
                        <div class="card-body">
                            ${renderDetections(result.vehicle_detections, 'vehicles')}
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card mb-3">
                        <div class="card-header">
                            <h6 class="mb-0"><i class="fas fa-id-card me-2"></i>License Plate Detections</h6>
                        </div>
                        <div class="card-body">
                            ${renderDetections(result.plate_detections, 'license plates')}
                        </div>
                    </div>
                </div>
            </div>
            
            ${result.annotated_image_path ? `
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0"><i class="fas fa-image me-2"></i>Annotated Image</h6>
                    </div>
                    <div class="card-body">
                        <p class="text-muted">Image path: ${result.annotated_image_path}</p>
                        <p class="text-info"><i class="fas fa-info-circle me-1"></i>Image display functionality would be implemented based on your image serving setup.</p>
                    </div>
                </div>
            ` : ''}
        `;
    },

    /**
     * Show export modal
     */
    showExportModal: function() {
        const modal = new bootstrap.Modal(document.getElementById('export-modal'));
        modal.show();
    },

    /**
     * Export results with current filters
     */
    exportResults: function() {
        const format = document.getElementById('export-format').value;
        
        // Build query parameters (same as loadResults but without pagination)
        const params = new URLSearchParams({
            format: format,
            sort_by: this.currentSort.by,
            sort_order: this.currentSort.order
        });

        // Add current filters
        if (this.currentFilters.search) {
            params.append('search', this.currentFilters.search);
        }
        if (this.currentFilters.dateFrom) {
            params.append('date_from', this.currentFilters.dateFrom);
        }
        if (this.currentFilters.dateTo) {
            params.append('date_to', this.currentFilters.dateTo);
        }
        if (this.currentFilters.hasVehicles) {
            params.append('has_vehicles', this.currentFilters.hasVehicles);
        }
        if (this.currentFilters.hasPlates) {
            params.append('has_plates', this.currentFilters.hasPlates);
        }

        // Create download link
        const url = `/detection_results/api/export?${params.toString()}`;
        const link = document.createElement('a');
        link.href = url;
        link.download = `detection_results_${new Date().toISOString().slice(0, 10)}.${format}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('export-modal'));
        modal.hide();

        AICameraUtils.showToast('Export started', 'success');
    },

    /**
     * Load and update statistics
     */
    loadStatistics: function() {
        AICameraUtils.apiRequest('/detection_results/api/statistics')
            .then(data => {
                if (data && data.success) {
                    this.updateStatistics(data.statistics);
                }
            })
            .catch(error => {
                console.error('Error loading statistics:', error);
            });
    },

    /**
     * Update statistics display
     */
    updateStatistics: function(stats) {
        document.getElementById('total-detections').textContent = stats.total_detections || 0;
        document.getElementById('total-vehicles').textContent = stats.total_vehicles || 0;
        document.getElementById('total-plates').textContent = stats.total_plates || 0;
        document.getElementById('avg-processing-time').textContent = `${(stats.avg_processing_time_ms || 0).toFixed(1)}ms`;
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    DetectionResultsManager.init();
    console.log('Detection Results JavaScript loaded');
});
