import React from "react";

/** Tiny markdown subset for learn modules (headings, lists, bold, code, tables, hr). */
export function MdLite({ source }: { source: string }) {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  const inline = (text: string) => {
    const parts: React.ReactNode[] = [];
    const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text))) {
      if (m.index > last) parts.push(text.slice(last, m.index));
      const tok = m[0];
      if (tok.startsWith("**")) parts.push(<strong key={parts.length}>{tok.slice(2, -2)}</strong>);
      else parts.push(<code key={parts.length} className="code-pill">{tok.slice(1, -1)}</code>);
      last = m.index + tok.length;
    }
    if (last < text.length) parts.push(text.slice(last));
    return parts;
  };

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    if (line.startsWith("# ")) {
      blocks.push(
        <h1 key={key++} style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.02em" }}>
          {line.slice(2)}
        </h1>
      );
      i++;
      continue;
    }
    if (line.startsWith("## ")) {
      blocks.push(
        <h2 key={key++} style={{ fontFamily: "var(--font-display)", marginTop: "1.25rem" }}>
          {line.slice(3)}
        </h2>
      );
      i++;
      continue;
    }
    if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        const cells = lines[i]
          .split("|")
          .slice(1, -1)
          .map((c) => c.trim());
        if (!cells.every((c) => /^:?-+:?$/.test(c))) rows.push(cells);
        i++;
      }
      blocks.push(
        <div key={key++} style={{ overflowX: "auto", margin: "0.75rem 0" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.92rem" }}>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri}>
                  {r.map((c, ci) => {
                    const Tag = ri === 0 ? "th" : "td";
                    return (
                      <Tag
                        key={ci}
                        style={{
                          border: "1px solid var(--line)",
                          padding: "0.45rem 0.55rem",
                          textAlign: "start",
                          background: ri === 0 ? "var(--paper-2)" : "white",
                        }}
                      >
                        {inline(c)}
                      </Tag>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }
    if (/^\d+\.\s/.test(line) || line.startsWith("- ")) {
      const ordered = /^\d+\.\s/.test(line);
      const items: string[] = [];
      while (i < lines.length && (ordered ? /^\d+\.\s/.test(lines[i]) : lines[i].startsWith("- "))) {
        items.push(lines[i].replace(/^\d+\.\s/, "").replace(/^- /, ""));
        i++;
      }
      const ListTag = ordered ? "ol" : "ul";
      blocks.push(
        <ListTag key={key++} style={{ paddingInlineStart: "1.2rem" }}>
          {items.map((it, ii) => (
            <li key={ii} style={{ marginBottom: "0.35rem" }}>
              {inline(it)}
            </li>
          ))}
        </ListTag>
      );
      continue;
    }
    if (line.startsWith("```")) {
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        code.push(lines[i]);
        i++;
      }
      i++;
      blocks.push(
        <pre
          key={key++}
          style={{
            background: "#0c1b2a",
            color: "#e8f4f6",
            padding: "0.9rem 1rem",
            borderRadius: "0.75rem",
            overflowX: "auto",
            fontSize: "0.85rem",
          }}
        >
          {code.join("\n")}
        </pre>
      );
      continue;
    }
    blocks.push(
      <p key={key++} className="muted" style={{ color: "var(--ink)", lineHeight: 1.55 }}>
        {inline(line)}
      </p>
    );
    i++;
  }

  return <div className="md-lite">{blocks}</div>;
}
