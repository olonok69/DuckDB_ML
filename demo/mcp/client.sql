-- Demo 5 (optional): DuckDB as an MCP client of youtube_ML's own MCP server.
--
-- Build youtube_ML/youtube_mcp first (npm install && npm run build) and put the
-- API key in its environment. Then, from this repository's root:
--     duckdb -init demo/mcp/client.sql
-- Client mode does not run on Windows.

INSTALL duckdb_mcp FROM community;
LOAD duckdb_mcp;

-- Only this command may be started as an MCP server (an allowlist, deny by default).
SET allowed_mcp_commands = 'node';

ATTACH 'node' AS youtube (
    TYPE mcp,
    TRANSPORT 'stdio',
    ARGS '["../youtube_ML/youtube_mcp/dist/index.js"]'
);

-- What the server offers.
SELECT mcp_list_tools('youtube');

-- Call a tool and land its JSON answer in a table, next to the SQLite data.
CREATE TABLE channel_live AS
SELECT mcp_call_tool('youtube', 'get_channel_info', '{"url": "@themachinelearningengineer"}') AS answer;

SELECT * FROM channel_live;
