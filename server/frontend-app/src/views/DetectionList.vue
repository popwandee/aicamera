<template>
  <div class="detection-list">
    <!-- Header -->
    <div class="page-header">
      <div>
        <div class="page-title font-display">◎ Detection Log</div>
        <div class="page-desc">License plate detections — filter, browse, export</div>
      </div>
      <div class="header-actions">
        <span class="live-badge" v-if="socketOk">● LIVE</span>
        <span class="new-badge" v-if="newCount > 0" @click="refresh">
          +{{ newCount }} new — click to refresh
        </span>
        <button class="btn" :disabled="!store.filtered.length" @click="exportCSV">
          ⬇ CSV
        </button>
      </div>
    </div>

    <!-- Filter bar -->
    <FilterBar
      v-model="store.filters"
      :cameras="cameras"
      :count="store.filtered.length"
      @update:modelValue="onFilterChange"
      @clear="clearFilters"
    />

    <!-- Table -->
    <div class="table-wrap panel" v-if="!store.loading">
      <table class="data-table" v-if="store.currentPage.length">
        <thead>
          <tr>
            <th class="col-thumb"></th>
            <th class="col-plate">Plate</th>
            <th>Camera</th>
            <th class="col-conf">Confidence</th>
            <th class="col-time">Timestamp</th>
            <th class="col-arch" title="Archived">⊘</th>
            <th class="col-actions"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in store.currentPage" :key="d.id"
              class="table-row" @click="goToDetail(d.id)">
            <td class="col-thumb">
              <img v-if="d.imagePath"
                   :src="thumbUrl(d.id)"
                   class="thumb-img"
                   loading="lazy"
                   alt=""
                   @error="$event.target.style.visibility='hidden'" />
              <div v-else class="thumb-none" />
            </td>
            <td class="col-plate">
              <PlateTag :plate="d.licensePlate" size="sm" />
            </td>
            <td class="cam-cell font-data text-muted">
              {{ d.camera?.cameraId || '—' }}
            </td>
            <td class="col-conf">
              <ConfidenceBar :value="d.confidence" />
            </td>
            <td class="col-time font-data text-muted">{{ fmtTs(d.timestamp) }}</td>
            <td class="col-arch">
              <span v-if="d.archived" class="arch-dot text-muted" title="Archived">⊘</span>
            </td>
            <td class="col-actions" @click.stop>
              <button class="action-btn action-edit" title="Edit"
                      @click="openEdit(d)">✎</button>
              <button class="action-btn action-delete" title="Delete"
                      @click="confirmDelete(d)">✕</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="empty-state text-muted" v-else>
        {{ store.items.length ? 'No results match the current filters.' : 'No detections found.' }}
      </div>
    </div>

    <!-- Skeleton -->
    <div class="table-wrap panel skeleton-wrap" v-else>
      <div class="skeleton-row" v-for="n in 8" :key="n" />
    </div>

    <!-- Pagination -->
    <div class="pagination" v-if="store.pageCount > 1">
      <button class="page-btn" :disabled="!store.hasPrev" @click="store.prevPage()">‹ Prev</button>
      <span class="page-info font-data">
        {{ store.page + 1 }} / {{ store.pageCount }}
        <span class="text-muted">({{ store.filtered.length }} results)</span>
      </span>
      <button class="page-btn" :disabled="!store.hasNext" @click="store.nextPage()">Next ›</button>
    </div>

    <ErrorBanner :message="store.error" @retry="retry" />

    <!-- Edit modal -->
    <EditDetectionModal
      v-if="editTarget"
      :detection="editTarget"
      @close="editTarget = null"
      @updated="onUpdated"
    />

    <!-- Delete confirm -->
    <div class="modal-backdrop" v-if="deleteTarget" @click.self="deleteTarget = null">
      <div class="confirm-box panel">
        <div class="confirm-title">Delete Detection?</div>
        <div class="confirm-body">
          Permanently remove plate
          <span class="font-data text-cyan font-thai">{{ deleteTarget.licensePlate || '—' }}</span>
          from the database? This cannot be undone.
        </div>
        <div class="confirm-actions">
          <button class="btn" @click="deleteTarget = null">Cancel</button>
          <button class="btn btn-danger" :disabled="deleting" @click="doDelete">
            {{ deleting ? 'Deleting…' : 'Delete' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import FilterBar           from '@/components/shared/FilterBar.vue';
import PlateTag            from '@/components/shared/PlateTag.vue';
import ConfidenceBar       from '@/components/shared/ConfidenceBar.vue';
import ErrorBanner         from '@/components/shared/ErrorBanner.vue';
import EditDetectionModal  from '@/components/detections/EditDetectionModal.vue';
import { useDetectionsStore } from '@/stores/detections.store.js';
import { useCamerasStore }    from '@/stores/cameras.store.js';
import { useSocket }          from '@/composables/useSocket.js';
import api from '@/api/index.js';

export default {
  name: 'DetectionList',
  components: { FilterBar, PlateTag, ConfidenceBar, ErrorBanner, EditDetectionModal },
  data() {
    return {
      cameras:      [],
      socketOk:     false,
      newCount:     0,
      editTarget:   null,
      deleteTarget: null,
      deleting:     false,
    };
  },
  setup() {
    const store  = useDetectionsStore();
    const camStore = useCamerasStore();
    const { socket, connected } = useSocket();
    return { store, camStore, socket, connected };
  },
  mounted() {
    this.store.fetchFiltered();
    this.loadCameras();
    this.socketOk = this.connected;
    this.socket.on('connect',       () => { this.socketOk = true; });
    this.socket.on('disconnect',    () => { this.socketOk = false; });
    this.socket.on('message_saved', () => { this.newCount++; });
  },
  methods: {
    retry() { this.store.fetchFiltered(); },

    async loadCameras() {
      try {
        this.cameras = await api.getCameras();
      } catch { /* non-fatal */ }
    },
    onFilterChange(newFilters) {
      this.store.filters = newFilters;
      // re-fetch from server only when server-side filters (cameraId, search, archived) change
      this.store.fetchFiltered();
      this.newCount = 0;
    },
    clearFilters() {
      this.store.resetFilters();
      this.store.fetchFiltered();
      this.newCount = 0;
    },
    refresh() {
      this.store.fetchFiltered();
      this.newCount = 0;
    },
    thumbUrl(id) {
      return api.getDetectionImageUrl(id);
    },
    goToDetail(id) {
      this.$router.push('/detections/' + id);
    },
    openEdit(detection) {
      this.editTarget = detection;
    },
    onUpdated() {
      this.editTarget = null;
    },
    confirmDelete(detection) {
      this.deleteTarget = detection;
    },
    async doDelete() {
      this.deleting = true;
      try {
        await this.store.removeDetection(this.deleteTarget.id);
        this.deleteTarget = null;
      } catch (e) {
        this.store.error = e.message;
      } finally {
        this.deleting = false;
      }
    },
    fmtTs(ts) {
      if (!ts) return '—';
      return new Date(ts).toLocaleString('th-TH', {
        year: '2-digit', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    },
    exportCSV() {
      const rows = this.store.filtered;
      const header = '"Date","Time","License Plate","Camera","Confidence %","Archived","Has Image"';
      const lines = rows.map(d => {
        const ts   = d.timestamp ? new Date(d.timestamp) : null;
        const date = ts ? ts.toLocaleDateString('en-CA') : '';
        const time = ts ? ts.toLocaleTimeString('th-TH') : '';
        const conf = d.confidence ? (parseFloat(d.confidence) * 100).toFixed(1) : '';
        return [
          date,
          time,
          d.licensePlate || '',
          d.camera?.cameraId || '',
          conf,
          d.archived ? 'Yes' : 'No',
          d.imagePath ? 'Yes' : 'No',
        ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(',');
      });
      const csv  = '﻿' + header + '\n' + lines.join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `detections-${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    },
  },
};
</script>

<style scoped>
.detection-list { max-width: 1200px; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-dim);
}
.page-title {
  font-size: 1.6rem; font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--cyan); text-shadow: var(--cyan-glow);
}
.page-desc { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding-top: 4px;
}
.live-badge {
  font-size: 10px;
  color: var(--green);
  animation: blink 2s infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.4} }

.new-badge {
  font-size: 11px;
  color: var(--amber);
  border: 1px solid rgba(255,171,64,0.3);
  border-radius: var(--radius-sm);
  padding: 3px 9px;
  cursor: pointer;
  transition: background var(--transition);
}
.new-badge:hover { background: var(--amber-dim); }

/* Table */
.table-wrap { padding: 0; overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th {
  padding: 8px 12px;
  text-align: left;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-dim);
  white-space: nowrap;
}
.data-table td {
  padding: 9px 12px;
  border-bottom: 1px solid var(--border-dim);
  vertical-align: middle;
}
.table-row { cursor: pointer; transition: background var(--transition); }
.table-row:hover { background: var(--bg-hover); }
.table-row:last-child td { border-bottom: none; }

.col-actions { width: 64px; text-align: center; white-space: nowrap; }
.action-btn {
  background: none; border: none; color: var(--text-muted);
  cursor: pointer; font-size: 12px; padding: 3px 6px;
  border-radius: var(--radius-sm);
  transition: color var(--transition), background var(--transition);
}
.action-edit:hover   { color: var(--cyan); background: rgba(0,200,255,0.08); }
.action-delete:hover { color: var(--red);  background: var(--red-dim); }

/* Delete confirm modal */
.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(8,12,18,0.80);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000; backdrop-filter: blur(2px);
}
.confirm-box { width: 400px; max-width: calc(100vw - 2rem); }
.confirm-title { font-size: 1rem; font-weight: 600; color: var(--red); margin-bottom: 0.75rem; }
.confirm-body  { font-size: 13px; color: var(--text-secondary); margin-bottom: 1.25rem; line-height: 1.6; }
.confirm-actions { display: flex; justify-content: flex-end; gap: 0.5rem; }
.btn-danger { border-color: rgba(255,61,87,0.5); color: var(--red); }
.btn-danger:hover { background: var(--red-dim); }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

.col-thumb { width: 62px; padding: 4px 6px !important; }
.thumb-img {
  width: 50px;
  height: 50px;
  object-fit: cover;
  border-radius: 3px;
  display: block;
  background: var(--bg-surface);
}
.thumb-none {
  width: 50px;
  height: 50px;
  border-radius: 3px;
  background: var(--bg-surface);
  border: 1px solid var(--border-dim);
}
.col-plate { min-width: 140px; }
.col-conf  { min-width: 130px; }
.col-time  { text-align: right; white-space: nowrap; width: 130px; }
.col-arch  { text-align: center; width: 30px; }
.cam-cell  { font-size: 11px; }
.arch-dot  { font-size: 12px; }

.empty-state {
  padding: 3rem 1rem;
  text-align: center;
  font-size: 13px;
}

/* Skeleton */
.skeleton-wrap { padding: 1rem; display: flex; flex-direction: column; gap: 0.5rem; }
.skeleton-row {
  height: 38px;
  background: linear-gradient(90deg, var(--bg-panel) 25%, var(--bg-surface) 50%, var(--bg-panel) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

/* Pagination */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-top: 1rem;
}
.page-btn {
  background: none;
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  color: var(--cyan-dim);
  cursor: pointer;
  font-size: 12px;
  padding: 5px 14px;
  transition: border-color var(--transition), color var(--transition);
}
.page-btn:hover:not(:disabled) { border-color: var(--border-bright); color: var(--cyan); }
.page-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.page-info { font-size: 12px; color: var(--text-secondary); }

</style>
