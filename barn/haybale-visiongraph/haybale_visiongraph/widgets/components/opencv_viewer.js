/**
 * OpenCV Viewer JavaScript Component
 * 
 * Simple MJPEG image display component for streaming video.
 */

export default {
  template: `
    <div class="opencv-viewer-container" :style="containerStyle">
      <img 
        :src="endpoint" 
        class="opencv-viewer-img"
        :style="imageStyle"
        @error="onError"
        @load="onLoad"
      />
      <div v-if="error" class="opencv-viewer-error">
        {{ errorMessage }}
      </div>
    </div>
  `,
  
  props: {
    endpoint: {
      type: String,
      required: true
    }
  },
  
  data() {
    return {
      error: false,
      errorMessage: 'Stream unavailable',
      loaded: false
    }
  },
  
  computed: {
    containerStyle() {
      return {
        position: 'relative',
        width: '100%',
        height: '100%',
        backgroundColor: '#1a1a1a',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden'
      }
    },
    
    imageStyle() {
      return {
        maxWidth: '100%',
        maxHeight: '100%',
        objectFit: 'contain',
        display: this.error ? 'none' : 'block'
      }
    }
  },
  
  methods: {
    onError(event) {
      this.error = true
      this.loaded = false
      console.error('OpenCV Viewer: Stream error', event)
    },
    
    onLoad(event) {
      this.error = false
      this.loaded = true
    }
  },
  
  mounted() {
    console.log('OpenCV Viewer mounted with endpoint:', this.endpoint)
  }
}