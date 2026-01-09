# 📈 StockLLM (AI Agent + Dashboard)

A secure, private stock analysis platform that runs 100% locally. It combines a professional financial dashboard with an **AI Copilot** (powered by local LLMs via Ollama) to fetch, visualize, and analyze stock data from Indian exchanges (NSE/BSE).

## ✨ Features

* **Dual-Interface Design:**
* **Main Dashboard:** Professional-grade database viewer with interactive Candlestick charts (Plotly), raw data tables, and date-range filtering.
* **AI Copilot (Sidebar):** A persistent chat interface to talk to your data.


* **Local LLM Integration:** Supports **Mistral 7B** and **Qwen 2.5 (14B)** via Ollama. No data leaves your machine.
* **Universal Data Syncer:** Automatically fetches missing data from Yahoo Finance (`yfinance`) when the AI agent requests it.
* **Context-Aware AI:** The agent knows which stock you are viewing on the dashboard and answers questions contextually (e.g., "Why did *it* fall today?").
* **Robust Data Storage:** Uses a local SQLite database (`stocks.db`) to persist all fetched data for offline access.

---

## 🛠️ Prerequisites

1. **Python 3.10+**
2. **Ollama**: Download from [ollama.com](https://ollama.com) to run local LLMs.

---

## 🚀 Setup Guide

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/local-stock-analyst.git
cd local-stock-analyst

```

### 2. Install Dependencies

Create a virtual environment (recommended) and install the required Python packages:

```bash
# Create virtual env
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Mac/Linux)
source venv/bin/activate

# Install libraries
pip install streamlit pandas yfinance plotly langchain-ollama langgraph langchain-core

```

### 3. Initialize Ollama Models

You need to pull the models used by the agent. Open a terminal and run:

```bash
# Pull the standard model (Fast)
ollama pull mistral

# Pull the advanced model (Smart)
ollama pull qwen2.5:14b

```

*Note: Ensure the Ollama app is running in the background.*

---

## 🏃 How to Run

1. **Start the Application:**
Run the Streamlit app from your terminal:
```bash
streamlit run agent.py

```


2. **Access the Dashboard:**
Your browser will automatically open `http://localhost:8501`.
3. **Using the App:**
* **First Run:** The database will be empty. Go to the **AI Copilot** (sidebar) and type:
> *"Fetch data for Reliance and Tata Motors for 2025"*


* **Visualize:** Once fetched, refresh the page (or let the auto-refresh handle it). Select the company from the dropdown to see interactive charts.
* **Context Chat:** Select a stock (e.g., TCS) and ask the AI:
> *"What was the highest price for this stock?"*





---

## 📂 Project Structure

* **`agent.py`**: The main frontend application. Handles the Streamlit UI, AI chat logic, and StateGraph workflow.
* **`retriever.py`**: The backend logic for fetching data from Yahoo Finance (`yfinance`). Includes a "Universal Syncer" to download and clean data.
* **`market_db.py`**: The database layer. Manages SQLite connections, schema creation (tables: `metadata`, `prices`), and CRUD operations.
* **`data/`**: Directory where the SQLite database (`stocks.db`) is stored locally.
* **`logs/`**: Stores execution logs for debugging agent decisions and tool calls.

---

## ⚠️ Troubleshooting

**Issue: "Connection Refused"**

* Ensure Ollama is running (`ollama serve` or open the app).

**Issue: Model Hallucinating JSON**

* The system includes a "Parser Shim" to catch text-based JSON outputs from smaller models like Mistral and convert them into valid tool calls. If issues persist, switch to **Qwen 2.5 (14B)** in the sidebar.

**Issue: Missing Data**

* If the chart is empty, ask the AI to "fetch data" for that specific date range. The database only stores what you have requested.
