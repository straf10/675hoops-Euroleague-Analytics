import test from "node:test";
import assert from "node:assert/strict";
import worker, { buildRequest, dispatch } from "../src/index.js";

const TOKEN = "github_pat_TEST_SECRET_VALUE";
const env = {
  REPO: "straf10/675hoops-Euroleague-Analytics",
  WORKFLOW: "daily.yml",
  REF: "main",
  GITHUB_TOKEN: TOKEN,
};

test("buildRequest gives the exact dispatch request", () => {
  const { url, init } = buildRequest(env);
  assert.equal(
    url,
    "https://api.github.com/repos/straf10/675hoops-Euroleague-Analytics/actions/workflows/daily.yml/dispatches",
  );
  assert.equal(init.method, "POST");
  assert.deepEqual(init.headers, {
    Authorization: `Bearer ${TOKEN}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "daily-trigger-worker",
    "Content-Type": "application/json",
  });
  const body = JSON.parse(init.body);
  assert.deepEqual(body, { ref: "main" });
  assert.equal("inputs" in body, false);
});

test("dispatch resolves on status 204", async () => {
  const fakeFetch = async () => new Response(null, { status: 204 });
  await assert.doesNotReject(dispatch(env, fakeFetch));
});

for (const status of [401, 404]) {
  test(`dispatch rejects on status ${status} without leaking the token`, async () => {
    const fakeFetch = async () => new Response("Not Found", { status });
    await assert.rejects(dispatch(env, fakeFetch), (err) => {
      assert.ok(err instanceof Error);
      assert.ok(err.message.includes(String(status)));
      assert.ok(!err.message.includes(TOKEN));
      return true;
    });
  });
}

test("the HTTP handler returns 404 and starts nothing", async () => {
  const res = await worker.fetch();
  assert.equal(res.status, 404);
});
