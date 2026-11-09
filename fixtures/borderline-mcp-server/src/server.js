// An MCP server: LLM clients call these tools, but this process never calls a model.
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({ name: "inventory", version: "1.0.0" });
server.tool("stock_level", { sku: z.string() }, async ({ sku }) => ({
  content: [{ type: "text", text: `SKU ${sku}: 42 in stock` }],
}));
await server.connect(new StdioServerTransport());
