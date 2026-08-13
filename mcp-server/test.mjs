import assert from "node:assert/strict";

const MCP_URL = "https://example.test/mcp";
let worker;
let pass = 0;
let fail = 0;

async function getWorker() {
  if (!worker) {
    const module = await import("./src/index.js");
    worker = module.default;
  }
  return worker;
}

async function request(method, params, ...ids) {
  const id = ids.length === 0 ? 1 : ids[0];
  const handler = await getWorker();
  const message = { jsonrpc: "2.0", method };
  if (params !== undefined) message.params = params;
  if (id !== undefined) message.id = id;
  return handler.fetch(new Request(MCP_URL, {
    method: "POST",
    headers: {
      Accept: "application/json, text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(message),
  }), {}, {});
}

async function rpc(method, params, id = 1) {
  const response = await request(method, params, id);
  return { response, body: await response.json() };
}

async function test(name, fn) {
  try {
    await fn();
    pass += 1;
    console.log(`PASS ${name}`);
  } catch (error) {
    fail += 1;
    console.error(`FAIL ${name}: ${error.message}`);
  }
}

await test("1 initialize negotiates protocol and identifies server", async () => {
  const { body } = await rpc("initialize", {
    protocolVersion: "2025-06-18",
    capabilities: {},
    clientInfo: { name: "test", version: "1.0.0" },
  });
  assert.equal(body.result.protocolVersion, "2025-06-18");
  assert.deepEqual(body.result.serverInfo, { name: "kou-skills", version: "1.0.0" });
});

await test("2 initialized notification returns 202", async () => {
  const response = await request("notifications/initialized", {}, undefined);
  assert.equal(response.status, 202);
  assert.equal(await response.text(), "");
});

await test("3 ping returns empty result", async () => {
  const { body } = await rpc("ping");
  assert.deepEqual(body.result, {});
});

await test("4 tools/list returns exactly three tools", async () => {
  const { body } = await rpc("tools/list");
  assert.equal(body.result.tools.length, 3);
  assert.deepEqual(body.result.tools.map(({ name }) => name), [
    "list_skills", "get_skill", "get_skill_reference",
  ]);
});

await test("5 list_skills returns all 22 skill names", async () => {
  const { body } = await rpc("tools/call", { name: "list_skills", arguments: {} });
  const text = body.result.content[0].text;
  const skills = (await import("./src/skills-data.json", { with: { type: "json" } })).default;
  assert.equal(skills.length, 22);
  for (const skill of skills) assert.match(text, new RegExp(`(^|\\W)${skill.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}($|\\W)`));
});

await test("6 get_skill returns the dod SKILL.md", async () => {
  const { body } = await rpc("tools/call", { name: "get_skill", arguments: { name: "dod" } });
  assert.equal(body.result.isError, undefined);
  assert.match(body.result.content[0].text, /^---\nname: dod\n/);
  assert.match(body.result.content[0].text, /目的逆算思考DoD/);
});

await test("7 get_skill returns the project-flow-diagram SKILL.md", async () => {
  const { body } = await rpc("tools/call", { name: "get_skill", arguments: { name: "project-flow-diagram" } });
  assert.equal(body.result.isError, undefined);
  assert.match(body.result.content[0].text, /^---\nname: project-flow-diagram\n/);
  assert.match(body.result.content[0].text, /全体の流れ・現在地・次の一手/);
});

await test("8 get_skill rejects an unknown skill", async () => {
  const { body } = await rpc("tools/call", { name: "get_skill", arguments: { name: "does-not-exist" } });
  assert.ok(body.error || body.result?.isError === true);
});

await test("9 prompts/list returns 22 prompts", async () => {
  const { body } = await rpc("prompts/list");
  assert.equal(body.result.prompts.length, 22);
});

await test("10 prompts/get returns the requested skill body", async () => {
  const { body } = await rpc("prompts/get", { name: "dod", arguments: {} });
  assert.equal(body.result.messages[0].role, "user");
  assert.match(body.result.messages[0].content.text, /^---\nname: dod\n/);
});

await test("11 unknown method returns -32601", async () => {
  const { body } = await rpc("unknown/method");
  assert.equal(body.error.code, -32601);
});

await test("12 GET /mcp returns 405", async () => {
  const handler = await getWorker();
  const response = await handler.fetch(new Request(MCP_URL), {}, {});
  assert.equal(response.status, 405);
});

await test("13 OPTIONS /mcp returns 204 with CORS", async () => {
  const handler = await getWorker();
  const response = await handler.fetch(new Request(MCP_URL, { method: "OPTIONS" }), {}, {});
  assert.equal(response.status, 204);
  assert.equal(response.headers.get("Access-Control-Allow-Origin"), "*");
  assert.match(response.headers.get("Access-Control-Allow-Methods"), /POST/);
});

console.log(`\nRESULT PASS ${pass} FAIL ${fail} TOTAL ${pass + fail}`);
if (fail > 0) process.exitCode = 1;
