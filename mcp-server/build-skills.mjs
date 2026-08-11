import { readdir, readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const serverDir = path.dirname(fileURLToPath(import.meta.url));
const repositoryDir = path.dirname(serverDir);
const pluginsDir = path.join(repositoryDir, "plugins");
const outputFile = path.join(serverDir, "src", "skills-data.json");
const textExtensions = new Set([".md", ".json", ".txt", ".yml", ".yaml"]);

async function directories(parent) {
  return (await readdir(parent, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort((a, b) => a.localeCompare(b));
}

async function filesRecursively(parent, relative = "") {
  const current = path.join(parent, relative);
  let entries;
  try {
    entries = await readdir(current, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }

  const files = [];
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    const child = path.posix.join(relative, entry.name);
    if (entry.isDirectory()) files.push(...await filesRecursively(parent, child));
    else if (entry.isFile()) files.push(child);
  }
  return files;
}

function frontmatterValue(body, key) {
  const match = body.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
  if (!match) return undefined;
  const line = match[1].split(/\r?\n/).find((item) => item.startsWith(`${key}:`));
  if (!line) return undefined;
  const value = line.slice(key.length + 1).trim();
  if (!value || value === ">" || value === ">-" || value === "|" || value === "|-") return undefined;
  return value.replace(/^("|')([\s\S]*)\1$/, "$2");
}

function firstBodyLine(body) {
  return body
    .replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/, "")
    .split(/\r?\n/)
    .map((line) => line.replace(/^#+\s*/, "").trim())
    .find(Boolean) ?? "";
}

const skills = [];
for (const plugin of await directories(pluginsDir)) {
  const skillsDir = path.join(pluginsDir, plugin, "skills");
  let skillNames;
  try {
    skillNames = await directories(skillsDir);
  } catch (error) {
    if (error.code === "ENOENT") continue;
    throw error;
  }

  for (const name of skillNames) {
    const skillDir = path.join(skillsDir, name);
    let body;
    try {
      body = await readFile(path.join(skillDir, "SKILL.md"), "utf8");
    } catch (error) {
      if (error.code === "ENOENT") continue;
      throw error;
    }

    const references = {};
    for (const relativePath of await filesRecursively(path.join(skillDir, "references"))) {
      if (!textExtensions.has(path.extname(relativePath).toLowerCase())) continue;
      references[relativePath] = await readFile(path.join(skillDir, "references", relativePath), "utf8");
    }

    skills.push({
      name,
      plugin,
      description: frontmatterValue(body, "description") ?? firstBodyLine(body),
      body,
      references,
      script_files: await filesRecursively(path.join(skillDir, "scripts")),
    });
  }
}

skills.sort((a, b) => a.name.localeCompare(b.name) || a.plugin.localeCompare(b.plugin));
await mkdir(path.dirname(outputFile), { recursive: true });
await writeFile(outputFile, `${JSON.stringify(skills, null, 2)}\n`, "utf8");
console.log(`Built ${skills.length} skills into ${path.relative(repositoryDir, outputFile)}`);

