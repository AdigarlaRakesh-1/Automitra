# Contributing to AutoMitra

Thank you for your interest in contributing to **AutoMitra**! AutoMitra is an open-source Garage Management System designed to streamline garage operations with a modern web interface and centralized relational database.

We welcome all kinds of contributions: bug fixes, feature enhancements, documentation updates, UI polish, and localized customizations.

---

## 📋 Code of Conduct
Please be respectful, constructive, and helpful when interacting with fellow contributors and opening discussions or pull requests.

---

## 🛠️ Getting Started

### 1. Fork the Repository
Click the **Fork** button at the top-right of the GitHub repository page to create your own copy of the project.

### 2. Clone Your Fork
Clone your forked repository locally:
```bash
git clone https://github.com/<your-username>/AutoMitra.git
cd AutoMitra
```

### 3. Create a Virtual Environment (Optional but Recommended)
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Run the Application
AutoMitra automatically initializes and seeds an embedded SQLite database (`automitra.db`) if MySQL is not configured:
```bash
python app.py
```
Open `http://127.0.0.1:5000` in your browser.

---

## 🧪 Running Tests
Before submitting changes, ensure the automated test suite passes:
```bash
python -m pytest test_app.py -v
```

All 7 test suites should pass:
- Database table seeding
- Duplicate customer live detection
- Missed bookings detection and rescheduling
- Inventory stock deduction & reorder alerts
- Low stock calculation
- Billing, invoice generation & payment transactions
- All web dashboard routes

---

## 🌿 Contribution Workflow

1. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bugfix-name
   ```

2. **Make Your Changes**:
   - Write clean, documented code.
   - Follow PEP 8 style standards for Python.
   - Keep styling in `static/css/` consistent with existing design tokens.

3. **Commit Your Changes**:
   ```bash
   git add .
   git commit -m "feat: describe your feature or fix in present tense"
   ```

4. **Push to Your Fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Open a Pull Request (PR)**:
   - Go to the original repository on GitHub.
   - Click **Compare & pull request**.
   - Provide a concise description of what changes were made and why.
   - Mention any related issues.

---

## 📄 License
By contributing to AutoMitra, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
