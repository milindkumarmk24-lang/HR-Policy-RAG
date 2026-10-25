/** "3.4 Sick Leave" -> { num: "3.4", title: "Sick Leave" } */
export function splitSection(section: string | null | undefined): { num: string | null; title: string } {
  if (!section) return { num: null, title: "Untitled passage" };
  // "3.4 Sick Leave", "II. Pregnancy and Childbirth", "II.A Sick Leave"
  const m = section.match(/^(\d{1,2}(?:\.\d{1,2})*|[IVX]{1,4}(?:\.[A-Z])?|[A-Z])\.?\s+(.*)$/);
  return m ? { num: m[1], title: m[2] } : { num: null, title: section };
}

export function pageLabel(page: number, pageEnd?: number | null): string {
  return pageEnd && pageEnd !== page ? `Pages ${page}–${pageEnd}` : `Page ${page}`;
}

/** Short marker text for an inline citation: the section number when there is one. */
export function citeLabel(section: string | null | undefined, page: number): string {
  const { num } = splitSection(section);
  return num ? `§${num}` : `p.${page}`;
}

export function score(v: number | null | undefined): string {
  return v === null || v === undefined ? "–" : v.toFixed(2);
}

export function seconds(ms: number | undefined): string {
  return ms === undefined ? "" : `${(ms / 1000).toFixed(1)} s`;
}

export function shortModel(name: string | null | undefined): string {
  if (!name) return "none";
  return name.split("/").pop() ?? name;
}

export function timeAgo(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** "Lumora_Employee_Handbook_2026.pdf" -> "Lumora Employee Handbook 2026" */
export function docName(filename: string): string {
  return filename.replace(/\.pdf$/i, "").replace(/[_]+/g, " ").replace(/\s+/g, " ").trim();
}

/** Drop the section heading line a chunk starts with (the note already shows it). */
export function excerptBody(text: string, section: string | null | undefined): string {
  if (section && text.startsWith(section)) return text.slice(section.length).replace(/^\s*\n/, "").trimStart();
  return text;
}
