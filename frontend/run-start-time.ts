type TimedRun = {
  run_id: string;
  thread_id: string;
  status: string;
  created_at: string;
};

/** Use the persisted run clock, including when this tab did not create it. */
export function getRunStartTime(
  runs: readonly TimedRun[] | undefined,
  submittedRunId: string | null,
  threadId: string | null | undefined,
  now = Date.now(),
): number | null {
  const run = runs?.find((candidate) =>
    candidate.thread_id === threadId &&
    (candidate.status === "pending" || candidate.status === "running") &&
    (submittedRunId !== null
      ? candidate.run_id === submittedRunId
      : true),
  );
  if (!run?.created_at) return null;
  const start = Date.parse(run.created_at);
  return Number.isFinite(start) && start <= now ? start : null;
}
