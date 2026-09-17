/**
 * Printing Press Barcode System Backend UI Pipeline
 * Enhanced with Hardware Scanner Throttling & Client-side Validation.
 */

document.addEventListener('DOMContentLoaded', () => {
    const symbologySelect = document.getElementById('symbology');
    const barcodeInput = document.getElementById('barcodeData');
    const validationFeedback = document.getElementById('validationFeedback');
    const scanForm = document.getElementById('scanForm');
    
    // Safety throttle state to block hardware laser double-triggers
    let isSubmitting = false;

    // Handle interactive validation switching 
    symbologySelect.addEventListener('change', function() {
        if (this.value === 'EAN13') {
            barcodeInput.placeholder = "e.g. 4006381333931 (13 numbers)";
        } else {
            barcodeInput.placeholder = "Job code or alphanumeric strings";
        }
        validateInput();
    });

    // Real-time structural evaluation
    function validateInput() {
        const data = barcodeInput.value.trim();
        const type = symbologySelect.value;
        
        if (!data) {
            barcodeInput.classList.remove('is-invalid');
            return false;
        }
        
        if (type === 'EAN13') {
            const is13Digits = /^\d{13}\$/.test(data);
            if (!is13Digits) {
                barcodeInput.classList.add('is-invalid');
                validationFeedback.textContent = `EAN-13 require 13 digits. Current: ${data.length}`;
                return false;
            }
        }
        
        barcodeInput.classList.remove('is-invalid');
        return true;
    }

    barcodeInput.addEventListener('input', validateInput);

    // Capture the hardware scan submit action
    scanForm.addEventListener('submit', function(e) {
        e.preventDefault();

        // 1. Block submissions if a request is already actively in-flight
        if (isSubmitting) {
            return; 
        }

        // 2. Validate input structural conditions before sending packet
        if (!validateInput()) {
            showAlert('Submission blocked: Barcode string does not match selected format rules.', 'danger');
            return;
        }

        // Engage lock to shield against physical hardware key bounce-back
        isSubmitting = true;
        const submitBtn = scanForm.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = "Processing Scan...";

        const payload = {
            session_id: document.getElementById('sessionId').value.trim(),
            operator_id: document.getElementById('operatorId').value.trim(),
            symbology: symbologySelect.value,
            barcode_data: barcodeInput.value.trim(),
            generate_svg: document.getElementById('generateSvg').checked
        };

        fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
                barcodeInput.value = ''; // Flush input deck for the next hardware trigger
                updateLogTable(data.logs);
            } else {
                showAlert(data.error || 'Submission failed.', 'danger');
            }
        })
        .catch(() => showAlert('Network connection failure. Check server status.', 'danger'))
        .finally(() => {
            // Lift locks to allow the next barcode execution pass
            isSubmitting = false;
            submitBtn.disabled = false;
            submitBtn.textContent = "Submit Floor Scan";
            barcodeInput.focus(); // Keep selection pointer locked to text input for rapid scanning
        });
    });

    // Renders custom dismissible Bootstrap warning nodes
    function showAlert(msg, type) {
        const container = document.getElementById('alertContainer');
        container.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${msg}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>`;
            
        // Auto-close success messages after 3 seconds to keep UI clean
        if (type === 'success') {
            setTimeout(() => {
                const activeAlert = container.querySelector('.alert');
                if (activeAlert) {
                    const bsAlert = new bootstrap.Alert(activeAlert);
                    bsAlert.close();
                }
            }, 3000);
        }
    }

    // Completely rebuilds data presentation tracking layers cleanly
    function updateLogTable(logs) {
        document.getElementById('recordCount').textContent = `${logs.length} Total Records`;
        const tbody = document.getElementById('logTableBody');
        tbody.innerHTML = ''; 

        logs.forEach(log => {
            const isEan = log.Barcode_Data.length === 13 && /^\d+\$/.test(log.Barcode_Data);
            const fileLink = isEan ? 'barcode_ean13.svg' : 'barcode_code128.svg';
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="text-muted">${log.Timestamp}</td>
                <td><span class="badge bg-outline text-secondary border border-secondary">${log.Session_ID}</span></td>
                <td><strong>${log.Operator_ID}</strong></td>
                <td class="font-monospace text-primary fw-bold">${log.Barcode_Data}</td>
                <td>
                    <a href="/barcodes/${fileLink}" class="btn btn-xs btn-outline-dark py-0 px-2" style="font-size: 0.75rem;">📥 Download SVG</a>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }
});