/**
 * OpenCV Viewer JavaScript Component
 *
 * MJPEG image display component for streaming video.
 *
 * Instead of binding <img src> directly to the MJPEG endpoint (a never-ending
 * multipart/x-mixed-replace response), this component consumes the stream via
 * fetch() + ReadableStream and parses the multipart frames itself, assigning
 * each decoded JPEG to the <img> as an object URL.
 *
 * Why: an open <img src> pointing at an endless stream keeps the browser's
 * page-load indicator (tab throbber / "Waiting for …") active for as long as
 * the image is in the DOM. A fetch()-driven read does not feed that indicator,
 * so the tab settles while the live stream keeps updating. The fetch is aborted
 * on unmount so the server-side client disconnects cleanly.
 */

export default {
  template: `
    <div class="opencv-viewer-container" :style="containerStyle">
      <img
        ref="img"
        class="opencv-viewer-img"
        :style="imageStyle"
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
    /**
     * Open the MJPEG stream via fetch() and pump decoded frames into the <img>.
     * Retries with backoff if the stream ends or errors, unless we've unmounted.
     */
    async _startStream() {
      while (!this._stopped) {
        this._abort = new AbortController()
        try {
          const response = await fetch(this.endpoint, { signal: this._abort.signal })
          if (!response.ok || !response.body) {
            throw new Error(`HTTP ${response.status}`)
          }
          this.error = false
          await this._consume(response.body.getReader())
        } catch (e) {
          if (this._stopped || e.name === 'AbortError') {
            return
          }
          this.error = true
          this.loaded = false
          console.error('OpenCV Viewer: stream error', e)
        }
        // Stream ended (or errored): pause briefly before reconnecting.
        if (this._stopped) return
        await new Promise(r => setTimeout(r, 1000))
      }
    },

    /**
     * Read the multipart/x-mixed-replace body, locating each JPEG by its
     * Content-Length header, and hand the bytes to _showFrame().
     *
     * Part layout emitted by the server:
     *   --frame\r\n
     *   Content-Type: image/jpeg\r\n
     *   Content-Length: <N>\r\n
     *   \r\n
     *   <N bytes JPEG>\r\n
     */
    async _consume(reader) {
      const decoder = new TextDecoder('latin1')
      let buf = new Uint8Array(0)

      const append = (chunk) => {
        const next = new Uint8Array(buf.length + chunk.length)
        next.set(buf, 0)
        next.set(chunk, buf.length)
        buf = next
      }

      const indexOf = (needle, from) => {
        // Byte search for the header/body separator within the leading ASCII region.
        outer: for (let i = from; i <= buf.length - needle.length; i++) {
          for (let j = 0; j < needle.length; j++) {
            if (buf[i + j] !== needle[j]) continue outer
          }
          return i
        }
        return -1
      }

      const SEP = [13, 10, 13, 10] // \r\n\r\n  (end of part headers)

      while (true) {
        if (this._stopped) {
          await reader.cancel().catch(() => {})
          return
        }

        // Find the end of the current part's headers.
        const headerEnd = indexOf(SEP, 0)
        if (headerEnd === -1) {
          const { done, value } = await reader.read()
          if (done) return
          append(value)
          continue
        }

        // Parse headers to get the JPEG byte length.
        const headerText = decoder.decode(buf.subarray(0, headerEnd))
        const match = /Content-Length:\s*(\d+)/i.exec(headerText)
        if (!match) {
          // Malformed/garbage before a boundary — drop up to the separator and resync.
          buf = buf.subarray(headerEnd + SEP.length)
          continue
        }
        const length = parseInt(match[1], 10)
        const bodyStart = headerEnd + SEP.length

        // Ensure the full JPEG body is buffered.
        while (buf.length < bodyStart + length) {
          if (this._stopped) {
            await reader.cancel().catch(() => {})
            return
          }
          const { done, value } = await reader.read()
          if (done) return
          append(value)
        }

        const frame = buf.subarray(bodyStart, bodyStart + length)
        this._showFrame(frame)

        // Advance past this frame (skip the trailing \r\n the server appends).
        let nextStart = bodyStart + length
        if (buf[nextStart] === 13 && buf[nextStart + 1] === 10) {
          nextStart += 2
        }
        buf = buf.slice(nextStart)
      }
    },

    /**
     * Render one JPEG frame into the <img> via an object URL, revoking the
     * previous URL to avoid leaking blobs.
     */
    _showFrame(bytes) {
      const img = this.$refs.img
      if (!img) return
      // Copy out of the streaming buffer — Blob keeps a reference otherwise.
      const blob = new Blob([bytes.slice()], { type: 'image/jpeg' })
      const url = URL.createObjectURL(blob)
      const previous = this._objectUrl
      img.src = url
      this._objectUrl = url
      this.error = false
      this.loaded = true
      if (previous) {
        // Revoke after the new frame is painted to avoid flicker.
        requestAnimationFrame(() => URL.revokeObjectURL(previous))
      }
    }
  },

  mounted() {
    this._stopped = false
    this._abort = null
    this._objectUrl = null
    this._startStream()
  },

  beforeUnmount() {
    this._stopped = true
    if (this._abort) {
      this._abort.abort()
      this._abort = null
    }
    if (this._objectUrl) {
      URL.revokeObjectURL(this._objectUrl)
      this._objectUrl = null
    }
  }
}
