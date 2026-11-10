// Starts the daily-predictions GitHub Actions workflow at an exact minute.
// Only the cron trigger starts a run. The HTTP handler never does.

export function buildRequest(env) {
  return {
    url: `https://api.github.com/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`,
    init: {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "daily-trigger-worker",
        "Content-Type": "application/json",
      },
      // No "inputs": injury_refresh keeps its default (false), so the run is a full run.
      body: JSON.stringify({ ref: env.REF }),
    },
  };
}

export async function dispatch(env, fetchImpl = fetch) {
  const { url, init } = buildRequest(env);
  const res = await fetchImpl(url, init);
  // GitHub answers 204 No Content on success.
  if (res.status !== 204) {
    const text = await res.text();
    throw new Error(`GitHub workflow dispatch failed with status ${res.status}: ${text}`);
  }
}

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(dispatch(env));
  },
  async fetch() {
    return new Response("Not found", { status: 404 });
  },
};
