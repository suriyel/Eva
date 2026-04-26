/**
 * MarkdownPreview — F22 §IC Section C.
 *
 * Minimal GFM-ish renderer: H1-H6 + paragraphs. Script tags stripped at the
 * source level (we never insert via dangerouslySetInnerHTML). For Wave 1 the
 * heading-level + paragraph fidelity is sufficient for §VRC `markdown-preview`
 * assertions; richer rendering (tables / code fences) can land in refactor.
 */
import * as React from "react";

export interface MarkdownPreviewProps {
  content: string;
}

interface ParsedNode {
  type: "h1" | "h2" | "h3" | "h4" | "h5" | "h6" | "p";
  text: string;
  slug?: string;
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9一-龥]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function parseMarkdown(src: string): ParsedNode[] {
  const out: ParsedNode[] = [];
  const lines = src.split(/\r?\n/);
  let para: string[] = [];
  const flush = (): void => {
    if (para.length > 0) {
      const text = para.join(" ").trim();
      if (text) out.push({ type: "p", text });
      para = [];
    }
  };
  for (const line of lines) {
    const m = /^(#{1,6})\s+(.+)$/.exec(line.trim());
    if (m) {
      flush();
      const level = m[1].length;
      const text = m[2];
      out.push({
        type: (`h${level}` as ParsedNode["type"]),
        text,
        slug: slugify(text),
      });
    } else if (line.trim() === "") {
      flush();
    } else {
      para.push(line);
    }
  }
  flush();
  return out;
}

export function MarkdownPreview(props: MarkdownPreviewProps): React.ReactElement {
  const { content } = props;
  const nodes = React.useMemo(() => parseMarkdown(content || ""), [content]);
  return (
    <div data-component="markdown-preview">
      {nodes.map((n, i) => {
        const Tag = n.type;
        if (Tag === "p") {
          return <p key={i}>{n.text}</p>;
        }
        return React.createElement(Tag, { key: i, id: n.slug }, n.text);
      })}
    </div>
  );
}
