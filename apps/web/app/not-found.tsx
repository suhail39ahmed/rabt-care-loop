import Link from "next/link";

export default function NotFound() {
  return (
    <main className="shell" style={{ textAlign: "center", paddingTop: "4rem" }}>
      <div className="brand-mark" style={{ justifyContent: "center" }}>
        <div className="mark">ر</div>
        <div style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>Rabt</div>
      </div>
      <h1 style={{ fontFamily: "var(--font-display)" }}>Page not found</h1>
      <p className="muted">That route is not part of the demo — or the shared demo was reset.</p>
      <Link className="btn" href="/">
        Back to demo home
      </Link>
    </main>
  );
}
