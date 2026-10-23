// embed-chunks v1 (as deployed until 2026-10-23, backed up by Claude before the v2 redeploy).
// Failed with HTTP 546 WORKER_RESOURCE_LIMIT: the 45 s loop of in-runtime gte-small inference
// exceeds the edge worker's per-request CPU budget.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
const model = new Supabase.ai.Session("gte-small");
const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
const TIME_BUDGET_MS = 45_000;
Deno.serve(async (req: Request) => {
  const started = Date.now();
  let batchSize = 100;
  try { const body = await req.json().catch(() => ({})); if (typeof body.batch_size === "number") batchSize = body.batch_size; } catch { /* */ }
  let embedded = 0; let failed = 0;
  while (Date.now() - started < TIME_BUDGET_MS) {
    const { data: rows, error } = await supabase.from("brain_chunks").select("id, content").is("embedding", null).limit(batchSize);
    if (error) return Response.json({ ok: false, stage: "select", error: error.message }, { status: 500 });
    if (!rows || rows.length === 0) break;
    for (const row of rows) {
      try {
        const embedding = await model.run(row.content, { mean_pool: true, normalize: true }) as number[];
        const { error: upErr } = await supabase.from("brain_chunks").update({ embedding }).eq("id", row.id);
        if (upErr) failed++; else embedded++;
      } catch { failed++; }
      if (Date.now() - started >= TIME_BUDGET_MS) break;
    }
  }
  const { count: remaining } = await supabase.from("brain_chunks").select("id", { count: "exact", head: true }).is("embedding", null);
  return Response.json({ ok: true, embedded, failed, remaining: remaining ?? null, elapsed_ms: Date.now() - started });
});
