import streamlit as st
import asyncio
from mcp.client.stdio import stdio_client
from mcp.client.stdio import StdioServerParameters
import requests  # For Gemini API validation
import os

st.set_page_config(page_title="MCP SQL Query Runner", layout="wide")
st.title("⚡ MCP SQL Query Runner")

# Initialize session state for connection status
if 'db_connected' not in st.session_state:
    st.session_state.db_connected = False
if 'gemini_validated' not in st.session_state:
    st.session_state.gemini_validated = False

# -------------------------------
# User inputs for Gemini API
# -------------------------------
st.subheader("🔑 Enter Gemini API Key")

gemini_api_key = st.text_input("Gemini API Key", type="password", 
                              placeholder="Enter your Gemini API key")

# Validate Gemini API key
def validate_gemini_api(api_key):
    if not api_key:
        return False, "API key is empty"
    
    try:
        # Simple validation - try to make a basic request to Gemini API
        response = requests.get(
            "https://generativelanguage.googleapis.com/v1/models",
            params={"key": api_key},
            timeout=10
        )
        
        if response.status_code == 200:
            return True, "✅ Gemini API key is valid"
        else:
            return False, f"❌ Gemini API validation failed: {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"❌ Error validating Gemini API: {str(e)}"

if st.button("Validate Gemini API"):
    if gemini_api_key:
        with st.spinner("Validating Gemini API key..."):
            is_valid, message = validate_gemini_api(gemini_api_key)
            if is_valid:
                st.session_state.gemini_validated = True
                st.success(message)
            else:
                st.session_state.gemini_validated = False
                st.error(message)
    else:
        st.error("Please enter a Gemini API key")

# -------------------------------
# User inputs for DB connection
# -------------------------------
st.subheader("🔑 Enter SQL Database Credentials")

server = st.text_input("Server", placeholder="e.g., chatbotdatabase123.database.windows.net")
database = st.text_input("Database", placeholder="e.g., chatbotdatabase")
username = st.text_input("Username", placeholder="e.g., admin123")
password = st.text_input("Password", type="password")

# Build connection string (Azure SQL with ODBC)
conn_str = ""
if server and database and username and password:
    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={server},1433;"
        f"Database={database};"
        f"Uid={username};"
        f"Pwd={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30;"
    )

# Validate database connection using MCP server
async def validate_db_connection_mcp(connection_string):
    if not connection_string:
        return False, "Connection string is empty"
    
    try:
        params = StdioServerParameters(
            command="npx",
            args=[
                "-y",
                "@modelcontextprotocol/server-sql",
                "--connection-string", connection_string
            ]
        )

        async with stdio_client(params) as (read, write):
            # Try to list tables to test the connection
            result = await write.call_tool("query", {"query": "SELECT 1 AS test"})
            return True, "✅ Database connection successful"
    except Exception as e:
        return False, f"❌ Database connection failed: {str(e)}"

if st.button("Test Database Connection"):
    if conn_str:
        with st.spinner("Testing database connection..."):
            is_connected, message = asyncio.run(validate_db_connection_mcp(conn_str))
            if is_connected:
                st.session_state.db_connected = True
                st.success(message)
            else:
                st.session_state.db_connected = False
                st.error(message)
    else:
        st.error("Please fill in all database credentials")

# Show connection status
if st.session_state.gemini_validated and st.session_state.db_connected:
    st.success("✅ Both Gemini API and Database are successfully connected!")
elif st.session_state.gemini_validated:
    st.info("✅ Gemini API connected, but database not yet validated")
elif st.session_state.db_connected:
    st.info("✅ Database connected, but Gemini API not yet validated")

# -------------------------------
# User input for SQL query (only show if both validations passed)
# -------------------------------
if st.session_state.gemini_validated and st.session_state.db_connected:
    st.subheader("📝 Write your SQL query")
    query = st.text_area(
        "SQL Query",
        placeholder="e.g., SELECT TOP 10 * FROM SalesLT.Customer"
    )

    # -------------------------------
    # MCP SQL Execution Function
    # -------------------------------
    async def run_mcp_query(conn_str: str, query: str):
        if not conn_str:
            return "❌ Connection string is missing."
        if not query:
            return "❌ SQL query is missing."

        params = StdioServerParameters(
            command="npx",
            args=[
                "-y",
                "@modelcontextprotocol/server-sql",
                "--connection-string", conn_str
            ]
        )

        async with stdio_client(params) as (read, write):
            # List tools
            tools = await write.list_tools()
            sql_tool = next((t for t in tools if "query" in t.name.lower()), None)
            if not sql_tool:
                return "❌ No SQL query tool found in MCP server."

            # Execute query
            result = await write.call_tool(sql_tool.name, {"query": query})
            return result.content[0].text if result.content else "✅ Query executed, but no results."

    # -------------------------------
    # Run query button
    # -------------------------------
    if st.button("🚀 Run Query"):
        if not query:
            st.error("Please provide a SQL query.")
        else:
            with st.spinner("Running query via MCP..."):
                try:
                    result = asyncio.run(run_mcp_query(conn_str, query))
                    st.success("Query Completed ✅")
                    st.code(result, language="sql")
                except Exception as e:
                    st.error(f"Error running query: {str(e)}")
else:
    st.info("Please validate both Gemini API and Database connection to enable query execution")
