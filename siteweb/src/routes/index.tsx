/**
 * src/routes/index.tsx
 */
import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as XLSX from "xlsx";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart, // Kept per your imports, though AreaChart is primarily used
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload,
  FileSpreadsheet,
  Play,
  Pause,
  RotateCcw,
  CheckCircle2,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Activity,
} from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "HDJ Agent — Optimisation capacitaire des hôpitaux de jour" },
      {
        name: "description",
        content:
          "Système multi-agents de simulation et d'aide à la décision pour la création et l'optimisation des hôpitaux de jour au CHU de Guyane.",
      },
      { property: "og:title", content: "HDJ Agent — Simulateur multi-agents" },
      {
        property: "og:description",
        content:
          "Importez vos données PMSI/CCAM, simulez plusieurs scénarios et visualisez l'impact médico-économique en temps réel.",
      },
    ],
  }),
  component: HDJAgentApp,
});

// ---------- Types ----------

type Scenario = "statu-quo" | "optimisation" | "creation-hdj";

type ScenarioConfig = {
  id: Scenario;
  label: string;
  description: string;
  waitFactor: number; // multiplier on baseline wait
  satFactor: number;
  convertibleFactor: number;
  revenueFactor: number; // €k
  color: string;
};

const SCENARIOS: ScenarioConfig[] = [
  {
    id: "statu-quo",
    label: "Statu Quo (Actuel)",
    description: "Parcours fragmenté en consultations isolées",
    waitFactor: 1.0,
    satFactor: 0.62,
    convertibleFactor: 0,
    revenueFactor: 0,
    color: "#0284c7",
  },
  {
    id: "optimisation",
    label: "Optimisation Capacitaire",
    description: "Lissage des flux + ordonnanceur agent",
    waitFactor: 0.58,
    satFactor: 0.84,
    convertibleFactor: 1240,
    revenueFactor: 740,
    color: "#10b981",
  },
  {
    id: "creation-hdj",
    label: "+ Création HDJ Dédié",
    description: "Nouvelle unité HDJ multi-spécialités",
    waitFactor: 0.42,
    satFactor: 0.78,
    convertibleFactor: 2120,
    revenueFactor: 1340,
    color: "#f59e0b",
  },
];

type AgentDecision = {
  id: number;
  agent: "Triage" | "Ordonnanceur" | "Évaluateur" | "Patient";
  message: string;
  tone: "info" | "success" | "warn";
};

type FluxPoint = {
  t: string;
  consultations: number;
  hdj: number;
  attente: number;
};

type ParsedFile = {
  name: string;
  rows: number;
  sheets: string[];
  specialties: { name: string; volume: number }[];
};

// ---------- Helpers ----------

function makeFluxPoint(tick: number, scenario: ScenarioConfig): FluxPoint {
  const hour = 8 + Math.floor((tick * 10) / 60);
  const minute = (tick * 10) % 60;
  const baseConsult = 45 + Math.sin(tick / 3) * 18 + Math.random() * 8;
  const baseHdj = 28 + Math.cos(tick / 4) * 14 + Math.random() * 6;
  const baseAttente = 38 + Math.sin(tick / 2.5) * 22 + Math.random() * 10;
  return {
    t: `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`,
    consultations: Math.max(0, Math.round(baseConsult * scenario.waitFactor)),
    hdj: Math.max(0, Math.round(baseHdj * (2 - scenario.waitFactor))),
    attente: Math.max(0, Math.round(baseAttente * scenario.waitFactor)),
  };
}

const DECISION_TEMPLATES: Omit<AgentDecision, "id">[] = [
  { agent: "Triage", message: "Patient ID-{n} réorienté vers HDJ Gastro (Gain attente: {g}min)", tone: "info" },
  { agent: "Ordonnanceur", message: "Lissage capacitaire effectué sur Salle 0{r}. Occupation stabilisée à {s}%.", tone: "success" },
  { agent: "Évaluateur", message: "Seuil de rentabilité atteint pour la création d'une unité HDJ {sp}.", tone: "warn" },
  { agent: "Patient", message: "Parcours #{n} optimisé — consolidation de {a} actes en une journée.", tone: "success" },
  { agent: "Triage", message: "Cohorte {sp} regroupable: {a} patients identifiés pour HDJ.", tone: "info" },
  { agent: "Ordonnanceur", message: "Replanification dynamique — {a} créneaux libérés en après-midi.", tone: "success" },
];

function makeDecision(id: number): AgentDecision {
  const tpl = DECISION_TEMPLATES[id % DECISION_TEMPLATES.length];
  const specialties = ["Onco", "Cardio", "Gastro", "Endocrino", "Pneumo"];
  return {
    id,
    agent: tpl.agent,
    tone: tpl.tone,
    message: tpl.message
      .replace("{n}", String(100 + ((id * 37) % 900)))
      .replace("{g}", String(8 + ((id * 3) % 22)))
      .replace("{r}", String(1 + (id % 8)))
      .replace("{s}", String(78 + (id % 15)))
      .replace("{a}", String(2 + (id % 6)))
      .replace("{sp}", specialties[id % specialties.length]),
  };
}

// ---------- Main Component ----------

function HDJAgentApp() {
  const [file, setFile] = useState<ParsedFile | null>(null);
  const [scenario, setScenario] = useState<Scenario>("optimisation");
  const [agentsOn, setAgentsOn] = useState({ triage: true, optimisation: true, memoire: false });
  const [running, setRunning] = useState(false);
  const [tick, setTick] = useState(0);
  const [flux, setFlux] = useState<FluxPoint[]>([]);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const activeScenario = useMemo(
    () => SCENARIOS.find((s) => s.id === scenario)!,
    [scenario],
  );

  // Seed initial chart
  useEffect(() => {
    const seed: FluxPoint[] = [];
    for (let i = 0; i < 18; i++) seed.push(makeFluxPoint(i, activeScenario));
    setFlux(seed);
    setTick(18);
    const seedDecisions = Array.from({ length: 4 }).map((_, i) => makeDecision(i));
    setDecisions(seedDecisions);
  }, [activeScenario]);

  // Simulation loop
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => {
      setTick((t) => {
        const next = t + 1;
        setFlux((prev) => [...prev.slice(-29), makeFluxPoint(next, activeScenario)]);
        if (next % 2 === 0) {
          setDecisions((prev) => [makeDecision(next), ...prev].slice(0, 14));
        }
        return next;
      });
    }, 900);
    return () => clearInterval(id);
  }, [running, activeScenario]);

  const handleFile = useCallback(async (f: File) => {
    const buf = await f.arrayBuffer();
    const wb = XLSX.read(buf, { type: "array" });
    const first = wb.SheetNames[0];
    const sheet = wb.Sheets[first];
    const rows: Record<string, unknown>[] = XLSX.utils.sheet_to_json(sheet, { defval: null });

    // Try to detect a specialty / service column
    const sample = rows[0] ?? {};
    const keys = Object.keys(sample);
    const specKey =
      keys.find((k) => /spéc|specialit|service|unité|unite/i.test(k)) ?? keys[0];

    const counts = new Map<string, number>();
    for (const r of rows) {
      const v = String((r as Record<string, unknown>)[specKey] ?? "—").trim() || "—";
      counts.set(v, (counts.get(v) ?? 0) + 1);
    }
    const specialties = [...counts.entries()]
      .map(([name, volume]) => ({ name: name.slice(0, 18), volume }))
      .sort((a, b) => b.volume - a.volume)
      .slice(0, 8);

    setFile({
      name: f.name,
      rows: rows.length,
      sheets: wb.SheetNames,
      specialties: specialties.length
        ? specialties
        : [
            { name: "Cardiologie", volume: 412 },
            { name: "Oncologie", volume: 388 },
            { name: "Endocrinologie", volume: 274 },
            { name: "Gastro-entéro.", volume: 231 },
            { name: "Pneumologie", volume: 186 },
            { name: "Néphrologie", volume: 142 },
          ],
    });
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const f = e.dataTransfer.files?.[0];
      if (f) void handleFile(f);
    },
    [handleFile],
  );

  // KPIs
  const baselineWait = 52;
  const kpis = useMemo(() => {
    const wait = Math.round(baselineWait * activeScenario.waitFactor);
    const waitDelta = Math.round(((wait - baselineWait) / baselineWait) * 100);
    return {
      wait,
      waitDelta,
      sat: Math.round(activeScenario.satFactor * 1000) / 10,
      convertible: activeScenario.convertibleFactor,
      revenue: activeScenario.revenueFactor,
    };
  }, [activeScenario]);

  // Scenario comparison data
  const comparisonData = useMemo(
    () =>
      SCENARIOS.map((s) => ({
        name: s.label.replace(/\(.*\)/, "").trim(),
        attente: Math.round(baselineWait * s.waitFactor),
        occupation: Math.round(s.satFactor * 100),
        revenus: s.revenueFactor,
        color: s.color,
      })),
    [],
  );

  const reset = () => {
    setRunning(false);
    setTick(0);
    setFlux([]);
    setDecisions([]);
    // re-seed
    const seed: FluxPoint[] = [];
    for (let i = 0; i < 18; i++) seed.push(makeFluxPoint(i, activeScenario));
    setFlux(seed);
    setTick(18);
  };

  return (
    <div
      className="flex min-h-screen items-center justify-center"
      style={{ backgroundColor: "#fcfbf8" }}
    >
      <div className="flex h-screen w-full overflow-hidden bg-med-surface font-sans text-med-primary">
        {/* ============ SIDEBAR ============ */}
        <aside className="hidden w-72 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
          <div className="border-b border-slate-100 p-6">
            <div className="flex items-center gap-2">
              <div className="grid size-7 place-items-center rounded-md bg-med-accent">
                <Activity className="size-4 text-white" strokeWidth={2.5} />
              </div>
              <h1 className="text-lg font-bold uppercase tracking-tight text-med-accent">
                HDJ Agent
              </h1>
            </div>
            <p className="mt-2 text-[11px] font-medium text-slate-400">
              CHU DE GUYANE • SYSTÈME MULTI-AGENTS
            </p>
          </div>

          <div className="flex-1 space-y-8 overflow-y-auto p-6">
            {/* Upload */}
            <div>
              <label className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Importation Données
              </label>
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={onDrop}
                onClick={() => fileInputRef.current?.click()}
                className="group mt-3 cursor-pointer rounded-xl border-2 border-dashed border-slate-200 p-4 text-center transition-colors hover:border-med-accent hover:bg-med-accent-soft/40"
              >
                {file ? (
                  <div className="flex flex-col items-center gap-1">
                    <FileSpreadsheet className="size-5 text-med-success" />
                    <div className="truncate text-xs font-semibold text-med-primary" title={file.name}>
                      {file.name}
                    </div>
                    <div className="text-[10px] text-slate-400">
                      {file.rows.toLocaleString("fr-FR")} parcours • {file.sheets.length} feuille(s)
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-1">
                    <Upload className="size-5 text-slate-400 group-hover:text-med-accent" />
                    <div className="text-xs text-slate-500">Glissez votre fichier XLSX</div>
                    <div className="text-[10px] text-slate-400">PMSI, CCAM, Consultations</div>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xlsx,.xls"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void handleFile(f);
                  }}
                />
              </div>
            </div>

            {/* Agent toggles */}
            <div className="space-y-3">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Configuration Agents
              </label>
              {(
                [
                  ["triage", "Agent Triage"],
                  ["optimisation", "Optimisation IA"],
                  ["memoire", "Mémoire / Apprentissage"],
                ] as const
              ).map(([k, label]) => (
                <button
                  key={k}
                  onClick={() => setAgentsOn((s) => ({ ...s, [k]: !s[k] }))}
                  className="flex w-full items-center justify-between"
                >
                  <span
                    className={`text-sm ${
                      agentsOn[k] ? "text-med-primary" : "text-slate-400"
                    }`}
                  >
                    {label}
                  </span>
                  <span
                    className={`relative h-4 w-8 rounded-full transition-colors ${
                      agentsOn[k] ? "bg-med-accent" : "bg-slate-200"
                    }`}
                  >
                    <span
                      className={`absolute top-1 size-2 rounded-full bg-white transition-all ${
                        agentsOn[k] ? "right-1" : "left-1"
                      }`}
                    />
                  </span>
                </button>
              ))}
            </div>

            {/* Scenarios */}
            <div className="space-y-1">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Scénarios
              </label>
              {SCENARIOS.map((s) => {
                const active = scenario === s.id;
                const accent = s.id === "creation-hdj";
                return (
                  <button
                    key={s.id}
                    onClick={() => setScenario(s.id)}
                    className={`block w-full rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                      active
                        ? "bg-med-accent font-medium text-white shadow-sm"
                        : accent
                          ? "font-semibold text-med-success hover:bg-slate-50"
                          : "text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {accent && !active ? "+ " : ""}
                    {s.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2 border-t border-slate-100 p-6">
            <button
              onClick={() => setRunning((r) => !r)}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-med-primary py-3 text-sm font-bold tracking-wide text-white transition-all hover:bg-slate-800 active:scale-[0.98]"
            >
              {running ? (
                <>
                  <Pause className="size-4" /> PAUSE SIMULATION
                </>
              ) : (
                <>
                  <Play className="size-4" /> LANCER SIMULATION
                </>
              )}
            </button>
            <button
              onClick={reset}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 py-2 text-xs font-semibold text-slate-500 hover:bg-slate-50"
            >
              <RotateCcw className="size-3" /> Réinitialiser
            </button>
          </div>
        </aside>

        {/* ============ MAIN ============ */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">Tableau de Bord Décisionnel</h2>
              <p className="text-slate-500">
                Analyse des flux ambulatoires et trajectoires patients
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-bold uppercase ${
                  running
                    ? "border-med-success/20 bg-med-success/10 text-med-success"
                    : "border-slate-200 bg-slate-50 text-slate-500"
                }`}
              >
                <span
                  className={`size-1.5 rounded-full ${
                    running ? "animate-pulse bg-med-success" : "bg-slate-400"
                  }`}
                />
                {running ? "Simulation en cours" : "Système opérationnel"}
              </span>
            </div>
          </header>

          {/* KPIs */}
          <div className="mb-8 grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Attente Moyenne"
              value={`${kpis.wait} min`}
              delta={
                kpis.waitDelta < 0
                  ? { text: `${kpis.waitDelta}% vs Statu Quo`, tone: "good" }
                  : { text: "Référence", tone: "neutral" }
              }
              icon={<TrendingDown className="size-4" />}
            />
            <KpiCard
              label="Saturation HDJ"
              value={`${kpis.sat}%`}
              delta={
                kpis.sat > 85
                  ? { text: "Zone de vigilance", tone: "warn" }
                  : kpis.sat > 70
                    ? { text: "Optimum", tone: "good" }
                    : { text: "Sous-utilisation", tone: "warn" }
              }
              bar={kpis.sat}
            />
            <KpiCard
              label="Actes Convertibles"
              value={kpis.convertible ? kpis.convertible.toLocaleString("fr-FR") : "—"}
              delta={
                kpis.convertible
                  ? { text: "Potentiel de création", tone: "info" }
                  : { text: "Activité de référence", tone: "neutral" }
              }
              icon={<Sparkles className="size-4" />}
            />
            <KpiCard
              label="Impact Valorisation"
              value={kpis.revenue ? `+${kpis.revenue}k€` : "—"}
              delta={{ text: "Projection annuelle", tone: "info" }}
              highlight
              icon={<TrendingUp className="size-4" />}
            />
          </div>

          {/* Live flux + decisions */}
          <div className="mb-8 grid grid-cols-1 gap-6 xl:grid-cols-3">
            <div className="overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-sm xl:col-span-2">
              <div className="flex items-center justify-between border-b border-slate-50 p-4">
                <span className="text-xs font-bold uppercase tracking-widest text-slate-500">
                  Flux Dynamique des Agents Patients
                </span>
                <div className="flex items-center gap-2">
                  <div
                    className={`size-2 rounded-full ${
                      running ? "animate-pulse bg-med-accent" : "bg-slate-300"
                    }`}
                  />
                  <span className="text-[10px] uppercase tracking-wider text-slate-400">
                    {running ? "Live simulation" : "En attente"}
                  </span>
                </div>
              </div>
              <div className="h-[320px] w-full p-2">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={flux} margin={{ top: 16, right: 20, bottom: 8, left: 0 }}>
                    <defs>
                      <linearGradient id="gradConsult" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#0284c7" stopOpacity={0.4} />
                        <stop offset="100%" stopColor="#0284c7" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="gradHdj" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#10b981" stopOpacity={0.4} />
                        <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#f1f5f9" vertical={false} />
                    <XAxis
                      dataKey="t"
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={{ stroke: "#e2e8f0" }}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                      width={32}
                    />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 12,
                        border: "1px solid #e2e8f0",
                        fontSize: 12,
                      }}
                    />
                    <Legend
                      iconType="circle"
                      wrapperStyle={{ fontSize: 11, paddingTop: 4 }}
                    />
                    <Area
                      type="monotone"
                      dataKey="consultations"
                      name="Consultations"
                      stroke="#0284c7"
                      strokeWidth={2}
                      fill="url(#gradConsult)"
                      isAnimationActive={false}
                    />
                    <Area
                      type="monotone"
                      dataKey="hdj"
                      name="HDJ"
                      stroke="#10b981"
                      strokeWidth={2}
                      fill="url(#gradHdj)"
                      isAnimationActive={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="attente"
                      name="File d'attente"
                      stroke="#f59e0b"
                      strokeWidth={2}
                      dot={false}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Decisions feed */}
            <div className="flex flex-col rounded-2xl border border-slate-100 bg-white shadow-sm">
              <div className="border-b border-slate-50 p-4">
                <span className="text-xs font-bold uppercase tracking-widest text-slate-500">
                  Décisions Agents
                </span>
              </div>
              <div className="flex-1 space-y-3 overflow-y-auto p-4" style={{ maxHeight: 320 }}>
                <AnimatePresence initial={false}>
                  {decisions.map((d) => (
                    <motion.div
                      key={d.id}
                      layout
                      initial={{ opacity: 0, y: -6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      className="flex gap-3"
                    >
                      <div
                        className={`mt-1.5 size-2 shrink-0 rounded-full ${
                          d.tone === "success"
                            ? "bg-med-success"
                            : d.tone === "warn"
                              ? "bg-med-amber"
                              : "bg-med-accent"
                        }`}
                      />
                      <div>
                        <p className="text-xs font-semibold">Agent {d.agent}</p>
                        <p className="text-[11px] leading-relaxed text-slate-500">{d.message}</p>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
                {decisions.length === 0 && (
                  <p className="text-center text-[11px] text-slate-400">
                    Lancez la simulation pour observer les décisions des agents.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Bottom analysis */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-sm font-bold">Distribution des Actes par Spécialité</h3>
                {file && (
                  <span className="flex items-center gap-1 text-[10px] font-medium uppercase text-med-success">
                    <CheckCircle2 className="size-3" /> Source: {file.name}
                  </span>
                )}
              </div>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={
                      file?.specialties ?? [
                        { name: "Cardiologie", volume: 412 },
                        { name: "Oncologie", volume: 388 },
                        { name: "Endocrinologie", volume: 274 },
                        { name: "Gastro", volume: 231 },
                        { name: "Pneumologie", volume: 186 },
                        { name: "Néphrologie", volume: 142 },
                      ]
                    }
                    margin={{ top: 8, right: 8, left: -16, bottom: 0 }}
                  >
                    <CartesianGrid stroke="#f1f5f9" vertical={false} />
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={{ stroke: "#e2e8f0" }}
                      interval={0}
                      angle={-20}
                      textAnchor="end"
                      height={50}
                    />
                    <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }}
                    />
                    <Bar dataKey="volume" fill="#0284c7" radius={[6, 6, 0, 0]}>
                      {(file?.specialties ?? []).map((_, i) => (
                        <Cell
                          key={i}
                          fill={i === 0 ? "#0f172a" : i < 3 ? "#0284c7" : "#7dd3fc"}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
              <h3 className="mb-4 text-sm font-bold">Comparaison des Scénarios</h3>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comparisonData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                    <CartesianGrid stroke="#f1f5f9" vertical={false} />
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={{ stroke: "#e2e8f0" }}
                    />
                    <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }}
                    />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="attente" name="Attente (min)" fill="#f59e0b" radius={[6, 6, 0, 0]} />
                    <Bar dataKey="occupation" name="Occupation (%)" fill="#0284c7" radius={[6, 6, 0, 0]} />
                    <Bar dataKey="revenus" name="Revenus (k€)" fill="#10b981" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2">
                {comparisonData.map((s) => (
                  <div
                    key={s.name}
                    className={`rounded-lg border p-2 text-center ${
                      s.name.toLowerCase().includes(activeScenario.label.split(" ")[0].toLowerCase())
                        ? "border-med-accent bg-med-accent-soft"
                        : "border-slate-100"
                    }`}
                  >
                    <div className="truncate text-[10px] font-semibold uppercase text-slate-500">
                      {s.name}
                    </div>
                    <div className="text-sm font-bold text-med-primary">
                      {s.revenus ? `+${s.revenus}k€` : "—"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <footer className="mt-10 border-t border-slate-200 pt-4 text-center text-[10px] uppercase tracking-widest text-slate-400">
            HDJ Agent • Système multi-agents d'aide à la décision — CHU de Guyane
          </footer>
        </main>
      </div>
    </div>
  );
}

// ---------- KPI Card Component ----------

function KpiCard({
  label,
  value,
  delta,
  icon,
  bar,
  highlight,
}: {
  label: string;
  value: string;
  delta: { text: string; tone: "good" | "warn" | "info" | "neutral" };
  icon?: React.ReactNode;
  bar?: number;
  highlight?: boolean;
}) {
  const toneClass = {
    good: "text-med-success",
    warn: "text-med-amber",
    info: "text-med-accent",
    neutral: "text-slate-400",
  }[delta.tone];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm"
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="text-xs font-bold uppercase text-slate-400">{label}</div>
        {icon && <span className={toneClass}>{icon}</span>}
      </div>
      <div
        className={`text-3xl font-bold tracking-tight ${
          highlight ? "text-med-success" : "text-med-primary"
        }`}
      >
        {value}
      </div>
      {typeof bar === "number" && (
        <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-med-accent transition-all duration-500"
            style={{ width: `${Math.min(100, bar)}%` }}
          />
        </div>
      )}
      <div className={`mt-2 text-[11px] font-medium ${toneClass}`}>{delta.text}</div>
    </motion.div>
  );
}