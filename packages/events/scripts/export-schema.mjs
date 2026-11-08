import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { StreamEventSchema } from "../src/events.ts";

const args = process.argv.slice(2);
if (args.length > 1 || (args.length === 1 && args[0] !== "--check")) {
  throw new Error("Usage: export-schema.mjs [--check]");
}
const outputs = [
  new URL("../schema/stream-event.schema.json", import.meta.url),
  new URL("../../../apps/api/src/qvelt_api/schemas/stream-event.schema.json", import.meta.url),
];
const expected = JSON.stringify(StreamEventSchema, null, 2) + "\n";
for (const output of outputs) {
  if (args[0] === "--check") {
    let actual;
    try { actual = readFileSync(output, "utf8"); }
    catch (error) { if (error.code !== "ENOENT") throw error; }
    if (actual !== expected) {
      console.error(`Generated schema is stale: ${fileURLToPath(output)}`);
      process.exitCode = 1;
    }
  } else {
    mkdirSync(new URL(".", output), { recursive: true });
    writeFileSync(output, expected);
  }
}
