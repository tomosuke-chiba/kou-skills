import skills from "./skills-data.json" with { type: "json" };

const PROTOCOL_VERSION = "2025-06-18";
const SERVER_INFO = { name: "kou-skills", version: "1.0.0" };
const skillNames = skills.map(({ name }) => name);
const skillByName = new Map(skills.map((skill) => [skill.name, skill]));
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, MCP-Protocol-Version, Mcp-Session-Id, Authorization",
};

const tools = [
  {
    name: "list_skills",
    description: `利用できるAIエージェント用スキルを探すときに使います。用途・プラグイン・説明を一覧し、次にget_skillで読むスキルを選べます。利用可能な${skills.length}スキル: ${skillNames.join(", ")}`,
    inputSchema: {
      type: "object",
      properties: {
        plugin: {
          type: "string",
          enum: ["goal-align", "fulltelop-edit"],
          description: "任意のプラグイン絞り込み",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "get_skill",
    description: "指定したスキルの完全なSKILL.md手順書を取得するときに使います。",
    inputSchema: {
      type: "object",
      properties: { name: { type: "string", enum: skillNames } },
      required: ["name"],
      additionalProperties: false,
    },
  },
  {
    name: "get_skill_reference",
    description: "スキルが参照する補足テキストを取得します。path省略時は利用可能な参照一覧を返します。",
    inputSchema: {
      type: "object",
      properties: {
        name: { type: "string", enum: skillNames },
        path: { type: "string", description: "references/配下からの相対パス" },
      },
      required: ["name"],
      additionalProperties: false,
    },
  },
];

function response(body, status = 200, headers = {}) {
  return new Response(body, { status, headers: { ...corsHeaders, ...headers } });
}

function json(body, status = 200) {
  return response(JSON.stringify(body), status, { "Content-Type": "application/json" });
}

function result(id, value) {
  return json({ jsonrpc: "2.0", id, result: value });
}

function error(id, code, message, data) {
  const detail = { code, message };
  if (data !== undefined) detail.data = data;
  return json({ jsonrpc: "2.0", id: id ?? null, error: detail });
}

function toolText(text, extras = {}) {
  return { content: [{ type: "text", text }], ...extras };
}

function toolFailure(message) {
  return toolText(message, { isError: true });
}

function callTool(params = {}) {
  const args = params.arguments ?? {};
  if (params.name === "list_skills") {
    if (args.plugin !== undefined && !["goal-align", "fulltelop-edit"].includes(args.plugin)) {
      return toolFailure(`Unknown plugin: ${String(args.plugin)}`);
    }
    const selected = args.plugin ? skills.filter(({ plugin }) => plugin === args.plugin) : skills;
    return toolText(selected.map(({ name, plugin, description }) => `${name} [${plugin}] — ${description}`).join("\n"));
  }

  if (params.name === "get_skill") {
    const skill = skillByName.get(args.name);
    if (!skill) return toolFailure(`Unknown skill: ${String(args.name)}`);
    const note = skill.script_files.length > 0
      ? "このスキルはローカルでの実行ファイル（ffmpeg/Python等）を前提とする手順書です。実行環境は利用者のローカルに必要です\n"
      : "";
    return toolText(`${note}${skill.body}`);
  }

  if (params.name === "get_skill_reference") {
    const skill = skillByName.get(args.name);
    if (!skill) return toolFailure(`Unknown skill: ${String(args.name)}`);
    const paths = Object.keys(skill.references);
    if (args.path === undefined) {
      return toolText(paths.length ? paths.join("\n") : "No references available.");
    }
    if (!Object.hasOwn(skill.references, args.path)) {
      return toolFailure(`Unknown reference path: ${String(args.path)}`);
    }
    return toolText(skill.references[args.path]);
  }

  return toolFailure(`Unknown tool: ${String(params.name)}`);
}

function promptList() {
  return skills.map(({ name, description }) => ({ name, description, arguments: [] }));
}

function handleRpc(message) {
  const { id, method, params } = message;
  if (id === undefined) return response(null, 202);

  switch (method) {
    case "initialize": {
      const requested = params?.protocolVersion;
      const protocolVersion = requested === PROTOCOL_VERSION ? requested : PROTOCOL_VERSION;
      return result(id, {
        protocolVersion,
        capabilities: { tools: {}, prompts: {} },
        serverInfo: SERVER_INFO,
      });
    }
    case "ping":
      return result(id, {});
    case "tools/list":
      return result(id, { tools });
    case "tools/call":
      return result(id, callTool(params));
    case "prompts/list":
      return result(id, { prompts: promptList() });
    case "prompts/get": {
      const skill = skillByName.get(params?.name);
      if (!skill) return error(id, -32602, "Invalid params", `Unknown prompt: ${String(params?.name)}`);
      return result(id, {
        description: skill.description,
        messages: [{ role: "user", content: { type: "text", text: skill.body } }],
      });
    }
    default:
      return error(id, -32601, "Method not found");
  }
}

const rootHtml = `<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>KOU Skills MCP</title></head>
<body><main><h1>KOU Skills MCP</h1><p>読み取り専用のスキル配布サーバーです。</p><p>MCP endpoint: <code>/mcp</code></p><p>接続方法: クライアントのリモートMCP設定にこのサーバーの <code>/mcp</code> URLを登録してください。</p></main></body></html>`;

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return response(null, 204);

    if (url.pathname === "/") {
      if (request.method !== "GET") return response("Method Not Allowed", 405, { Allow: "GET, OPTIONS" });
      return response(rootHtml, 200, { "Content-Type": "text/html; charset=utf-8" });
    }

    if (url.pathname !== "/mcp") return response("Not Found", 404);
    if (request.method === "GET") return response("Method Not Allowed", 405, { Allow: "POST, OPTIONS" });
    if (request.method !== "POST") return response("Method Not Allowed", 405, { Allow: "POST, OPTIONS" });

    let message;
    try {
      message = await request.json();
    } catch {
      return error(null, -32700, "Parse error");
    }

    if (!message || typeof message !== "object" || Array.isArray(message) || message.jsonrpc !== "2.0" || typeof message.method !== "string") {
      return error(message?.id, -32600, "Invalid Request");
    }
    return handleRpc(message);
  },
};
