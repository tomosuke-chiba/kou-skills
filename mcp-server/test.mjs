import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { inflateSync } from "node:zlib";

const MCP_URL = "https://example.test/mcp";
const serverDir = path.dirname(fileURLToPath(import.meta.url));
const repositoryDir = path.dirname(serverDir);
let worker;
let pass = 0;
let fail = 0;

const pngSignature = Buffer.from("89504e470d0a1a0a", "hex");
const crcTable = new Uint32Array(256);
for (let index = 0; index < crcTable.length; index += 1) {
  let value = index;
  for (let bit = 0; bit < 8; bit += 1) {
    value = (value & 1) === 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  }
  crcTable[index] = value >>> 0;
}

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function assertDecodedPixels(decoded, { width, height, bitDepth, colorType, interlace }, imageFile) {
  const channelsByColorType = new Map([[0, 1], [2, 3], [3, 1], [4, 2], [6, 4]]);
  const validBitDepths = new Map([
    [0, [1, 2, 4, 8, 16]],
    [2, [8, 16]],
    [3, [1, 2, 4, 8]],
    [4, [8, 16]],
    [6, [8, 16]],
  ]);
  assert.ok(channelsByColorType.has(colorType), `invalid PNG color type: ${imageFile}`);
  assert.ok(validBitDepths.get(colorType).includes(bitDepth), `invalid PNG bit depth for color type: ${imageFile}`);

  const passes = interlace === 0
    ? [[0, 0, 1, 1]]
    : [
        [0, 0, 8, 8],
        [4, 0, 8, 8],
        [0, 4, 4, 8],
        [2, 0, 4, 4],
        [0, 2, 2, 4],
        [1, 0, 2, 2],
        [0, 1, 1, 2],
      ];
  const bitsPerPixel = channelsByColorType.get(colorType) * bitDepth;
  let offset = 0;

  for (const [xStart, yStart, xStep, yStep] of passes) {
    const passWidth = width <= xStart ? 0 : Math.ceil((width - xStart) / xStep);
    const passHeight = height <= yStart ? 0 : Math.ceil((height - yStart) / yStep);
    if (passWidth === 0 || passHeight === 0) continue;
    const scanlineLength = Math.ceil((passWidth * bitsPerPixel) / 8);
    for (let row = 0; row < passHeight; row += 1) {
      assert.ok(offset < decoded.length, `PNG pixel rows are truncated: ${imageFile}`);
      assert.ok(decoded[offset] <= 4, `invalid PNG scanline filter: ${imageFile}`);
      offset += 1 + scanlineLength;
      assert.ok(offset <= decoded.length, `PNG scanline data is truncated: ${imageFile}`);
    }
  }

  assert.equal(offset, decoded.length, `PNG pixel data length does not match its dimensions: ${imageFile}`);
}

function visibleMarkdownLines(markdown) {
  const visible = [];
  let inComment = false;
  let fenceCharacter;
  let fenceLength = 0;

  for (const rawLine of markdown.split("\n")) {
    let line = "";
    let cursor = 0;
    while (cursor < rawLine.length) {
      if (inComment) {
        const end = rawLine.indexOf("-->", cursor);
        if (end === -1) {
          cursor = rawLine.length;
          continue;
        }
        inComment = false;
        cursor = end + 3;
      } else {
        const start = rawLine.indexOf("<!--", cursor);
        if (start === -1) {
          line += rawLine.slice(cursor);
          cursor = rawLine.length;
        } else {
          line += rawLine.slice(cursor, start);
          inComment = true;
          cursor = start + 4;
        }
      }
    }

    if (fenceCharacter) {
      const closingFence = line.match(/^ {0,3}(`{3,}|~{3,})\s*$/);
      if (closingFence && closingFence[1][0] === fenceCharacter && closingFence[1].length >= fenceLength) {
        fenceCharacter = undefined;
        fenceLength = 0;
      }
      continue;
    }

    const openingFence = line.match(/^ {0,3}(`{3,}|~{3,})/);
    if (openingFence) {
      fenceCharacter = openingFence[1][0];
      fenceLength = openingFence[1].length;
      continue;
    }
    if (/^( {4}|\t)/.test(line)) continue;
    visible.push(line);
  }

  return visible;
}

function inspectPng(image, imageFile) {
  assert.ok(image.length >= 33, `PNG is truncated: ${imageFile}`);
  assert.ok(image.subarray(0, 8).equals(pngSignature), `not a PNG: ${imageFile}`);

  let offset = 8;
  let chunkIndex = 0;
  let width;
  let height;
  let bitDepth;
  let colorType;
  let interlace;
  let sawIend = false;
  const idatChunks = [];

  while (offset < image.length) {
    assert.ok(offset + 12 <= image.length, `PNG chunk header is truncated: ${imageFile}`);
    const length = image.readUInt32BE(offset);
    const typeStart = offset + 4;
    const dataStart = offset + 8;
    const dataEnd = dataStart + length;
    const chunkEnd = dataEnd + 4;
    assert.ok(chunkEnd <= image.length, `PNG chunk data is truncated: ${imageFile}`);

    const type = image.subarray(typeStart, dataStart).toString("ascii");
    assert.match(type, /^[A-Za-z]{4}$/, `invalid PNG chunk type: ${imageFile}`);
    const expectedCrc = image.readUInt32BE(dataEnd);
    const actualCrc = crc32(image.subarray(typeStart, dataEnd));
    assert.equal(actualCrc, expectedCrc, `PNG chunk CRC mismatch (${type}): ${imageFile}`);

    if (chunkIndex === 0) assert.equal(type, "IHDR", `PNG must start with IHDR: ${imageFile}`);
    if (type === "IHDR") {
      assert.equal(length, 13, `invalid IHDR length: ${imageFile}`);
      width = image.readUInt32BE(dataStart);
      height = image.readUInt32BE(dataStart + 4);
      bitDepth = image[dataStart + 8];
      colorType = image[dataStart + 9];
      assert.equal(image[dataStart + 10], 0, `unsupported PNG compression method: ${imageFile}`);
      assert.equal(image[dataStart + 11], 0, `unsupported PNG filter method: ${imageFile}`);
      interlace = image[dataStart + 12];
      assert.ok([0, 1].includes(interlace), `invalid PNG interlace method: ${imageFile}`);
    } else if (type === "IDAT") {
      idatChunks.push(image.subarray(dataStart, dataEnd));
    } else if (type === "IEND") {
      assert.equal(length, 0, `invalid IEND length: ${imageFile}`);
      sawIend = true;
      assert.equal(chunkEnd, image.length, `unexpected bytes after IEND: ${imageFile}`);
    }

    offset = chunkEnd;
    chunkIndex += 1;
    if (sawIend) break;
  }

  assert.ok(width > 0 && height > 0, `invalid PNG dimensions: ${imageFile}`);
  assert.ok(idatChunks.length > 0, `PNG has no image data: ${imageFile}`);
  assert.ok(sawIend, `PNG has no IEND chunk: ${imageFile}`);
  const decoded = inflateSync(Buffer.concat(idatChunks));
  assertDecodedPixels(decoded, { width, height, bitDepth, colorType, interlace }, imageFile);
  return { width, height };
}

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

await test("14 every skill has exactly one dedicated 16:9 PNG shown in README", async () => {
  const pluginDirectory = path.join(repositoryDir, "plugins");
  const pluginEntries = (await readdir(pluginDirectory, { withFileTypes: true })).filter((entry) => entry.isDirectory());
  const sourceSkillNames = [];
  for (const pluginEntry of pluginEntries) {
    const skillsDirectory = path.join(pluginDirectory, pluginEntry.name, "skills");
    const skillEntries = (await readdir(skillsDirectory, { withFileTypes: true })).filter((entry) => entry.isDirectory());
    for (const skillEntry of skillEntries) {
      await readFile(path.join(skillsDirectory, skillEntry.name, "SKILL.md"), "utf8");
      sourceSkillNames.push(skillEntry.name);
    }
  }
  sourceSkillNames.sort();

  const bundledSkills = (await import("./src/skills-data.json", { with: { type: "json" } })).default;
  const bundledSkillNames = bundledSkills.map(({ name }) => name).sort();
  assert.deepEqual(bundledSkillNames, sourceSkillNames, "skills-data.json must be rebuilt after every Skill change");

  const imageDirectory = path.join(repositoryDir, "docs", "images", "skills");
  const imageFiles = (await readdir(imageDirectory)).filter((name) => name.endsWith(".png")).sort();
  const readme = await readFile(path.join(repositoryDir, "README.md"), "utf8");
  const visibleReadmeLines = visibleMarkdownLines(readme);
  const coveredNames = [];
  const imageNumbers = [];

  for (const imageFile of imageFiles) {
    const match = imageFile.match(/^(\d{2})-(.+)\.png$/);
    assert.ok(match, `dedicated image must use NN-skill-name.png: ${imageFile}`);
    imageNumbers.push(Number(match[1]));
    const skillName = match[2];
    assert.ok(sourceSkillNames.includes(skillName), `dedicated image has no matching skill: ${imageFile}`);
    coveredNames.push(skillName);

    const image = await readFile(path.join(imageDirectory, imageFile));
    const { width, height } = inspectPng(image, imageFile);
    assert.ok(width >= 1600 && height >= 900, `dedicated image is below the required production size: ${imageFile} is ${width}x${height}`);
    assert.ok(Math.abs(width - (height * 16) / 9) <= 1, `dedicated image must be 16:9 within one raster pixel: ${imageFile} is ${width}x${height}`);

    const markdown = `![${skillName}](docs/images/skills/${imageFile})`;
    assert.equal(readme.split(markdown).length - 1, 1, `README must display dedicated image exactly once: ${imageFile}`);
    const heading = `#### ${skillName}`;
    const headingIndexes = visibleReadmeLines.flatMap((line, index) => line === heading ? [index] : []);
    assert.equal(headingIndexes.length, 1, `README must contain exactly one visible heading for the Skill: ${skillName}`);
    const nextContentLine = visibleReadmeLines.slice(headingIndexes[0] + 1).find((line) => line.trim() !== "");
    assert.equal(nextContentLine, markdown, `README must display the image directly below its matching Skill heading: ${imageFile}`);
  }

  const expectedNumbers = Array.from({ length: imageFiles.length }, (_, index) => index + 1);
  assert.deepEqual(imageNumbers.sort((a, b) => a - b), expectedNumbers, "dedicated image numbers must be unique and contiguous from 01");
  assert.deepEqual(coveredNames.sort(), sourceSkillNames, "every skill must have exactly one dedicated PNG");
});

console.log(`\nRESULT PASS ${pass} FAIL ${fail} TOTAL ${pass + fail}`);
if (fail > 0) process.exitCode = 1;
