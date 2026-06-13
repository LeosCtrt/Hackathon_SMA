import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import {
  Activity,
  Users,
  Hospital,
  Cpu,
  GitBranch,
  Layers,
  Sparkles,
  Database,
  Brain,
  Network,
  Calendar,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  ArrowUpRight,
  FileText,
  Workflow,
  Stethoscope,
  Building2,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  LineChart,
  Line,
  Area,
  AreaChart,
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
} from "recharts";
import heroFlow from "@/assets/hero-flow.jpg";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "HDJ Agent — Optimisation des hôpitaux de jour · CHU Guyane" },
      {
        name: "description",
        content:
          "Système multi-agents d'aide à la décision pour la création et l'optimisation des hôpitaux de jour. Simulation capacitaire, scénarios médico-économiques, priorisation des parcours.",
      },
    ],
  }),
  component: Showcase,
});

const sections = [
  { id: "apercu", label: "Aperçu", icon: Activity },
  { id: "agents", label: "Multi-agents", icon: Network },
  { id: "kpi", label: "Synthèse", icon: TrendingUp },
  { id: "scenarios", label: "Scénarios", icon: GitBranch },
  { id: "capacite", label: "Capacité", icon: Layers },
  { id: "priorisation", label: "Priorisation", icon: Sparkles },
  { id: "fragmentation", label: "Fragmentation", icon: Users },
  { id: "medeco", label: "Médico-éco", icon: TrendingUp },
  { id: "decision", label: "Décision", icon: FileText },
];

function Showcase() {
  const [active, setActive] = useState("apercu");
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <div className="mx-auto flex max-w-[1400px] gap-8 px-6 py-8 lg:px-10">
        <SideNav active={active} setActive={setActive} />
        <main className="min-w-0 flex-1 space-y-24 pb-32">
          <Hero />
          <Section id="agents" eyebrow="Architecture Mesa + NetworkX" title="Cinq agents, une chaîne décisionnelle">
            <Agents />
          </Section>
          <Section id="kpi" eyebrow="Synthèse exécutive" title="Chiffres clés de la simulation">
            <Kpis />
          </Section>
          <Section id="scenarios" eyebrow="Comparaison" title="Trois scénarios d'organisation">
            <Scenarios />
          </Section>
          <Section id="capacite" eyebrow="What-if" title="Simulateur de capacité HDJ">
            <Capacite />
          </Section>
          <Section
            id="priorisation"
            eyebrow="Score multicritère — volume (30%) · faisabilité (15%) · valeur stratégique (20%)"
            title="Parcours HDJ prioritaires"
          >
            <Priorisation />
          </Section>
          <Section id="fragmentation" eyebrow="Parcours patients" title="Fragmentation des venues">
            <Fragmentation />
          </Section>
          <Section id="medeco" eyebrow="Impact" title="Estimation médico-économique">
            <MedEco />
          </Section>
          <Section id="decision" eyebrow="Livrable" title="Note de décision hospitalière">
            <Decision />
          </Section>
          <Footer />
        </main>
      </div>
    </div>
  );
}

function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1400px] items-center justify-between px-6 py-4 lg:px-10">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-primary text-primary-foreground">
            <Hospital className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight">HDJ Agent</div>
            <div className="text-xs text-muted-foreground">CHU Guyane · Endocrino-Diabétologie</div>
          </div>
        </div>
        <nav className="hidden items-center gap-7 text-sm text-muted-foreground md:flex">
          <a href="#agents" className="hover:text-foreground">
            Agents
          </a>
          <a href="#scenarios" className="hover:text-foreground">
            Scénarios
          </a>
          <a href="#capacite" className="hover:text-foreground">
            Capacité
          </a>
          <a href="#decision" className="hover:text-foreground">
            Décision
          </a>
        </nav>
        <div className="flex items-center gap-2">
          <span className="hidden rounded-full bg-success/10 px-3 py-1 text-xs font-medium text-success md:inline">
            ● Prototype actif
          </span>
        </div>
      </div>
    </header>
  );
}

function SideNav({ active, setActive }: { active: string; setActive: (s: string) => void }) {
  return (
    <aside className="hidden w-56 shrink-0 lg:block">
      <div className="sticky top-24 space-y-1">
        <div className="px-3 pb-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Navigation
        </div>
        {sections.map((s) => {
          const Icon = s.icon;
          const isActive = active === s.id;
          return (
            <a
              key={s.id}
              href={`#${s.id}`}
              onClick={() => setActive(s.id)}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4" />
              {s.label}
            </a>
          );
        })}
        <div className="mt-6 rounded-xl border border-border bg-card p-4">
          <div className="text-xs font-semibold text-foreground">Source des données</div>
          <div className="mt-1 text-xs text-muted-foreground">
            TYPE_SEJOUR=EXT · 627 lignes · 369 IPP · couverture CCAM 39% · validation DIM/PMSI requise.
          </div>
        </div>
      </div>
    </aside>
  );
}

function Hero() {
  return (
    <section id="apercu" className="relative overflow-hidden rounded-3xl border border-border bg-card">
      <div className="grid gap-0 md:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6 p-10 lg:p-14">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-secondary px-3 py-1 text-xs">
            <Sparkles className="h-3 w-3 text-accent" />
            Défi 5 · Hôpitaux de jour · CHU Guyane
          </div>
          <h1 className="text-5xl leading-[1.02] lg:text-6xl">
            Le jumeau organisationnel
            <br />
            <em className="text-accent">des hôpitaux de jour.</em>
          </h1>
          <p className="max-w-xl text-base leading-relaxed text-muted-foreground">
            Cinq agents Mesa (Patient, Soignant, Environnement, Triage, Coordinateur) analysent 409 séjours réels
            2020–2026, détectent 94 patients récurrents, simulent 8 configurations capacitaires et produisent une note
            de décision actionnelle — pour aider la gouvernance à instruire la création des HDJ endocrino-diabéto.
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <a
              href="#scenarios"
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-medium text-primary-foreground transition hover:opacity-90"
            >
              Explorer les scénarios <ArrowUpRight className="h-4 w-4" />
            </a>
            <a
              href="#agents"
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-5 py-3 text-sm font-medium hover:bg-muted"
            >
              Architecture des agents
            </a>
          </div>
          <div className="grid grid-cols-3 gap-6 border-t border-border pt-6">
            <Stat value="369" label="Patients IPP" />
            <Stat value="5" label="Agents Mesa" />
            <Stat value="3" label="Scénarios comparés" />
          </div>
        </div>
        <div className="relative min-h-[320px] overflow-hidden bg-secondary md:min-h-full">
          <img
            src={heroFlow}
            alt="Flux des parcours patients"
            className="absolute inset-0 h-full w-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-l from-transparent via-transparent to-card/40" />
          <div className="absolute bottom-6 right-6 max-w-[240px] rounded-xl bg-card/95 p-4 shadow-lg backdrop-blur">
            <div className="text-xs font-medium text-muted-foreground">Gain réorganisation</div>
            <div className="mt-1 text-3xl font-semibold text-foreground">
              +28<span className="text-base text-muted-foreground"> séj.</span>
            </div>
            <div className="mt-1 text-xs text-success">▲ scénario B vs garde-fou PMSI</div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="text-3xl font-semibold tracking-tight">{value}</div>
      <div className="mt-1 text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

function Section({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24 space-y-6">
      <div className="flex items-end justify-between gap-6">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-accent">{eyebrow}</div>
          <h2 className="mt-2 text-4xl">{title}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}

// ── Agents ────────────────────────────────────────────────────────────────
const agents = [
  {
    icon: Users,
    name: "Agent Patient",
    desc: "Parcours physique simulé dans l'HDJ (salle → salle). États TRANSIT / ATTENTE_SOIN / SOIN / TERMINÉ. Mesure les temps de passage et les attentes réelles.",
    color: "bg-accent/10 text-accent",
  },
  {
    icon: Stethoscope,
    name: "Agent Soignant",
    desc: "IDE, endocrinologue, ophtalmologue, diététicienne — rôle et salle assignés depuis le YAML métier. Modélise la disponibilité soignante et les goulots humains.",
    color: "bg-primary/10 text-primary",
  },
  {
    icon: Building2,
    name: "Agent Environnement",
    desc: "Horaires, retards, indisponibilités, saturation — gestionnaire global du modèle Mesa. Jumeau des contraintes opérationnelles : ouverture/fermeture service, alertes capacitaires.",
    color: "bg-coral/10 text-coral",
  },
  {
    icon: GitBranch,
    name: "Agent Triage",
    desc: "Classe chaque séjour en 7 catégories décisionnelles (already_hdj, pmsi_guardrail, réorganisation_cible, récurrents, hors_périmètre…). Règles CCAM/CIM-10 centralisées dans le YAML métier.",
    color: "bg-success/10 text-success",
  },
  {
    icon: Workflow,
    name: "Coordinateur / Scheduler",
    desc: "Ordonnanceur greedy — planifie les scénarios A (5 séjours) et B (33 séjours) sur horizon paramétrable. Affecte fauteuil médicalisé et rétinographe, calcule les KPIs, détecte les saturations.",
    color: "bg-warning/15 text-warning-foreground",
  },
];

function Agents() {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {agents.map((a) => {
        const Icon = a.icon;
        return (
          <div
            key={a.name}
            className="group rounded-2xl border border-border bg-card p-6 transition hover:border-accent/40 hover:shadow-lg"
          >
            <div className={`mb-4 grid h-11 w-11 place-items-center rounded-lg ${a.color}`}>
              <Icon className="h-5 w-5" />
            </div>
            <div className="text-base font-semibold">{a.name}</div>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{a.desc}</p>
          </div>
        );
      })}
    </div>
  );
}

// ── KPIs ──────────────────────────────────────────────────────────────────
function Kpis() {
  const data = [
    { mois: "Jan", consult: 412, hdj: 38 },
    { mois: "Fév", consult: 398, hdj: 41 },
    { mois: "Mar", consult: 445, hdj: 52 },
    { mois: "Avr", consult: 430, hdj: 64 },
    { mois: "Mai", consult: 461, hdj: 73 },
    { mois: "Juin", consult: 422, hdj: 81 },
  ];
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
      <div className="grid grid-cols-2 gap-4">
        <Kpi label="Séjours analysés" value="409" trend="2020–2026" />
        <Kpi label="Patients pseudonymisés" value="369" trend="IPP uniques" />
        <Kpi label="Scénario prudent (A)" value="5" trend="garde-fou PMSI" />
        <Kpi label="Réorganisation (B)" value="33" trend="+28 séj. vs A" highlight />
      </div>
      <div className="rounded-2xl border border-border bg-card p-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold">Potentiel de conversion consultations → HDJ</div>
            <div className="text-xs text-muted-foreground">Projection illustrative — 409 séjours EXT analysés</div>
          </div>
          <div className="text-xs text-muted-foreground">▲ +560% scén. B vs A</div>
        </div>
        <div className="mt-6 h-56">
          <ResponsiveContainer>
            <AreaChart data={data}>
              <defs>
                <linearGradient id="g1" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="oklch(0.55 0.13 195)" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="oklch(0.55 0.13 195)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="mois" stroke="oklch(0.5 0.02 220)" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="oklch(0.5 0.02 220)" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{
                  background: "white",
                  border: "1px solid oklch(0.9 0.01 95)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Area
                type="monotone"
                dataKey="consult"
                stroke="oklch(0.32 0.06 210)"
                strokeWidth={2}
                fill="transparent"
              />
              <Area type="monotone" dataKey="hdj" stroke="oklch(0.55 0.13 195)" strokeWidth={2.5} fill="url(#g1)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function Kpi({
  label,
  value,
  trend,
  highlight,
}: {
  label: string;
  value: string;
  trend?: string;
  highlight?: boolean;
}) {
  return (
    <div className={`rounded-2xl border p-5 ${highlight ? "border-accent/50 bg-accent/5" : "border-border bg-card"}`}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-2 text-3xl font-semibold tracking-tight">{value}</div>
      {trend && <div className={`mt-1 text-xs ${highlight ? "text-accent" : "text-muted-foreground"}`}>{trend}</div>}
    </div>
  );
}

// ── Scénarios ─────────────────────────────────────────────────────────────
function Scenarios() {
  const scs = [
    {
      tag: "A",
      title: "Garde-fou PMSI",
      sej: 5,
      ret: 3,
      fau: 0,
      color: "border-border",
      desc: "Uniquement les séjours avec référence PMSI solide (already_hdj + convertibles). Démarrage sécurisé, risque réglementaire minimal.",
    },
    {
      tag: "B",
      title: "Réorganisation cible",
      sej: 33,
      ret: 3,
      fau: 10,
      color: "border-accent/60 bg-accent/5",
      desc: "Candidats high + medium potential après validation DIM/PMSI. +28 séjours structurés vs scénario A.",
      recommended: true,
    },
    {
      tag: "C",
      title: "Transformation ambulatoire",
      sej: 94,
      ret: 10,
      fau: 30,
      color: "border-border",
      desc: "Regroupement des 94 patients récurrents (352 venues fragmentées). Horizon 12–24 mois, protocoles HDJ dédiés à créer.",
    },
  ];
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {scs.map((s) => (
        <div key={s.tag} className={`relative rounded-2xl border-2 bg-card p-6 transition ${s.color}`}>
          {s.recommended && (
            <div className="absolute -top-3 left-6 rounded-full bg-accent px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-accent-foreground">
              Recommandé
            </div>
          )}
          <div className="flex items-baseline justify-between">
            <div className="font-display text-5xl text-foreground/80">{s.tag}</div>
            <div className="text-right">
              <div className="text-3xl font-semibold">{s.sej}</div>
              <div className="text-xs text-muted-foreground">séjours identifiés</div>
            </div>
          </div>
          <div className="mt-4 text-base font-semibold">{s.title}</div>
          <p className="mt-2 text-sm text-muted-foreground">{s.desc}</p>
          <div className="mt-5 space-y-3 border-t border-border pt-4">
            <OccBar label="Rétinographe" value={s.ret} />
            <OccBar label="Fauteuil méd." value={s.fau} />
          </div>
        </div>
      ))}
    </div>
  );
}

function OccBar({ label, value }: { label: string; value: number }) {
  const color = value > 85 ? "bg-coral" : value > 70 ? "bg-warning" : "bg-success";
  return (
    <div>
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{value}%</span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-secondary">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

// ── Capacité ──────────────────────────────────────────────────────────────
function Capacite() {
  // Données réelles — daily_schedule_example.json · Scénario B · 5 jours
  const data = [
    { jour: "J1", occ: 100 },
    { jour: "J2", occ: 92 },
    { jour: "J3", occ: 100 },
    { jour: "J4", occ: 75 },
    { jour: "J5", occ: 0 },
  ];
  const radial = [{ name: "Moy. B", value: 73, fill: "oklch(0.55 0.13 195)" }];
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="rounded-2xl border border-border bg-card p-6 lg:col-span-2">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold">Planning journalier simulé — Scénario B</div>
            <div className="text-xs text-muted-foreground">
              Occupation fauteuil médicalisé · 33 séjours sur 5 jours · ordonnancement greedy
            </div>
          </div>
          <div className="flex gap-4 text-xs">
            <Legend dot="bg-accent" label="Occupation" />
            <Legend dot="bg-coral" label="Saturation (≥90%)" />
          </div>
        </div>
        <div className="h-64">
          <ResponsiveContainer>
            <BarChart data={data}>
              <XAxis dataKey="jour" stroke="oklch(0.5 0.02 220)" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="oklch(0.5 0.02 220)" fontSize={11} tickLine={false} axisLine={false} domain={[0, 100]} />
              <Tooltip
                contentStyle={{
                  background: "white",
                  border: "1px solid oklch(0.9 0.01 95)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                cursor={{ fill: "oklch(0.96 0.008 95)" }}
              />
              <Bar dataKey="occ" radius={[6, 6, 0, 0]}>
                {data.map((d, i) => (
                  <rect key={i} fill={d.occ >= 90 ? "oklch(0.68 0.16 35)" : "oklch(0.55 0.13 195)"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="rounded-2xl border border-border bg-card p-6">
        <div className="text-sm font-semibold">Occupation moyenne fauteuil</div>
        <div className="text-xs text-muted-foreground">Scénario B · 5 jours · résultat simulateur</div>
        <div className="relative mx-auto mt-4 h-40 w-40">
          <ResponsiveContainer>
            <RadialBarChart innerRadius="70%" outerRadius="100%" data={radial} startAngle={90} endAngle={-270}>
              <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
              <RadialBar dataKey="value" cornerRadius={20} background={{ fill: "oklch(0.95 0.012 200)" }} />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 grid place-items-center">
            <div className="text-center">
              <div className="text-3xl font-semibold">73%</div>
              <div className="text-[10px] text-muted-foreground">Moy. scén. B</div>
            </div>
          </div>
        </div>
        <div className="mt-4 rounded-lg bg-warning/10 px-3 py-2 text-xs text-warning-foreground">
          <AlertTriangle className="mr-1 inline h-3 w-3" /> J1 et J3 à saturation — lisser sur 10 jours réduit à 37%
        </div>
      </div>
    </div>
  );
}

function Legend({ dot, label }: { dot: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      <span className="text-muted-foreground">{label}</span>
    </div>
  );
}

// ── Priorisation ──────────────────────────────────────────────────────────
function Priorisation() {
  const items = [
    {
      rank: 1,
      name: "Bilan annuel diabète",
      score: 68,
      vol: "12 séj.",
      faisa: "85%",
      tags: ["Faisabilité max", "Sans ressource critique"],
    },
    { rank: 2, name: "Bilan endocrino-métabolique", score: 58, vol: "9 séj.", faisa: "70%", tags: ["Multi-soignants"] },
    {
      rank: 3,
      name: "Séjours déjà HDJ (statu quo)",
      score: 54,
      vol: "4 séj.",
      faisa: "95%",
      tags: ["HDJ existant", "Consolidation"],
    },
    {
      rank: 4,
      name: "ETP diabète / obésité",
      score: 49,
      vol: "4 séj.",
      faisa: "75%",
      tags: ["IDE dédié", "Diététicienne"],
    },
  ];
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card">
      {items.map((it, i) => (
        <div
          key={it.rank}
          className={`flex items-center gap-6 p-5 ${i < items.length - 1 ? "border-b border-border" : ""}`}
        >
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-secondary font-display text-lg text-primary">
            {it.rank}
          </div>
          <div className="min-w-0 flex-1">
            <div className="font-medium">{it.name}</div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {it.tags.map((t) => (
                <span key={t} className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                  {t}
                </span>
              ))}
            </div>
          </div>
          <div className="hidden text-right md:block">
            <div className="text-xs text-muted-foreground">Volume</div>
            <div className="text-sm font-medium">{it.vol}</div>
          </div>
          <div className="hidden text-right md:block">
            <div className="text-xs text-muted-foreground">Faisabilité</div>
            <div className="text-sm font-medium">{it.faisa}</div>
          </div>
          <div className="w-32">
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Score</span>
              <span className="font-semibold">{it.score}</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-secondary">
              <div className="h-full rounded-full bg-accent" style={{ width: `${it.score}%` }} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Fragmentation ─────────────────────────────────────────────────────────
function Fragmentation() {
  const data = [
    { venues: "1", patients: 275 },
    { venues: "2-3", patients: 72 },
    { venues: "4-9", patients: 18 },
    { venues: "10-20", patients: 3 },
    { venues: "20+", patients: 1 },
  ];
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
      <div className="rounded-2xl border border-border bg-card p-6">
        <div className="text-sm font-semibold">Distribution des venues / patient</div>
        <div className="text-xs text-muted-foreground">369 IPP · 2020–2026</div>
        <div className="mt-4 h-56">
          <ResponsiveContainer>
            <BarChart data={data}>
              <XAxis dataKey="venues" stroke="oklch(0.5 0.02 220)" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="oklch(0.5 0.02 220)" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{
                  background: "white",
                  border: "1px solid oklch(0.9 0.01 95)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                cursor={{ fill: "oklch(0.96 0.008 95)" }}
              />
              <Bar dataKey="patients" fill="oklch(0.32 0.06 210)" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="space-y-3">
        <div className="rounded-2xl border border-border bg-card p-6">
          <div className="text-sm font-semibold">Segments de fragmentation — triage organisationnel</div>
          <div className="mt-4 space-y-3">
            {[
              {
                name: "1 venue — pas de fragmentation",
                pct: 75,
                color: "bg-primary",
                note: "275 patients — maintien en externe ou consultation ponctuelle",
              },
              {
                name: "2-3 venues — fragmentation légère",
                pct: 20,
                color: "bg-accent",
                note: "72 patients — éligibilité HDJ à évaluer au cas par cas",
              },
              {
                name: "4+ venues — fragmentation forte",
                pct: 6,
                color: "bg-coral",
                note: "22 patients — regroupement HDJ recommandé ou urgent",
              },
            ].map((s) => (
              <div key={s.name}>
                <div className="flex justify-between text-sm">
                  <span className="font-medium">{s.name}</span>
                  <span className="text-muted-foreground">{s.pct}%</span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-secondary">
                  <div className={`h-full ${s.color}`} style={{ width: `${s.pct}%` }} />
                </div>
                <div className="mt-1 text-xs text-muted-foreground">{s.note}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Médico-éco ────────────────────────────────────────────────────────────
function MedEco() {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {[
        {
          tag: "Prudent (A)",
          value: "3 000 €",
          desc: "Scénario A garde-fou PMSI — 5 journées HDJ structurées × 600 € forfait de référence. Facturation sécurisée, risque réglementaire minimal.",
          color: "border-border",
        },
        {
          tag: "Opérationnel (B)",
          value: "19 800 €",
          desc: "Scénario B après validation DIM/PMSI — 33 séjours × 600 €. +28 journées HDJ supplémentaires vs scénario A.",
          color: "border-accent/60 bg-accent/5",
          recommended: true,
        },
        {
          tag: "Transformation (C)",
          value: "À calculer",
          desc: "94 patients récurrents (352 venues fragmentées) — protocoles HDJ à définir avec le DIM avant tout chiffrage.",
          color: "border-border",
        },
      ].map((s) => (
        <div key={s.tag} className={`relative rounded-2xl border-2 bg-card p-6 ${s.color}`}>
          {s.recommended && (
            <div className="absolute -top-3 left-6 rounded-full bg-accent px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-accent-foreground">
              Référence
            </div>
          )}
          <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Estimation {s.tag}</div>
          <div className="mt-3 font-display text-4xl text-foreground">{s.value}</div>
          <div className="mt-1 text-xs text-muted-foreground">valorisation indicative · à valider DIM/PMSI</div>
          <p className="mt-4 text-sm text-muted-foreground">{s.desc}</p>
        </div>
      ))}
      <div className="md:col-span-3 flex items-start gap-3 rounded-xl bg-warning/10 p-4 text-sm">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-foreground" />
        <p className="text-warning-foreground">
          Estimations basées sur un forfait journalier HDJ de référence (600 €) à remplacer par le GHS réel validé par
          le DIM. Ces montants servent à prioriser l'instruction PMSI, pas à facturer. Données TYPE_SEJOUR=EXT —
          contexte CHU Guyane, déficit 75 M€.
        </p>
      </div>
    </div>
  );
}

// ── Décision ──────────────────────────────────────────────────────────────
function Decision() {
  return (
    <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
      <div className="rounded-2xl border border-border bg-card p-8">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-accent">
          <FileText className="h-3.5 w-3.5" /> Note de décision · 09 juin 2026
        </div>
        <h3 className="mt-3 text-3xl">
          Démarrer par un pilote HDJ <em>« Bilan annuel diabète »</em>
        </h3>
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
          Parcours prioritaire identifié dans les données (12 séjours, score multicritère 68/100), faisabilité
          opérationnelle maximale, validation DIM/PMSI réalisable en 4–6 semaines, aucun investissement équipement
          requis. Gain projeté : +28 séjours vs scénario garde-fou (A), 19 800 € de valorisation indicative
          opérationnelle.
        </p>
        <div className="mt-6 space-y-2">
          {[
            "Présenter ce tableau de bord au comité de direction médicale",
            "Mandater le DIM pour validation PMSI des cas candidats",
            "Constituer une équipe pilote IDE + endocrinologue + secrétariat",
            "Démarrage proposé : T+6 semaines après validation",
          ].map((step, i) => (
            <div key={i} className="flex items-start gap-3">
              <div className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-accent text-[10px] font-semibold text-accent-foreground">
                {i + 1}
              </div>
              <div className="text-sm">{step}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="space-y-4">
        <div className="rounded-2xl border border-border bg-primary p-6 text-primary-foreground">
          <Database className="h-5 w-5 opacity-80" />
          <div className="mt-3 text-sm font-semibold">Stack technologique</div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs opacity-90">
            {["Mesa", "NetworkX", "Streamlit", "PyYAML", "Pandas", "matplotlib", "openpyxl", "Qdrant ↗"].map((t) => (
              <div key={t} className="rounded-md bg-primary-foreground/10 px-2.5 py-1.5">
                {t}
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-border bg-card p-6">
          <Cpu className="h-5 w-5 text-accent" />
          <div className="mt-3 text-sm font-semibold">24 exports disponibles</div>
          <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
            <li className="flex justify-between">
              <span>kpi_summary.json</span>
              <span className="text-xs">2.0 ko</span>
            </li>
            <li className="flex justify-between">
              <span>what_if_capacity_results.json</span>
              <span className="text-xs">6.2 ko</span>
            </li>
            <li className="flex justify-between">
              <span>pathway_prioritization.json</span>
              <span className="text-xs">6.5 ko</span>
            </li>
            <li className="flex justify-between">
              <span>note_decision_hospitaliere.md</span>
              <span className="text-xs">4.8 ko</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}

function Footer() {
  return (
    <footer className="border-t border-border pt-10">
      <div className="flex flex-col items-start justify-between gap-4 md:flex-row">
        <div>
          <div className="text-sm font-semibold">HDJ Agent — Prototype d'aide à la décision</div>
          <div className="mt-1 text-xs text-muted-foreground">
            Porté par Ahmed EL-BAHRI & Caroline CARTIER · CHU Guyane · Défi 5 — Hôpitaux de jour.
          </div>
        </div>
        <div className="text-xs text-muted-foreground">
          Validation DIM/PMSI et gouvernance hospitalière requises avant mise en œuvre.
        </div>
      </div>
    </footer>
  );
}
