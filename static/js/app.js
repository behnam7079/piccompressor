document.addEventListener("DOMContentLoaded", function () {
    const fileInput = document.getElementById("file-input");
    const dropZone = document.getElementById("drop-zone");
    const qualitySlider = document.getElementById("quality-slider");
    const qualityVal = document.getElementById("quality-val");
    const formatSelect = document.getElementById("format-select");
    const maxWidthInput = document.getElementById("max-width");
    const stripExifCheck = document.getElementById("strip-exif");
    const loadingOverlay = document.getElementById("loading-overlay");
    const loadingText = document.getElementById("loading-text");
    const resultsContainer = document.getElementById("results-container");
    const batchActionBar = document.getElementById("batch-action-bar");
    const batchCount = document.getElementById("batch-count");
    const batchSavedTotal = document.getElementById("batch-saved-total");
    const downloadAllBtn = document.getElementById("download-all-btn");
    const clearAllBtn = document.getElementById("clear-all-btn");
    const themeToggle = document.getElementById("theme-toggle");
    const previewModal = document.getElementById("preview-modal");
    const modalCloseBtn = document.getElementById("modal-close-btn");

    let processedFiles = [];

    // Theme handling
    const savedTheme = localStorage.getItem("piccompressor-theme");
    if (savedTheme === "dark") document.body.classList.add("theme-dark");
    if (themeToggle) {
        themeToggle.addEventListener("click", function () {
            document.body.classList.toggle("theme-dark");
            localStorage.setItem("piccompressor-theme", document.body.classList.contains("theme-dark") ? "dark" : "light");
        });
    }

    // Quality slider update
    if (qualitySlider && qualityVal) {
        qualitySlider.addEventListener("input", function () {
            qualityVal.textContent = this.value + "%";
        });
    }

    // Drag and drop handling
    if (dropZone) {
        ["dragenter", "dragover", "dragleave", "drop"].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
            document.body.addEventListener(eventName, preventDefaults, false);
        });

        ["dragenter", "dragover"].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.add("drag-over"), false);
        });

        ["dragleave", "drop"].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.remove("drag-over"), false);
        });

        dropZone.addEventListener("drop", e => {
            if (e.dataTransfer && e.dataTransfer.files) {
                handleFiles(e.dataTransfer.files);
            }
        });
    }

    function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }

    if (fileInput) {
        fileInput.addEventListener("change", e => {
            if (e.target.files) handleFiles(e.target.files);
        });
    }

    function cleanupBlobs() {
        processedFiles.forEach(item => {
            if (item.originalUrl && item.originalUrl.startsWith("blob:")) {
                URL.revokeObjectURL(item.originalUrl);
            }
        });
    }

    async function handleFiles(fileList) {
        // اضافه شدن .heic برای پشتیبانی از دوربین گوشی‌های آیفون
        const allowedExts = [".jpg", ".jpeg", ".png", ".webp", ".heic"];
        const files = Array.from(fileList).filter(file => {
            const ext = "." + file.name.split(".").pop().toLowerCase();
            return file.type.startsWith("image/") || allowedExts.includes(ext);
        });

        if (files.length === 0) {
            alert("لطفاً فایل تصویری معتبر (JPG, PNG, WebP, HEIC) انتخاب کنید.");
            return;
        }

        // پاکسازی کش حافظه قبلی مرورگر
        cleanupBlobs();
        processedFiles = [];
        resultsContainer.innerHTML = "";
        if (batchActionBar) batchActionBar.style.display = "none";
        if (loadingOverlay) loadingOverlay.classList.add("active");
        if (loadingText) loadingText.textContent = `در حال پردازش ${files.length} تصویر...`;

        const formData = new FormData();
        files.forEach(file => formData.append("files", file));
        if (qualitySlider) formData.append("quality", qualitySlider.value);
        if (formatSelect) formData.append("format", formatSelect.value);
        if (stripExifCheck) formData.append("strip_exif", stripExifCheck.checked ? "true" : "false");
        if (maxWidthInput && maxWidthInput.value && parseInt(maxWidthInput.value, 10) > 0) {
            formData.append("max_width", maxWidthInput.value);
        }

        try {
            const response = await fetch("/api/compress-batch", { method: "POST", body: formData });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.detail || data.error || "خطا در پردازش تصاویر");
            }
            displayResults(files, data.items || []);
        } catch (error) {
            alert("خطا: " + error.message);
        } finally {
            if (loadingOverlay) loadingOverlay.classList.remove("active");
            if (fileInput) fileInput.value = "";
        }
    }

    function formatBytes(bytes) {
        if (!bytes || bytes <= 0) return "۰ بایت";
        const units = ["بایت", "کیلوبایت", "مگابایت", "گیگابایت"];
        const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
        const val = (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 2);
        return val + " " + units[i];
    }

    function displayResults(originalFiles, items) {
        let totalSaved = 0;
        let validCount = 0;

        items.forEach((item, index) => {
            if (item.error) {
                const errorDiv = document.createElement("div");
                errorDiv.className = "result-item";
                errorDiv.innerHTML = `
                    <div class="result-details">
                        <div class="result-name">${escapeHTML(item.original_filename || "فایل")}</div>
                        <div class="result-specs" style="color:var(--danger-color, #dc2626)">خطا: ${escapeHTML(item.error)}</div>
                    </div>
                `;
                resultsContainer.appendChild(errorDiv);
                return;
            }

            const originalFile = originalFiles[index] || originalFiles.find(f => f.name === item.original_filename);
            const originalUrl = originalFile ? URL.createObjectURL(originalFile) : item.preview_url;
            const meta = item.meta || { original_size: 0, compressed_size: 0, saving_percentage: 0, new_dimensions: [0, 0] };
            
            totalSaved += (meta.saved_bytes || (meta.original_size - meta.compressed_size) || 0);
            validCount++;

            const result = {
                name: item.compressed_filename || "compressed-image.jpg",
                data: item.preview_url,
                originalUrl: originalUrl,
                originalName: item.original_filename || "original-image",
                meta: meta,
                previewUrl: item.preview_url
            };
            processedFiles.push(result);

            const resultItem = document.createElement("div");
            resultItem.className = "result-item";
            resultItem.innerHTML = `
                <img src="${item.preview_url}" alt="پیش‌نمایش ${escapeHTML(result.name)}" class="result-thumb">
                <div class="result-details">
                    <div class="result-name" title="${escapeHTML(result.name)}">${escapeHTML(result.name)}</div>
                    <div class="result-specs">
                        <span>${formatBytes(meta.original_size)} <span style="text-decoration:line-through;opacity:0.7">قبل</span></span>
                        <span>⬅</span>
                        <span class="font-bold text-teal">${formatBytes(meta.compressed_size)} <span>بعد</span></span>
                        <span class="badge-saving">${meta.saving_percentage}% کاهش</span>
                        <span>${meta.new_dimensions ? meta.new_dimensions[0] + ' × ' + meta.new_dimensions[1] + ' px' : ''}</span>
                    </div>
                    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${Math.min(Math.max(meta.saving_percentage, 0), 100)}%"></div></div>
                </div>
                <div class="result-actions">
                    <button class="btn-preview" type="button">مقایسه</button>
                    <button class="btn-download" type="button">دانلود</button>
                </div>
            `;

            resultItem.querySelector(".btn-preview").addEventListener("click", () => showPreview(result));
            resultItem.querySelector(".btn-download").addEventListener("click", () => downloadData(result.data, result.name));
            resultsContainer.appendChild(resultItem);
        });

        if (validCount > 0 && batchActionBar) {
            batchActionBar.style.display = "flex";
            if (batchCount) batchCount.textContent = `${validCount} تصویر پردازش شد`;
            if (batchSavedTotal) batchSavedTotal.textContent = `صرفه‌جویی کل: ${formatBytes(totalSaved)}`;
        }
    }

    function showPreview(result) {
        const modalOrigImg = document.getElementById("modal-orig-img");
        const modalCompImg = document.getElementById("modal-comp-img");
        if (modalOrigImg) modalOrigImg.src = result.originalUrl;
        if (modalCompImg) modalCompImg.src = result.previewUrl;
        
        const modalTitle = document.getElementById("modal-title");
        if (modalTitle) modalTitle.textContent = result.originalName;

        const origSpecs = document.getElementById("modal-orig-specs");
        if (origSpecs) origSpecs.textContent = `حجم: ${formatBytes(result.meta.original_size)} • تصویر اصلی`;

        const compSpecs = document.getElementById("modal-comp-specs");
        if (compSpecs && result.meta.new_dimensions) {
            compSpecs.textContent = `حجم: ${formatBytes(result.meta.compressed_size)} • ${result.meta.new_dimensions[0]} × ${result.meta.new_dimensions[1]} px`;
        }

        if (previewModal) previewModal.classList.add("active");
    }

    function downloadData(dataUrl, filename) {
        const link = document.createElement("a");
        link.href = dataUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
    }

    function escapeHTML(value) {
        return String(value || "").replace(/[&<>"']/g, char => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
        }[char]));
    }

    if (downloadAllBtn) {
        downloadAllBtn.addEventListener("click", function () {
            if (processedFiles.length === 0) return;
            const originalBtnText = downloadAllBtn.textContent;
            downloadAllBtn.textContent = "در حال آماده‌سازی زیپ...";
            downloadAllBtn.disabled = true;

            const zipData = processedFiles.map(item => ({ name: item.name, data: item.data }));
            fetch("/api/download-zip", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ files: zipData })
            })
            .then(response => {
                if (!response.ok) throw new Error("ساخت فایل ZIP ناموفق بود");
                return response.blob();
            })
            .then(blob => {
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = "compressed_images.zip";
                link.click();
                URL.revokeObjectURL(url);
            })
            .catch(error => alert("خطا: " + error.message))
            .finally(() => {
                downloadAllBtn.textContent = originalBtnText;
                downloadAllBtn.disabled = false;
            });
        });
    }

    if (clearAllBtn) {
        clearAllBtn.addEventListener("click", function () {
            cleanupBlobs();
            processedFiles = [];
            resultsContainer.innerHTML = "";
            if (batchActionBar) batchActionBar.style.display = "none";
        });
    }

    if (modalCloseBtn && previewModal) {
        modalCloseBtn.addEventListener("click", () => previewModal.classList.remove("active"));
    }
    if (previewModal) {
        previewModal.addEventListener("click", event => {
            if (event.target === previewModal) previewModal.classList.remove("active");
        });
    }
    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && previewModal) previewModal.classList.remove("active");
    });
});
