/**
 * TocPanel — F22 §IC Section C.
 * Parses H1-H4 from markdown content and emits anchor links scrolling to
 * ``#heading-slug`` (handled natively by the browser).
 */
import * as React from "react";

export interface TocPanelProps {
  content: string;
}

interface TocEntry {
  level: number;
  text: string;
  slug: string;
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9一-龥]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function parseToc(src: string): TocEntry[] {
  const lines = src.split(/\r?\n/);
  const out: TocEntry[] = [];
  for (const line of lines) {
    const m = /^(#{1,4})\s+(.+)$/.exec(line.trim());
    if (m) {
      out.push({
        level: m[1].length,
        text: m[2],
        slug: slugify(m[2]),
      });
    }
  }
  return out;
}

export function TocPanel(props: TocPanelProps): React.ReactElement {
  const { content } = props;
  const items = React.useMemo(() => parseToc(content || ""), [content]);
  return (
    <nav data-component="toc">
      <ul>
        {items.map((it, i) => (
          <li key={i} data-toc-level={it.level}>
            <a href={`#${it.slug}`}>{it.text}</a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
