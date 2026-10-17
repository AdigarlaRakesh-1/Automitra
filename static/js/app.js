// =====================================================================
// AutoMitra - Interactive Client Logic & Workflows
// =====================================================================

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initDuplicateCustomerCheck();
  initDynamicVehicleLoader();
  initSparePartPicker();
  initModals();
});

// ---------------------------------------------------------------------
// 1. Theme Toggle (Dark / Light Mode)
// ---------------------------------------------------------------------
function initThemeToggle() {
  const toggleBtn = document.getElementById('theme-toggle-btn');
  if (!toggleBtn) return;

  const currentTheme = localStorage.getItem('gb-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', currentTheme);

  toggleBtn.addEventListener('click', () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const nextTheme = isDark ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', nextTheme);
    localStorage.setItem('gb-theme', nextTheme);
  });
}

// ---------------------------------------------------------------------
// 2. Live Duplicate Customer Detection (Solves duplicate customer records)
// ---------------------------------------------------------------------
function initDuplicateCustomerCheck() {
  const phoneInput = document.getElementById('customer-phone-input');
  const emailInput = document.getElementById('customer-email-input');
  const alertBox = document.getElementById('duplicate-customer-alert');
  const customerIdInput = document.getElementById('customer-id-input');

  if (!phoneInput || !alertBox) return;

  let debounceTimer = null;

  function checkDuplicate() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
      const phone = phoneInput.value.trim();
      const email = emailInput ? emailInput.value.trim() : '';
      const excludeId = customerIdInput ? customerIdInput.value : '';

      if (phone.length < 5 && email.length < 5) {
        alertBox.classList.remove('active');
        return;
      }

      try {
        const url = `/api/check_duplicate_customer?phone=${encodeURIComponent(phone)}&email=${encodeURIComponent(email)}&exclude_id=${excludeId}`;
        const res = await fetch(url);
        const data = await res.json();

        if (data.duplicate) {
          alertBox.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            <div>
              <strong>Duplicate Customer Found!</strong> A record already exists for 
              <strong>${data.name}</strong> (Phone: ${data.phone}${data.email ? ', Email: ' + data.email : ''}).
              <a href="/customers/${data.id}" target="_blank" style="text-decoration:underline; font-weight:700; margin-left:6px; color:#FCA5A5;">
                View Customer Profile &rarr;
              </a>
            </div>
          `;
          alertBox.classList.add('active');
        } else {
          alertBox.classList.remove('active');
        }
      } catch (err) {
        console.error('Error verifying customer duplicate:', err);
      }
    }, 350);
  }

  phoneInput.addEventListener('input', checkDuplicate);
  if (emailInput) {
    emailInput.addEventListener('input', checkDuplicate);
  }
}

// ---------------------------------------------------------------------
// 3. Dynamic Vehicle Loader on Customer Selection (Service Bookings)
// ---------------------------------------------------------------------
function initDynamicVehicleLoader() {
  const customerSelect = document.getElementById('booking-customer-select');
  const vehicleSelect = document.getElementById('booking-vehicle-select');

  if (!customerSelect || !vehicleSelect) return;

  async function loadVehicles(customerId) {
    if (!customerId) {
      vehicleSelect.innerHTML = '<option value="">-- First Select a Customer --</option>';
      return;
    }

    try {
      vehicleSelect.innerHTML = '<option value="">Loading vehicles...</option>';
      const res = await fetch(`/api/customer_vehicles/${customerId}`);
      const vehicles = await res.json();

      if (vehicles.length === 0) {
        vehicleSelect.innerHTML = '<option value="">No vehicles found for this customer. Please register one first.</option>';
        return;
      }

      vehicleSelect.innerHTML = '<option value="">-- Select Customer Vehicle --</option>' +
        vehicles.map(v => `<option value="${v.id}">${v.display}</option>`).join('');

      const preselected = vehicleSelect.getAttribute('data-preselected');
      if (preselected) {
        vehicleSelect.value = preselected;
      }
    } catch (err) {
      console.error('Error loading customer vehicles:', err);
      vehicleSelect.innerHTML = '<option value="">Error loading vehicles</option>';
    }
  }

  customerSelect.addEventListener('change', (e) => loadVehicles(e.target.value));

  // Trigger on initial page load if customer is preselected
  if (customerSelect.value) {
    loadVehicles(customerSelect.value);
  }
}

// ---------------------------------------------------------------------
// 4. Dynamic Spare Part Picker in Job Detail
// ---------------------------------------------------------------------
function initSparePartPicker() {
  const partSelect = document.getElementById('job-part-select');
  const partInfoBox = document.getElementById('job-part-info');
  const quantityInput = document.getElementById('job-part-quantity');

  if (!partSelect || !partInfoBox) return;

  partSelect.addEventListener('change', async (e) => {
    const partId = e.target.value;
    if (!partId) {
      partInfoBox.style.display = 'none';
      return;
    }

    try {
      const res = await fetch(`/api/part_info/${partId}`);
      const part = await res.json();

      const unitPriceEl = document.getElementById('selected-part-price');
      const stockEl = document.getElementById('selected-part-stock');

      if (unitPriceEl) unitPriceEl.textContent = `₹${part.selling_price.toFixed(2)}`;
      if (stockEl) stockEl.textContent = `${part.stock_quantity} available`;
      
      if (quantityInput) {
        quantityInput.max = part.stock_quantity;
      }

      partInfoBox.style.display = 'block';
    } catch (err) {
      console.error('Error fetching part detail:', err);
    }
  });
}

// ---------------------------------------------------------------------
// 5. Modal Controllers
// ---------------------------------------------------------------------
function initModals() {
  // Open modal buttons
  document.querySelectorAll('[data-open-modal]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const modalId = btn.getAttribute('data-open-modal');
      const modal = document.getElementById(modalId);
      if (modal) modal.classList.add('active');
    });
  });

  // Close modal buttons
  document.querySelectorAll('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const modal = btn.closest('.modal-overlay');
      if (modal) modal.classList.remove('active');
    });
  });

  // Close on backdrop click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('active');
    });
  });
}
