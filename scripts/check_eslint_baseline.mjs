// ESLint gate for the RigHaven frontend overlays: fail only on errors beyond the baseline.
// Usage (from the Next.js app folder): node check_eslint_baseline.mjs <baseline.json> [--write]
// The baseline maps each overlay path (relative to the app) to {rule: error count}.
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { relative, resolve } from "node:path";

const [baselinePath, mode] = process.argv.slice(2);
const baseline = JSON.parse(readFileSync(baselinePath, "utf8"));
const files = Object.keys(baseline.files);
let output;
try {
  output = execFileSync("npx", ["eslint", "--no-warn-ignored", "-f", "json", ...files], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
} catch (error) {
  // ESLint exits 1 when it reports errors; the JSON report is still on stdout.
  if (!error.stdout) throw error;
  output = error.stdout;
}
const current = Object.fromEntries(files.map((file) => [file, {}]));
for (const result of JSON.parse(output)) {
  const file = relative(process.cwd(), resolve(result.filePath));
  for (const message of result.messages) {
    if (message.severity !== 2) continue;
    const rule = message.ruleId ?? "parse";
    current[file][rule] = (current[file][rule] ?? 0) + 1;
  }
}
if (mode === "--write") {
  writeFileSync(baselinePath, JSON.stringify({ ...baseline, files: current }, null, 1) + "\n");
  console.log("ESLint baseline written for", files.length, "files");
  process.exit(0);
}
const regressions = [];
const improvements = [];
for (const file of files) {
  const rules = new Set([...Object.keys(current[file]), ...Object.keys(baseline.files[file])]);
  for (const rule of rules) {
    const now = current[file][rule] ?? 0;
    const before = baseline.files[file][rule] ?? 0;
    if (now > before) regressions.push(`${file}: ${rule} ${before} -> ${now}`);
    else if (now < before) improvements.push(`${file}: ${rule} ${before} -> ${now}`);
  }
}
if (improvements.length) console.log("ESLint errors below the baseline (lower it with --write):\n" + improvements.join("\n"));
if (regressions.length) {
  console.error("New ESLint errors in RigHaven overlays:\n" + regressions.join("\n"));
  process.exit(1);
}
console.log("ESLint baseline OK:", files.length, "overlay files, no new errors");
