<template>
  <div class="detection-detail">
    <!-- Breadcrumb -->
    <div class="breadcrumb">
      <span class="back-link" @click="$router.push('/detections')">◎ Detections</span>
      <span class="sep">›</span>
      <span class="crumb-current font-thai">{{ detection?.licensePlate || id }}</span>
    </div>

    <!-- Loading -->
    <div class="skeleton-card" v-if="loading" />

    <!-- Main card -->
    <div class="detail-card panel" v-else-if="detection">
      <div class="card-left">
        <!-- Image -->
        <div class="img-wrap" :class="{ clickable: detection.imagePath }"
             @click="detection.imagePath && (viewerOpen = true)">
          <img v-if="detection.imagePath"
               :src="imageUrl"
               class="thumb"
               :class="{ loaded: imgLoaded }"
               @load="imgLoaded = true"
               @error="imgLoaded = true; imgBroken = true"
               alt="detection" />
          <div v-if="imgBroken || !detection.imagePath" class="no-img text-muted">
            {{ detection.imagePath ? 'Image unavailable' : 'No image' }}
          </div>
          <div v-if="detection.imagePath && !imgBroken" class="img-overlay">
            <span>🔍 View full</span>
          </div>
        </div>
      </div>

      <div class="card-right">
        <!-- Plate -->
        <PlateTag :plate="detection.licensePlate" size="lg" />

        <!-- Confidence -->
        <div class="field" style="margin-top: 1.25rem">
          <div class="field-label">Confidence</div>
          <ConfidenceBar :value="detection.confidence" style="max-width: 200px" />
        </div>

        <!-- Meta grid -->
        <div class="meta-grid">
          <div class="meta-item">
            <span class="field-label">Camera</span>
            <span class="meta-val font-data">{{ detection.camera?.cameraId || '—' }}</span>
          </div>
          <div class="meta-item">
            <span class="field-label">Timestamp</span>
            <span class="meta-val font-data">{{ fmtTs(detection.timestamp) }}</span>
          </div>
          <div class="meta-item">
            <span class="field-label">Detection ID</span>
            <span class="meta-val font-data id-text">{{ detection.id }}</span>
          </div>
          <div class="meta-item">
            <span class="field-label">Status</span>
            <span class="meta-val">
              <span class="badge" :class="detection.archived ? 'badge-amber' : 'badge-green'">
                {{ detection.archived ? 'Archived' : 'Active' }}
              </span>
            </span>
          </div>
        </div>

        <!-- Actions -->
        <div class="action-row">
          <button class="btn" v-if="!detection.archived"
                  :disabled="archiving" @click="doArchive">
            {{ archiving ? 'Archiving…' : '⊘ Archive' }}
          </button>
          <button class="btn" v-else
                  :disabled="archiving" @click="doUnarchive">
            {{ archiving ? 'Restoring…' : '↩ Restore' }}
          </button>
          <button class="btn" v-if="detection.imagePath"
                  @click="viewerOpen = true">
            🔍 View Image
          </button>
        </div>

        <div v-if="actionError" class="form-error">⚠ {{ actionError }}</div>
      </div>
    </div>

    <ErrorBanner :message="error" @retry="retry" />

    <!-- Image viewer modal -->
    <ImageViewer
      v-if="viewerOpen && detection?.imagePath"
      :src="imageUrl"
      :caption="{
        plate:      detection.licensePlate,
        confidence: confPct,
        camera:     detection.camera?.cameraId,
        timestamp:  fmtTs(detection.timestamp),
      }"
      @close="viewerOpen = false"
    />
  </div>
</template>

<script>
import PlateTag      from '@/components/shared/PlateTag.vue';
import ConfidenceBar from '@/components/shared/ConfidenceBar.vue';
import ImageViewer   from '@/components/shared/ImageViewer.vue';
import ErrorBanner   from '@/components/shared/ErrorBanner.vue';
import api           from '@/api/index.js';

export default {
  name: 'DetectionDetail',
  components: { PlateTag, ConfidenceBar, ImageViewer, ErrorBanner },
  props: { id: { type: String, required: true } },
  data() {
    return {
      detection:   null,
      loading:     true,
      error:       null,
      actionError: null,
      archiving:   false,
      viewerOpen:  false,
      imgLoaded:   false,
      imgBroken:   false,
    };
  },
  computed: {
    imageUrl() {
      return this.detection?.imagePath ? api.getDetectionImageUrl(this.id) : '';
    },
    confPct() {
      const v = parseFloat(this.detection?.confidence);
      return isNaN(v) ? '' : (v * 100).toFixed(0) + '%';
    },
  },
  mounted() {
    this.load();
  },
  methods: {
    retry() { this.load(); },

    async load() {
      this.loading = true;
      try {
        this.detection = await api.getDetection(this.id);
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },
    async doArchive() {
      this.archiving   = true;
      this.actionError = null;
      try {
        await api.archiveDetection(this.id);
        this.detection.archived = true;
      } catch (e) {
        this.actionError = e.message;
      } finally {
        this.archiving = false;
      }
    },
    async doUnarchive() {
      this.archiving   = true;
      this.actionError = null;
      try {
        await api.unarchiveDetection(this.id);
        this.detection.archived = false;
      } catch (e) {
        this.actionError = e.message;
      } finally {
        this.archiving = false;
      }
    },
    fmtTs(ts) {
      if (!ts) return '—';
      return new Date(ts).toLocaleString('th-TH', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    },
  },
};
</script>

<style scoped>
.detection-detail { max-width: 960px; }

/* Breadcrumb */
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 1.25rem;
}
.back-link { color: var(--cyan-dim); cursor: pointer; transition: color var(--transition); }
.back-link:hover { color: var(--cyan); }
.sep { opacity: 0.4; }
.crumb-current { color: var(--text-secondary); }

/* Skeleton */
.skeleton-card {
  height: 300px;
  background: linear-gradient(90deg, var(--bg-panel) 25%, var(--bg-surface) 50%, var(--bg-panel) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-md);
}
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

/* Main card */
.detail-card {
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
}

/* Image side */
.card-left { flex: 0 0 auto; }
.img-wrap {
  position: relative;
  width: 320px;
  max-width: 100%;
  height: 220px;
  background: var(--bg-surface);
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-md);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.img-wrap.clickable { cursor: pointer; }
.img-wrap.clickable:hover .img-overlay { opacity: 1; }

.thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transition: opacity 0.3s ease;
  display: block;
}
.thumb.loaded { opacity: 1; }
.no-img { font-size: 12px; }

.img-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--cyan);
  font-size: 13px;
  opacity: 0;
  transition: opacity var(--transition);
}

/* Info side */
.card-right { flex: 1; min-width: 260px; display: flex; flex-direction: column; }

.field { display: flex; flex-direction: column; gap: 4px; }
.field-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  color: var(--text-muted);
}

.meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-top: 1.25rem;
}
.meta-item { display: flex; flex-direction: column; gap: 3px; }
.meta-val { font-size: 13px; color: var(--text-primary); }
.id-text { font-size: 10px; color: var(--text-muted); word-break: break-all; }

.action-row {
  display: flex;
  gap: 0.5rem;
  margin-top: 1.5rem;
  flex-wrap: wrap;
}

.form-error {
  margin-top: 0.75rem;
  padding: 8px 10px;
  background: var(--red-dim);
  border: 1px solid rgba(255,61,87,0.3);
  border-radius: var(--radius-sm);
  color: var(--red);
  font-size: 12px;
}

</style>
