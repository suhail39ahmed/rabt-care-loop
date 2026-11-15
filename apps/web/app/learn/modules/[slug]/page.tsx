import Link from "next/link";
import { notFound } from "next/navigation";
import { MODULES, MODULE_BODY } from "@/lib/learn-content";
import { MdLite } from "@/lib/md-lite";

export function generateStaticParams() {
  return MODULES.map((m) => ({ slug: m.slug }));
}

export default async function ModulePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const meta = MODULES.find((m) => m.slug === slug);
  const body = MODULE_BODY[slug];
  if (!meta || !body) notFound();

  const idx = MODULES.findIndex((m) => m.slug === slug);
  const prev = idx > 0 ? MODULES[idx - 1] : null;
  const next = idx < MODULES.length - 1 ? MODULES[idx + 1] : null;

  return (
    <main className="shell" style={{ maxWidth: 760 }}>
      <div className="topbar">
        <div className="brand-mark">
          <div className="mark">{meta.num}</div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>Lesson {meta.num}</div>
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              ~{meta.minutes} min
            </div>
          </div>
        </div>
        <Link className="btn secondary" href="/learn">
          Path
        </Link>
      </div>

      <div className="chip-row" style={{ marginBottom: "0.75rem" }}>
        <span className="tag role">
          {idx + 1} / {MODULES.length}
        </span>
        <span className="tag fact">{meta.title}</span>
      </div>

      <article className="panel soft">
        <MdLite source={body} />
      </article>

      <div className="actions" style={{ marginTop: "1rem" }}>
        {prev ? (
          <Link className="btn secondary" href={`/learn/modules/${prev.slug}`}>
            ← {prev.title}
          </Link>
        ) : (
          <Link className="btn secondary" href="/learn">
            ← Hub
          </Link>
        )}
        {next ? (
          <Link className="btn" href={`/learn/modules/${next.slug}`}>
            Next: {next.title} →
          </Link>
        ) : meta.slug === "features-deep-dive" || meta.slug === "architecture" ? (
          <>
            <Link className="btn" href="/learn/features">
              Open F1–F8 deep dive →
            </Link>
            <Link className="btn secondary" href="/learn/game">
              Practice
            </Link>
          </>
        ) : (
          <>
            <Link className="btn" href="/learn/features">
              Features deep dive →
            </Link>
            <Link className="btn secondary" href="/learn/game">
              Practice game
            </Link>
          </>
        )}
      </div>
    </main>
  );
}
