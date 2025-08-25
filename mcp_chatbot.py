import os
import json
import asyncio
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
import mcp.types as types
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client

# -----------------------------
# Function to validate API Key
# -----------------------------
def validate_api_key(api_key: str) -> bool:
    try:
        os.environ["GOOGLE_API_KEY"] = api_key
        test_model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
        _ = test_model.invoke("ping")   # simple lightweight test
        return True
    except Exception:
        return False

# -----------------------------
# Block screen for API Key
# -----------------------------
st.set_page_config(page_title="MCP + Gemini SQL Query", layout="wide")
st.title("🔒 Secure Access")

if "validated" not in st.session_state:
    st.session_state.validated = False
if "user_api_key" not in st.session_state:
    st.session_state.user_api_key = ""

if not st.session_state.validated:
    st.info("Please enter your Gemini API key to unlock the app.")
    st.session_state.user_api_key = st.text_input(
        "🔑 Enter your Gemini API Key",
        type="password",
        value=st.session_state.user_api_key
    )

    if st.button("Validate Key"):
        with st.spinner("Validating API key..."):
            if validate_api_key(st.session_state.user_api_key):
                st.session_state.validated = True
                st.success("✅ API Key validated successfully! You can now use the app.")
                st.rerun()
            else:
                st.error("❌ Invalid Gemini API Key. Please try again.")
    st.stop()  # Block rest of the app

# -----------------------------
# Database Connection String
# -----------------------------
DB_LINK = (
    "mssql+pyodbc://admin123:Password123@chatbotdatabase123.database.windows.net:1433/"
    "chatbotdatabase?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30"
)

# -----------------------------
# Core APIs
# -----------------------------
async def create_agent():
    """Create MCP client with SQL server"""
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-sql", DB_LINK]
    )
    
    async with stdio_client(server_params) as client:
        await client.initialize()
        return client

async def call_mcp(client, prompt: str):
    """Call the MCP server with a prompt"""
    try:
        result = await client.sampling(prompt=prompt)
        return result
    except Exception as e:
        return f"Error: {str(e)}"

# -----------------------------
# Schema Fetching
# -----------------------------
async def load_schema_async():
    """Asynchronously load database schema"""
    try:
        client = await create_agent()
        rows = await call_mcp(client, """
            SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION;
        """)

        schema = {}
        if rows and not rows.startswith("Error:"):
            try:
                rows_list = json.loads(rows) if isinstance(rows, str) else rows
                for row in rows_list:
                    if isinstance(row, dict):
                        sch, tbl, col = row.get("TABLE_SCHEMA"), row.get("TABLE_NAME"), row.get("COLUMN_NAME")
                    else:
                        sch, tbl, col = row[:3]
                    key = f"{sch}.{tbl}"
                    schema.setdefault(key, []).append(col)
                return {"status": "success", "schema": schema}
            except json.JSONDecodeError:
                return {"status": "success", "schema": {"raw_output": rows}}
        return {"status": "error", "message": rows}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def load_schema():
    """Synchronous wrapper for schema loading"""
    return asyncio.run(load_schema_async())

# -----------------------------
# Query Execution
# -----------------------------
async def run_query_async(user_query, schema_info):
    """Asynchronously run query"""
    try:
        client = await create_agent()
        prompt = f"""
You are connected to Azure SQL Server.
Schema (schema.table -> columns): {schema_info}
Generate and run the SQL to answer: {user_query}
Return the results in JSON format if possible.
"""
        result = await call_mcp(client, prompt)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def run_query(user_query, schema_info):
    """Synchronous wrapper for query execution"""
    return asyncio.run(run_query_async(user_query, schema_info))

# -----------------------------
# Main App UI (Unlocked)
# -----------------------------
st.title("Query Your Azure SQL with MCP + Gemini")

if "schema" not in st.session_state:
    st.session_state.schema = None
if "result" not in st.session_state:
    st.session_state.result = None

if st.button("Load Schema"):
    with st.spinner("Loading schema..."):
        resp = load_schema()
    if resp["status"] == "success":
        st.session_state.schema = resp["schema"]
        st.success("✅ Schema loaded")
        if isinstance(resp["schema"], dict) and "raw_output" not in resp["schema"]:
            st.json(st.session_state.schema)
        else:
            st.write(st.session_state.schema)
    else:
        st.error(f"Failed: {resp.get('message')}")

query = st.text_input("Enter your query:")

if st.button("Run Query"):
    if not st.session_state.schema:
        st.warning("⚠️ Load schema first")
    else:
        with st.spinner("Running..."):
            resp = run_query(query, st.session_state.schema)
        if resp["status"] == "success":
            st.success("✅ Query executed")
            st.session_state.result = resp["result"]
            try:
                if isinstance(resp["result"], str) and resp["result"].strip().startswith('['):
                    df = pd.DataFrame(json.loads(resp["result"]))
                    st.dataframe(df)
                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button("Download CSV", csv, "query.csv", "text/csv")
                else:
                    st.write(resp["result"])
            except (json.JSONDecodeError, TypeError):
                st.write(resp["result"])
        else:
            st.error(f"Error: {resp.get('message')}")

# -----------------------------
# Display current schema if available
# -----------------------------
if st.session_state.schema:
    st.subheader("Current Schema")
    st.json(st.session_state.schema)
