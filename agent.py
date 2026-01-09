import streamlit as st
import pandas as pd
import os
import json as jsonlib 
import time
import logging
import re
from typing import TypedDict, Annotated, List
import operator
from datetime import datetime, timedelta
import plotly.graph_objects as go # <--- NEW IMPORT FOR CHARTS

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from market_db import MarketDB
from retriever import sync_ticker_data

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "agent.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("stock-agent")

# =============================================================================
# APP CONFIG & LAYOUT
# =============================================================================

st.set_page_config(
    page_title="Market Analyst", 
    page_icon="📈", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Initialize DB
os.makedirs("data", exist_ok=True)
db = MarketDB(os.path.join("data", "stocks.db"))

# =============================================================================
# PART 1: MAIN PAGE - THE DATABASE DASHBOARD
# =============================================================================

st.title("🗄️ Market Database Dashboard")

# 1. Fetch Tickers
@st.cache_data(ttl=60)
def get_all_tickers():
    try:
        conn = db._get_conn()
        df = pd.read_sql("SELECT ticker, company_name FROM metadata ORDER BY company_name", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame(columns=["ticker", "company_name"])

df_tickers = get_all_tickers()

if df_tickers.empty:
    st.info("👋 **Welcome!** The database is currently empty.")
    st.markdown("Use the **AI Assistant** in the sidebar to fetch your first stock data.")
    st.markdown("Try asking: *'Fetch data for Reliance and TCS for 2026'*")

else:
    # Dashboard Controls
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            df_tickers["display"] = df_tickers["company_name"] + " (" + df_tickers["ticker"] + ")"
            selected_display = st.selectbox("Select Company:", df_tickers["display"])
            selected_ticker = df_tickers.loc[df_tickers["display"] == selected_display, "ticker"].iloc[0]

        with col2:
            start_val = st.date_input("Start Date", value=datetime.today() - timedelta(days=90))
        
        with col3:
            end_val = st.date_input("End Date", value="today")

        with col4:
            st.write("") # Spacer
            st.write("") # Spacer
            refresh_btn = st.button("🔄 Refresh View", use_container_width=True)

    # Data Fetching
    if selected_ticker:
        s_str = start_val.strftime("%Y-%m-%d")
        e_str = end_val.strftime("%Y-%m-%d")
        
        df_data = db.get_price_history(selected_ticker, s_str, e_str)

        if not df_data.empty:
            # Metrics Row
            latest = df_data.iloc[-1]
            earliest = df_data.iloc[0]
            change = ((latest['close'] - earliest['open']) / earliest['open']) * 100
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Latest Close", f"₹{latest['close']:.2f}")
            m2.metric("Volume", f"{int(latest['volume']):,}")
            m3.metric("High (Period)", f"₹{df_data['high'].max():.2f}")
            m4.metric("Period Return", f"{change:.2f}%", delta_color="normal")

            # --- REVAMPED CHARTS SECTION ---
            tab_chart, tab_data = st.tabs(["📈 Candlestick Chart", "🔢 Raw Data"])
            
            with tab_chart:
                df_data["date"] = pd.to_datetime(df_data["date"])
                
                # Create interactive Candlestick chart
                fig = go.Figure(data=[go.Candlestick(
                    x=df_data['date'],
                    open=df_data['open'],
                    high=df_data['high'],
                    low=df_data['low'],
                    close=df_data['close'],
                    name=selected_ticker
                )])

                # Enhance layout
                fig.update_layout(
                    title=f"Price Movement: {selected_ticker}",
                    yaxis_title="Price (INR)",
                    xaxis_title="Date",
                    height=600,
                    template="plotly_dark", # Looks great in dark mode
                    xaxis_rangeslider_visible=False # Hide bottom slider to save space
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            with tab_data:
                st.dataframe(df_data.sort_values("date", ascending=False), use_container_width=True)
        else:
            st.warning(f"No data available for **{selected_ticker}** in this range.")
            st.caption("👈 **Tip:** Ask the AI Assistant to fetch this missing data.")


# =============================================================================
# PART 2: SIDEBAR - THE AI COPILOT
# =============================================================================

with st.sidebar:
    st.header("🤖 AI Copilot")
    
    # Model Selector
    model_choice = st.radio(
        "Model:",
        ("Qwen 2.5 (14B)", "Mistral 7B"),
        horizontal=True,
        label_visibility="collapsed"
    )
    
    MODEL_MAP = {"Qwen 2.5 (14B)": "qwen2.5:14b", "Mistral 7B": "mistral"}
    selected_model_tag = MODEL_MAP[model_choice]
    
    st.divider()

    # Chat Container (Scrollable)
    messages_container = st.container(height=500)
    
    # Input Area (Pinned to bottom of sidebar)
    user_input = st.chat_input(f"Message {model_choice}...")


# =============================================================================
# PART 3: AGENT LOGIC (Hidden Backend)
# =============================================================================

# --- TOOLS ---
@tool(description="Resolve a company name or partial ticker into a full exchange ticker.")
def lookup_stock(query: str) -> str:
    """Resolve a company name or partial ticker into a FULL exchange ticker."""
    start = time.time()
    result = db.search_ticker(query)
    output = f"{result['company_name']} | TICKER={result['ticker']}" if result else "No matching stock found."
    logger.info(jsonlib.dumps({"event": "tool_exec", "tool": "lookup_stock", "duration": round(time.time() - start, 3)}))
    return output

@tool(description="Return historical OHLCV stock data for a date range.")
def get_stock_history(ticker: str, start_date: str | None = None, end_date: str | None = None) -> str:
    """Return historical stock prices from the local SQLite database."""
    start = time.time()
    resolved = db.search_ticker(ticker)
    if resolved: ticker = resolved["ticker"]
    
    df = db.get_price_history(ticker, start_date, end_date)
    if df.empty:
        sync_ticker_data(ticker, start=start_date, end=end_date)
        df = db.get_price_history(ticker, start_date, end_date)
    
    output = df.to_string(index=False) if not df.empty else f"No data found for {ticker}."
    logger.info(jsonlib.dumps({"event": "tool_exec", "tool": "get_stock_history", "duration": round(time.time() - start, 3)}))
    return output

@tool(description="Return OHLCV stock data for ONE specific date.")
def get_stock_on_date(ticker: str, date: str) -> str:
    """Return stock OHLCV data for a single date (YYYY-MM-DD)."""
    start = time.time()
    resolved = db.search_ticker(ticker)
    if resolved: ticker = resolved["ticker"]
    
    df = db.get_price_history(ticker, date, date)
    output = df.to_string(index=False) if not df.empty else f"No data found for {ticker} on {date}."
    logger.info(jsonlib.dumps({"event": "tool_exec", "tool": "get_stock_on_date", "duration": round(time.time() - start, 3)}))
    return output

TOOLS = [lookup_stock, get_stock_history, get_stock_on_date]

# --- AGENT SETUP ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

if "mistral" in selected_model_tag:
    SYSTEM_PROMPT = SystemMessage(content="You are a stock data assistant.\nRULES:\n1. If data is missing, call a tool to fetch it.\n2. Convert dates to YYYY-MM-DD.\n3. Answer concisely.")
else:
    SYSTEM_PROMPT = SystemMessage(content="You are a financial data assistant.\nCORE ROLE: Fetch data using tools so it appears in the Dashboard.\nRULES:\n1. Always use tools for data requests.\n2. Convert dates to 'YYYY-MM-DD'.\n3. Be brief.")

llm = ChatOllama(model=selected_model_tag, temperature=0)
llm_with_tools = llm.bind_tools(TOOLS)

def agent_node(state: AgentState):
    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SYSTEM_PROMPT] + messages
    
    response = llm_with_tools.invoke(messages)

    # Parser Shim (Mistral Fix)
    if not response.tool_calls and response.content:
        match = re.search(r"\[\s*\{.*?\}\s*\]", response.content, re.DOTALL)
        if match:
            try:
                parsed = jsonlib.loads(match.group(0))
                parsed = parsed if isinstance(parsed, list) else [parsed]
                response.tool_calls = [{"name": parsed[0]["name"], "args": parsed[0]["arguments"], "id": "manual_fix"}]
                response.content = ""
            except: pass

    return {"messages": [response]}

def should_continue(state: AgentState):
    return "tools" if state["messages"][-1].tool_calls else END

workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(TOOLS))
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")
app_agent = workflow.compile()

# =============================================================================
# PART 4: RENDERING THE CHAT (Inside Sidebar)
# =============================================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

# 1. Render History
with messages_container:
    for msg in st.session_state.messages:
        if isinstance(msg, HumanMessage):
            with st.chat_message("user"): st.markdown(msg.content)
        elif isinstance(msg, AIMessage):
            with st.chat_message("assistant"): st.markdown(msg.content)

# 2. Handle Input
if user_input:
    # Add User Message
    st.session_state.messages.append(HumanMessage(content=user_input))
    with messages_container:
        with st.chat_message("user"): st.markdown(user_input)
        
        # Run Agent
        with st.chat_message("assistant"):
            with st.spinner("..."):
                final_text = None
                for event in app_agent.stream({"messages": st.session_state.messages}):
                    for node, value in event.items():
                        if node == "tools":
                            tool_msg = value["messages"][0]
                            st.caption(f"⚡ Fetched: {tool_msg.name}")
                        elif node == "agent":
                            msg = value["messages"][0]
                            if msg.content: final_text = msg.content
                
                if final_text:
                    st.markdown(final_text)
                    st.session_state.messages.append(AIMessage(content=final_text))
                    # FORCE REFRESH TO UPDATE MAIN DASHBOARD
                    st.rerun()