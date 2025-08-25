import os
import json
import asyncio
import pandas as pd
import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
import mcp.types as types
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client

# --------------------------
# Streamlit App
# --------------------------
st.set_page_config(page_title="MCP + Gemini SQL Chatbot", layout="wide")

# Step 1: API Key Input Gate
if "api_key" not in st.session_state:
    st.session_state.api_key = None

if not st.session_state.api_key:
    st.title("🔑 Enter your Gemini API Key")
    api_key_input = st.text_input("Gemini API Key", type="password")

    if st.button("Validate Key"):
        try:
            # Test the key by calling Gemini
            test_model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key_input)
            test_model.invoke("Say hello!")  # quick validation
            st.session_state.api_key = api_key_input
            st.success("✅ API Key validated successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Invalid API Key: {str(e)}")
    st.stop()

# Step 2: Main Chatbot Screen
st.title("💬 Query Your Azure SQL with MCP + Gemini")

# Input query
user_question = st.text_input(
    "Ask a question about your Azure SQL data:",
    placeholder="e.g., Show me the top 10 customers by total sales"
)

# Button to run query
if st.button("Run Query"):
    if not user_question.strip():
        st.warning("Please enter a question.")
    else:
        try:
            # Initialize Gemini with user-provided key
            model = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=st.session_state.api_key
            )

            # For demo purposes, just echo user query
            response = model.invoke(f"Generate SQL for this question: {user_question}")
            st.subheader("Generated SQL Query")
            st.code(response.content, language="sql")

            # ⚠️ Next step: Use MCP SQL connector to actually run query
            st.info("MCP SQL execution not yet implemented in this snippet.")

        except Exception as e:
            st.error(f"Error: {str(e)}")
