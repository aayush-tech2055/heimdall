"use client";

import { AlertTriangle, Loader2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { RoleGate } from "@/components/auth/role-gate";
import { PageHeader } from "@/components/shell/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { FilterTabs } from "@/components/ui/filter-tabs";
import { api, ApiError } from "@/lib/api";
import type { Me } from "@/types/api";

// Data-viz tokens (reference palette, light surface): one hue for single-series magnitude.
const SERIES = "#2a78d6";
const GRID = "#e6e5e1";
const AXIS = "#52514e";

type Insights = {
  days: number;
  contents: number;
  flags: number;
  open_flags: number;
  dismissal_rate: number | null;
  avg_hours_to_approval: number | null;
  approved: number;
  sent_back: number;
  submissions: number;
  send_back_rate: number | null;
  by_week: { week: string; flags: number; high: number }[];
  by_category: { key: string; count: number }[];
  by_severity: { key: string; count: number }[];
  top_rules: {
    rule_code: string;
    text: string | null;
    category: string | null;
    flags: number;
    open: number;
    dismissed: number;
  }[];
  by_creator: { creator: string; items: number; flags: number; high: number }[];
};

type Health = {
  source_id: string;
  text: string | null;
  category: string | null;
  flags: number;
  dismissed: number;
  dismissal_rate: number;
  probably_unclear: boolean;
  top_reasons: string[];
};

const pct = (v: number | null) =>
  v === null ? "–" : `${Math.round(v * 100)}%`;

function Stat({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-muted-foreground text-sm">{label}</p>
        <p className="text-3xl font-semibold tabular-nums">{value}</p>
        {note && <p className="text-muted-foreground mt-1 text-xs">{note}</p>}
      </CardContent>
    </Card>
  );
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-popover text-popover-foreground rounded-md border px-2 py-1 text-sm shadow">
      <p className="font-medium">{label}</p>
      <p>{payload[0].value} flags</p>
    </div>
  );
}

function Dashboard({ me }: { me: Me }) {
  const [days, setDays] = useState("90");
  const [data, setData] = useState<Insights | null>(null);
  const [health, setHealth] = useState<Health[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    Promise.all([
      api<Insights>(`/brands/${me.brand_id}/insights`, { query: { days } }),
      api<Health[]>(`/brands/${me.brand_id}/guideline-health`),
    ])
      .then(([i, h]) => {
        setData(i);
        setHealth(h);
      })
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Could not load insights"),
      );
  }, [me.brand_id, days]);

  const unclear = (health ?? []).filter((h) => h.probably_unclear);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader
          title="Insights"
          description={`How ${me.brand_name}'s content and guidelines are doing.`}
        />
        <FilterTabs
          label="Time range"
          value={days}
          onChange={setDays}
          options={[
            { value: "30", label: "30 days" },
            { value: "90", label: "90 days" },
            { value: "365", label: "1 year" },
          ]}
        />
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!data ? (
        <p
          className="text-muted-foreground flex items-center gap-2"
          role="status"
        >
          <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
        </p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label="Flags raised"
              value={String(data.flags)}
              note={`${data.open_flags} still open · ${data.contents} items checked`}
            />
            <Stat
              label="Average time to approval"
              value={
                data.avg_hours_to_approval === null
                  ? "–"
                  : `${data.avg_hours_to_approval.toFixed(1)} h`
              }
              note={`${data.approved} approved`}
            />
            <Stat
              label="Sent back"
              value={pct(data.send_back_rate)}
              note={`${data.sent_back} of ${data.submissions} submissions`}
            />
            <Stat
              label="Flags dismissed"
              value={pct(data.dismissal_rate)}
              note="of resolved flags"
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>
                  <h2>Flags per week</h2>
                </CardTitle>
                <CardDescription>
                  On each item&apos;s latest version.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {data.by_week.length === 0 ? (
                  <p className="text-muted-foreground text-sm">
                    No flags in this period.
                  </p>
                ) : (
                  <>
                    <div className="h-56" aria-hidden>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart
                          data={data.by_week}
                          margin={{ top: 8, right: 16, bottom: 0, left: -16 }}
                        >
                          <CartesianGrid stroke={GRID} vertical={false} />
                          <XAxis
                            dataKey="week"
                            tick={{ fill: AXIS, fontSize: 12 }}
                            tickLine={false}
                            axisLine={{ stroke: GRID }}
                          />
                          <YAxis
                            allowDecimals={false}
                            tick={{ fill: AXIS, fontSize: 12 }}
                            tickLine={false}
                            axisLine={false}
                          />
                          <Tooltip
                            content={<ChartTooltip />}
                            cursor={{ stroke: AXIS, strokeDasharray: "3 3" }}
                          />
                          <Line
                            type="monotone"
                            dataKey="flags"
                            stroke={SERIES}
                            strokeWidth={2}
                            dot={{
                              r: 4,
                              fill: SERIES,
                              strokeWidth: 2,
                              stroke: "#fff",
                            }}
                            activeDot={{ r: 5 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    <details className="mt-2 text-sm">
                      <summary className="cursor-pointer">Table view</summary>
                      <ul className="mt-1">
                        {data.by_week.map((w) => (
                          <li key={w.week}>
                            Week of {w.week}: {w.flags} flags ({w.high} high)
                          </li>
                        ))}
                      </ul>
                    </details>
                  </>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>
                  <h2>Flags by category</h2>
                </CardTitle>
                <CardDescription>
                  By severity:{" "}
                  {data.by_severity
                    .map((s) => `${s.count} ${s.key}`)
                    .join(" · ") || "none"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {data.by_category.length === 0 ? (
                  <p className="text-muted-foreground text-sm">
                    No flags in this period.
                  </p>
                ) : (
                  <>
                    <div className="h-56" aria-hidden>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={data.by_category}
                          layout="vertical"
                          margin={{ top: 0, right: 24, bottom: 0, left: 24 }}
                          barCategoryGap={6}
                        >
                          <CartesianGrid stroke={GRID} horizontal={false} />
                          <XAxis
                            type="number"
                            allowDecimals={false}
                            tick={{ fill: AXIS, fontSize: 12 }}
                            tickLine={false}
                            axisLine={false}
                          />
                          <YAxis
                            type="category"
                            dataKey="key"
                            tick={{ fill: AXIS, fontSize: 12 }}
                            tickLine={false}
                            axisLine={false}
                            width={90}
                          />
                          <Tooltip
                            content={<ChartTooltip />}
                            cursor={{ fill: GRID, opacity: 0.5 }}
                          />
                          <Bar
                            dataKey="count"
                            fill={SERIES}
                            radius={[0, 4, 4, 0]}
                            maxBarSize={22}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <details className="mt-2 text-sm">
                      <summary className="cursor-pointer">Table view</summary>
                      <ul className="mt-1">
                        {data.by_category.map((c) => (
                          <li key={c.key}>
                            {c.key}: {c.count}
                          </li>
                        ))}
                      </ul>
                    </details>
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          <section aria-labelledby="health-h" className="space-y-3">
            <h2 id="health-h" className="text-xl font-semibold">
              Guideline health
            </h2>
            <p className="text-muted-foreground text-sm">
              A rule dismissed in at least 40% of cases (with 5 or more flags)
              is probably unclear: rewrite it or retire it.
            </p>
            {unclear.length > 0 && (
              <Alert>
                <AlertTriangle className="size-4" aria-hidden />
                <AlertDescription>
                  {unclear.length} rule
                  {unclear.length === 1 ? " looks" : "s look"} unclear:{" "}
                  {unclear.map((u) => u.source_id).join(", ")}.
                </AlertDescription>
              </Alert>
            )}
            {!health?.length ? (
              <p className="text-muted-foreground">No flags yet.</p>
            ) : (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Rule</TableHead>
                      <TableHead>Flags</TableHead>
                      <TableHead>Dismissed</TableHead>
                      <TableHead>Common reasons</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {health.map((h) => (
                      <TableRow key={h.source_id}>
                        <TableCell className="max-w-sm whitespace-normal">
                          {me.role === "admin" &&
                          h.source_id.startsWith("R-") ? (
                            <Link
                              href={`/admin/guidelines#rule-${h.source_id}`}
                              className="font-mono font-medium underline underline-offset-2"
                            >
                              {h.source_id}
                            </Link>
                          ) : (
                            <span className="font-mono font-medium">
                              {h.source_id}
                            </span>
                          )}{" "}
                          {h.probably_unclear && (
                            <Badge
                              className="border-amber-300 bg-amber-100 text-amber-900"
                              variant="outline"
                            >
                              probably unclear
                            </Badge>
                          )}
                          <p className="text-muted-foreground text-sm">
                            {h.text ??
                              (h.source_id.startsWith("SYS-")
                                ? "Built-in claim policy"
                                : "")}
                          </p>
                        </TableCell>
                        <TableCell className="tabular-nums">
                          {h.flags}
                        </TableCell>
                        <TableCell className="tabular-nums">
                          {h.dismissed} ({pct(h.dismissal_rate)})
                        </TableCell>
                        <TableCell className="text-sm whitespace-normal">
                          {h.top_reasons.join(" · ") || "–"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section aria-labelledby="top-h" className="space-y-3">
              <h2 id="top-h" className="text-xl font-semibold">
                Most broken rules
              </h2>
              {data.top_rules.length === 0 ? (
                <p className="text-muted-foreground">None yet.</p>
              ) : (
                <ol className="space-y-2">
                  {data.top_rules.map((r) => (
                    <li
                      key={r.rule_code}
                      className="rounded-md border p-2 text-sm"
                    >
                      <span className="font-mono font-medium">
                        {r.rule_code}
                      </span>{" "}
                      · {r.flags} flags ({r.open} open, {r.dismissed} dismissed)
                      <p className="text-muted-foreground">{r.text}</p>
                    </li>
                  ))}
                </ol>
              )}
            </section>
            <section aria-labelledby="creators-h" className="space-y-3">
              <h2 id="creators-h" className="text-xl font-semibold">
                By creator
              </h2>
              {data.by_creator.length === 0 ? (
                <p className="text-muted-foreground">None yet.</p>
              ) : (
                <div className="rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Creator</TableHead>
                        <TableHead>Items</TableHead>
                        <TableHead>Flags</TableHead>
                        <TableHead>High</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.by_creator.map((c) => (
                        <TableRow key={c.creator}>
                          <TableCell>{c.creator}</TableCell>
                          <TableCell className="tabular-nums">
                            {c.items}
                          </TableCell>
                          <TableCell className="tabular-nums">
                            {c.flags}
                          </TableCell>
                          <TableCell className="tabular-nums">
                            {c.high}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}

export default function InsightsPage() {
  return (
    <RoleGate roles={["admin", "manager"]}>
      {(me) => <Dashboard me={me} />}
    </RoleGate>
  );
}
