# 📈 Fortune 100 Stock LLM (Google Colab + Alpha Vantage + Falcon-7B)

This project builds a **context-aware LLM financial assistant** that can answer natural language questions about **Fortune 100 companies’ stock performance**.

It uses:

* [Alpha Vantage API](https://www.alphavantage.co/) for stock data
* [Falcon 7B Instruct](https://huggingface.co/tiiuae/falcon-7b-instruct) (quantized for Colab T4 GPU)
* A Fortune 100 companies list (`fortune100.csv`) with stock tickers
* Google Colab’s **secrets system** to keep API keys safe

---

## 🚀 Features

* Fetches **daily stock prices** for Fortune 100 companies
* Summarizes **latest close, 5-day average, and trend** (up/down)
* Interactive **LLM query loop**: ask questions like

  * “Compare Apple and Amazon stock performance over the last 5 days.”
  * “What is the trend for Microsoft and Google?”
* Efficient for **Colab T4 GPU** (4-bit quantization of Falcon-7B)
* Keeps **API keys secure** (no hardcoding)

---

## 📂 Project Structure

```
📁 fortune100-stock-llm
 ┣ 📜 stock_llm.ipynb      # Main Colab notebook
 ┣ 📜 fortune100.csv       # Fortune 100 company → stock ticker mapping
 ┗ 📜 README.md            # Documentation
```

---

## 🔑 Setup (Colab)

1. Open the notebook in [Google Colab](https://colab.research.google.com/).
2. Install dependencies:

   ```bash
   !pip install openai pandas matplotlib alpha_vantage transformers accelerate bitsandbytes
   ```
3. Set your **Alpha Vantage API key** securely:

   * Go to **Colab → More → Settings → User secrets**
   * Add:

     ```
     API_KEY = your_alpha_vantage_key_here
     ```
4. Run the notebook.

---

## 📊 Workflow

1. **Create Fortune 100 CSV**

   * Maps companies to stock tickers (`fortune100.csv`).
2. **Fetch stock data**

   * Uses Alpha Vantage free tier (5 API calls/min → `time.sleep(15)`).
3. **Summarize stock trends**

   * Last close, 5-day average, and trend direction.
4. **Query with Falcon-7B**

   * Natural language Q\&A based on stock summaries.

---

## 🖥️ Example Run

```text
💡 Stock LLM ready! Type your query about Fortune 100 companies.
👉 Example: 'Compare Apple and Amazon stock performance over the last 5 days.'
Type 'exit' to stop.

Enter your query: Compare Apple and Amazon stock performance over the last 5 days.

📊 Response:
Apple: latest close $185.21, 5-day avg $183.92, trend up
Amazon: latest close $141.10, 5-day avg $139.84, trend up
Both companies show upward trends, but Apple is trading higher in absolute price.
```

---

## ⚠️ Notes

* **API Limits**: Alpha Vantage free tier allows **25 requests/day**. The notebook respects this with `time.sleep(15)`.
* **Private Companies**: Some Fortune 100 firms (State Farm, USAA, etc.) have no stock tickers and are skipped.
* **GPU**: Optimized for **Colab T4 GPU** with 4-bit quantization.

---

## 📌 Next Steps

* Add **historical trend comparison** (30/60/90 days).
* Extend to **Fortune 500 dataset**.
* Deploy as a **Streamlit app** with live queries.

---
