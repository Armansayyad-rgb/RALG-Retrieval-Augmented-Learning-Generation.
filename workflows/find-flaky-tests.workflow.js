export const meta = {
  name: "find-flaky-tests",
  description: "Find flaky tests and propose fixes",
  phases: [
    { title: "Scan", detail: "inspect CI logs for retries and flaky markers" },
    { title: "Fix", detail: "propose an actionable isolation or retry fix" },
  ],
};

const FLAKY_SCHEMA = {
  type: "object",
  properties: {
    filename: { type: "string" },
    line: { type: "integer", minimum: 1 },
    retryCount: { type: "integer", minimum: 1 },
    failurePattern: { type: "array", items: { type: "string" } },
    testName: { type: "string" },
  },
  required: ["filename", "line"],
};

const scans = await parallel([
  agent("Scan CI logs for retry markers and return filenames and line numbers", {
    schema: FLAKY_SCHEMA, phase: "Scan",
  }),
  agent("Find tests marked unstable or flaky in CI logs", {
    schema: FLAKY_SCHEMA, phase: "Scan",
  }),
]);

const candidates = scans.filter((item) => item && item.filename && item.line);
phase("Fix");
const fixes = await parallel(candidates.map((item) => agent(
  `Propose a concrete isolation or retry fix for ${item.filename}:${item.line}`,
  { schema: FLAKY_SCHEMA, phase: "Fix" },
)));

return { scans: candidates, fixes };
