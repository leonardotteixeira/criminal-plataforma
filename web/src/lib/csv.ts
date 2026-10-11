/** Gera CSV (UTF-8 com BOM, abre no Excel) com linhas de metadados iniciadas por "#". */
export function toCsv(
  header: string[],
  rows: (string | number | null | undefined)[][],
  meta: string[] = [],
): string {
  const esc = (v: string | number | null | undefined) => {
    if (v == null) return "";
    const s = String(v);
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [
    ...meta.map((m) => `# ${m}`),
    header.map(esc).join(","),
    ...rows.map((r) => r.map(esc).join(",")),
  ];
  return "﻿" + lines.join("\n") + "\n";
}

export function downloadText(
  filename: string,
  text: string,
  type = "text/csv;charset=utf-8",
) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
