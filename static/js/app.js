document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const plateNumber = document.getElementById("plateNumber")
  const authStatus = document.getElementById("authStatus")
  const statusBadge = document.getElementById("statusBadge")
  const confidenceIndicator = document.getElementById("confidenceIndicator")
  const vehicleDescription = document.getElementById("vehicleDescription")
  const totalDetections = document.getElementById("totalDetections")
  const authorizedCount = document.getElementById("authorizedCount")
  const unauthorizedCount = document.getElementById("unauthorizedCount")
  const historyList = document.getElementById("historyList")
  const authorizedList = document.getElementById("authorizedList")
  const plateCount = document.getElementById("plateCount")
  const clearHistoryBtn = document.getElementById("clearHistory")
  const menuToggle = document.getElementById("menuToggle")
  const sidebar = document.querySelector(".sidebar")
  const toastContainer = document.getElementById("toastContainer")
  const scanToggleBtn = document.getElementById("scanToggleBtn")
  const scanOverlay = document.getElementById("scanOverlay")
  const videoFeed = document.getElementById("videoFeed")
  const cameraStatus = document.getElementById("cameraStatus")
  const captureBtn = document.getElementById("captureBtn")
  const fullscreenBtn = document.getElementById("fullscreenBtn")

  // Modal elements
  const manualEntryModal = document.getElementById("manualEntryModal")
  const manualEntryBtn = document.getElementById("manualEntryBtn")
  const manualEntryLink = document.getElementById("manualEntryLink")
  const closeModal = document.getElementById("closeModal")
  const cancelModal = document.getElementById("cancelModal")
  const submitManualPlate = document.getElementById("submitManualPlate")
  const manualPlateInput = document.getElementById("manualPlateInput")

  // Stats
  const stats = {
    total: 0,
    authorized: 0,
    unauthorized: 0,
  }

  // Detection history
  let detectionHistory = []

  // Last processed plate to avoid duplicates
  let lastProcessedPlate = null

  // Scanning state
  let isScanning = false
  const scanningInterval = null

  // Load authorized plates
  fetchAuthorizedPlates()

  // Start polling for latest detection (but don't process until scanning is enabled)
  setInterval(fetchLatestDetection, 500)

  // Event Listeners
  clearHistoryBtn.addEventListener("click", clearHistory)
  menuToggle.addEventListener("click", toggleSidebar)
  scanToggleBtn.addEventListener("click", toggleScanning)
  captureBtn.addEventListener("click", captureScreenshot)
  fullscreenBtn.addEventListener("click", toggleFullscreen)

  // Modal event listeners
  manualEntryBtn.addEventListener("click", openModal)
  manualEntryLink.addEventListener("click", openModal)
  closeModal.addEventListener("click", closeModalFunc)
  cancelModal.addEventListener("click", closeModalFunc)
  submitManualPlate.addEventListener("click", submitManualEntry)

  // Close modal when clicking outside
  window.addEventListener("click", (e) => {
    if (e.target === manualEntryModal) {
      closeModalFunc()
    }
  })

  // Submit on Enter key
  manualPlateInput.addEventListener("keyup", (e) => {
    if (e.key === "Enter") {
      submitManualEntry()
    }
  })

  // Toggle scanning
  function toggleScanning() {
    isScanning = !isScanning

    // Send scanning state to server
    fetch("/toggle_scanning", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ enabled: isScanning }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          updateScanningUI(isScanning)
        } else {
          showToast("Error", "Failed to toggle scanning mode", "error")
        }
      })
      .catch((error) => {
        console.error("Error toggling scanning:", error)
        showToast("Error", "Failed to toggle scanning mode", "error")
      })
  }

  // Update UI based on scanning state
  function updateScanningUI(isScanning) {
    if (isScanning) {
      // Start scanning
      scanToggleBtn.innerHTML = '<i class="fas fa-stop"></i><span>Stop Scanning</span>'
      scanToggleBtn.classList.add("scanning")
      scanOverlay.classList.add("active")
      cameraStatus.textContent = "SCANNING"
      cameraStatus.style.color = "#00e676"

      // Show toast notification
      showToast("Scanning Started", "The system is now scanning for license plates", "success")
    } else {
      // Stop scanning
      scanToggleBtn.innerHTML = '<i class="fas fa-play"></i><span>Start Scanning</span>'
      scanToggleBtn.classList.remove("scanning")
      scanOverlay.classList.remove("active")
      cameraStatus.textContent = "PAUSED"
      cameraStatus.style.color = "#ffea00"

      // Show toast notification
      showToast("Scanning Paused", "The system has stopped scanning for license plates", "info")
    }
  }

  // Capture screenshot
  function captureScreenshot() {
    // Create a canvas element
    const canvas = document.createElement("canvas")
    const video = videoFeed

    // Set canvas dimensions to match video
    canvas.width = video.clientWidth
    canvas.height = video.clientHeight

    // Draw the current video frame on the canvas
    const ctx = canvas.getContext("2d")
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

    // Convert canvas to data URL
    const dataURL = canvas.toDataURL("image/png")

    // Create a temporary link and trigger download
    const link = document.createElement("a")
    link.href = dataURL
    link.download = `anpr_screenshot_${new Date().toISOString().replace(/:/g, "-")}.png`
    link.click()

    // Show toast notification
    showToast("Screenshot Captured", "The screenshot has been saved to your downloads", "success")
  }

  // Toggle fullscreen
  function toggleFullscreen() {
    const videoContainer = document.querySelector(".video-container")

    if (!document.fullscreenElement) {
      if (videoContainer.requestFullscreen) {
        videoContainer.requestFullscreen()
      } else if (videoContainer.webkitRequestFullscreen) {
        videoContainer.webkitRequestFullscreen()
      } else if (videoContainer.msRequestFullscreen) {
        videoContainer.msRequestFullscreen()
      }
      fullscreenBtn.innerHTML = '<i class="fas fa-compress"></i>'
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen()
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen()
      } else if (document.msExitFullscreen) {
        document.msExitFullscreen()
      }
      fullscreenBtn.innerHTML = '<i class="fas fa-expand"></i>'
    }
  }

  // Toggle sidebar
  function toggleSidebar() {
    sidebar.classList.toggle("active")
  }

  // Open modal
  function openModal() {
    manualEntryModal.classList.add("active")
    manualPlateInput.focus()
  }

  // Close modal
  function closeModalFunc() {
    manualEntryModal.classList.remove("active")
    manualPlateInput.value = ""
  }

  // Submit manual entry
  function submitManualEntry() {
    const plate = manualPlateInput.value.trim()

    if (!plate) {
      showToast("Error", "Please enter a license plate number", "error")
      return
    }

    fetch("/manual_authorize", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ plate }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          processNewDetection({
            plate: data.plate,
            authorized: data.authorized,
            timestamp: Date.now() / 1000,
            confidence: 1.0,
            description: data.description,
          })

          closeModalFunc()

          const status = data.authorized ? "authorized" : "unauthorized"
          showToast("Manual Entry", `License plate ${data.plate} is ${status}`, data.authorized ? "success" : "error")
        } else {
          showToast("Error", data.message, "error")
        }
      })
      .catch((error) => {
        console.error("Error submitting manual entry:", error)
        showToast("Error", "Failed to process manual entry", "error")
      })
  }

  // Clear history
  function clearHistory() {
    detectionHistory = []
    renderHistory()
    showToast("History Cleared", "All detection history has been cleared", "info")
  }

  // Fetch authorized plates
  function fetchAuthorizedPlates() {
    fetch("/authorized_plates")
      .then((response) => response.json())
      .then((plates) => {
        renderAuthorizedPlates(plates)
        plateCount.textContent = plates.length
      })
      .catch((error) => {
        console.error("Error fetching authorized plates:", error)
        showToast("Connection Error", "Failed to load authorized plates", "error")
      })
  }

  // Render authorized plates
  function renderAuthorizedPlates(plates) {
    authorizedList.innerHTML = ""

    if (plates.length === 0) {
      const emptyState = document.createElement("div")
      emptyState.className = "empty-state"
      emptyState.innerHTML = '<i class="fas fa-database"></i><p>No plates in database</p>'
      authorizedList.appendChild(emptyState)
      return
    }

    plates.forEach((plateData) => {
      const plateElement = document.createElement("div")
      plateElement.className = "authorized-plate"
      plateElement.textContent = plateData.plate
      plateElement.title = plateData.description || ""
      authorizedList.appendChild(plateElement)
    })
  }

  // Fetch latest detection
  function fetchLatestDetection() {
    fetch("/latest_detection")
      .then((response) => response.json())
      .then((detection) => {
        // Only process new detections if scanning is enabled or it's a manual entry
        if (detection.plate && detection.plate !== lastProcessedPlate && (isScanning || detection.confidence === 1.0)) {
          processNewDetection(detection)
          lastProcessedPlate = detection.plate
        }
      })
      .catch((error) => {
        console.error("Error fetching latest detection:", error)
        // Don't show toast for every error to avoid spamming
      })
  }

  // Process new detection
  function processNewDetection(detection) {
    // Update plate display
    plateNumber.textContent = detection.plate || "No plate detected"

    // Update vehicle description
    if (detection.description) {
      vehicleDescription.textContent = detection.description
      vehicleDescription.style.display = "block"
    } else {
      vehicleDescription.style.display = "none"
    }

    // Update confidence indicator
    if (detection.confidence) {
      const confidenceWidth = Math.min(detection.confidence * 100, 100)
      confidenceIndicator.style.setProperty("--confidence-width", `${confidenceWidth}%`)
      confidenceIndicator.style.display = "block"
      confidenceIndicator.style.setProperty("--confidence-color", getConfidenceColor(detection.confidence))

      // Apply the custom property in the ::after pseudo-element
      document.documentElement.style.setProperty("--confidence-width", `${confidenceWidth}%`)
      document.documentElement.style.setProperty("--confidence-color", getConfidenceColor(detection.confidence))
    } else {
      confidenceIndicator.style.display = "none"
    }

    // Update status badge
    statusBadge.textContent = detection.authorized ? "AUTHORIZED" : "UNAUTHORIZED"
    statusBadge.className = "status-badge " + (detection.authorized ? "authorized" : "unauthorized")

    // Add highlight effect
    const overlay = document.getElementById("detectionOverlay")
    overlay.classList.remove("highlight")
    // Trigger reflow
    void overlay.offsetWidth
    overlay.classList.add("highlight")

    // Update stats
    stats.total++
    if (detection.authorized) {
      stats.authorized++
    } else {
      stats.unauthorized++
    }

    updateStats()

    // Add to history
    addToHistory(detection)

    // Show toast notification
    const title = detection.authorized ? "Authorized Vehicle" : "Unauthorized Vehicle"
    const message = `License plate ${detection.plate} detected`
    const type = detection.authorized ? "success" : "error"
    showToast(title, message, type)
  }

  // Get color based on confidence level
  function getConfidenceColor(confidence) {
    if (confidence >= 0.8) return "var(--success-color)"
    if (confidence >= 0.6) return "var(--warning-color)"
    return "var(--danger-color)"
  }

  // Update stats display
  function updateStats() {
    totalDetections.textContent = stats.total
    authorizedCount.textContent = stats.authorized
    unauthorizedCount.textContent = stats.unauthorized
  }

  // Add detection to history
  function addToHistory(detection) {
    // Add to beginning of array
    detectionHistory.unshift({
      plate: detection.plate,
      authorized: detection.authorized,
      timestamp: detection.timestamp || Date.now(),
      confidence: detection.confidence || 0,
      description: detection.description || "",
    })

    // Limit history to 10 items
    if (detectionHistory.length > 10) {
      detectionHistory.pop()
    }

    renderHistory()
  }

  // Render detection history
  function renderHistory() {
    historyList.innerHTML = ""

    if (detectionHistory.length === 0) {
      const emptyState = document.createElement("div")
      emptyState.className = "empty-state"
      emptyState.innerHTML = '<i class="fas fa-car-side"></i><p>No detections yet</p>'
      historyList.appendChild(emptyState)
      return
    }

    detectionHistory.forEach((item) => {
      const historyItem = document.createElement("div")
      historyItem.className = "history-item"
      historyItem.title = item.description || ""

      const plateInfo = document.createElement("div")
      plateInfo.className = "history-plate-info"

      const plate = document.createElement("div")
      plate.className = "history-plate"
      plate.textContent = item.plate

      const time = document.createElement("div")
      time.className = "history-time"
      time.textContent = formatTime(item.timestamp)

      plateInfo.appendChild(plate)
      plateInfo.appendChild(time)

      const status = document.createElement("div")
      status.className = "history-status " + (item.authorized ? "authorized" : "unauthorized")
      status.textContent = item.authorized ? "Authorized" : "Unauthorized"

      historyItem.appendChild(plateInfo)
      historyItem.appendChild(status)

      historyList.appendChild(historyItem)
    })
  }

  // Show toast notification
  function showToast(title, message, type = "info") {
    const toast = document.createElement("div")
    toast.className = `toast ${type}`

    let iconClass = "fas fa-info-circle"
    if (type === "success") iconClass = "fas fa-check-circle"
    if (type === "error") iconClass = "fas fa-exclamation-circle"

    toast.innerHTML = `
            <div class="toast-icon">
                <i class="${iconClass}"></i>
            </div>
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close">
                <i class="fas fa-times"></i>
            </button>
        `

    // Add close button functionality
    toast.querySelector(".toast-close").addEventListener("click", () => {
      toast.remove()
    })

    toastContainer.appendChild(toast)

    // Auto remove after 5 seconds
    setTimeout(() => {
      if (toast.parentNode) {
        toast.remove()
      }
    }, 5000)
  }

  // Format timestamp
  function formatTime(timestamp) {
    const date = new Date(timestamp * 1000)
    const hours = date.getHours().toString().padStart(2, "0")
    const minutes = date.getMinutes().toString().padStart(2, "0")
    const seconds = date.getSeconds().toString().padStart(2, "0")
    return `${hours}:${minutes}:${seconds}`
  }

  // Add CSS for confidence indicator (since we can't modify the CSS file directly)
  const style = document.createElement("style")
  style.textContent = `
        .confidence-indicator::after {
            width: var(--confidence-width, 0%);
            background-color: var(--confidence-color, var(--success-color));
        }
    `
  document.head.appendChild(style)
})

