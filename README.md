# Order Webpage Project

This repository contains a Python-based web application along with an automated testing and coverage setup using **pytest**.

---

## 📁 Project Structure

```
order_webpage_final/
│
├── Config/
│   ├── run_tests.py          # Script to run tests
│   └── verify_isolation.py   # Environment / test isolation checks
│
├── Images/                   # Image assets
├── static/                   # Static files (CSS, JS, etc.)
├── Template/                 # HTML templates
├── tests/                    # Pytest test cases
│
├── uploads/                  # Uploaded files (if any)
│
├── alter.py                  # Business logic / helpers
├── db.py                     # Database logic
├── main.py                   # Application entry point
│
├── pytest.ini                # Pytest configuration
├── requirements.txt          # Python dependencies
├── runtime.txt               # Runtime version (for deployment)
├── render.yaml               # Render deployment configuration
├── test.db                   # Test database
├── test_suite.db             # Test suite database
└── htmlcov/                  # Coverage report output
```

---

## 🧪 Testing Setup

This project uses **pytest** along with plugins for:

* Test execution: `pytest`
* Coverage reports: `pytest-cov`
* HTML test reports: `pytest-html`

### Install dependencies

Activate your virtual environment, then run:

```bash
pip install -r requirements.txt
```

If needed, install testing tools manually:

```bash
pip install pytest pytest-cov pytest-html
```

---

## ▶️ Running Tests

From the project root directory:

```bash
python -m pytest tests/ \
  --cov=main \
  --cov-report=html \
  --html=test_report.html \
  --self-contained-html
```

---

## 📊 Test Reports

After running tests, the following reports will be generated:

* **Coverage Report** → `htmlcov/index.html`
* **Test Report** → `test_report.html`

Open these files in a browser to view detailed results.

---

## ⚙️ Pytest Configuration

`pytest.ini` controls default pytest behavior such as:

* Test discovery paths
* Warning suppression
* Plugins configuration

You can run pytest without extra flags if defaults are set correctly.

---

## 🚀 Deployment

The project includes `render.yaml` and `runtime.txt` for deployment on **Render**.

Ensure `requirements.txt` includes all dependencies required for production and testing.

---

## ✅ Notes

* Always run tests inside the virtual environment
* Use `python -m pytest` if `pytest` command is not recognized
* Keep test databases separate from production databases

---

