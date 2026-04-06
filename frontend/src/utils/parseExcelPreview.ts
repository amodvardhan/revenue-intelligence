import * as XLSX from "xlsx";

export function parseFirstSheetPreview(file: ArrayBuffer, maxRows = 5): {
  headers: string[];
  rows: (string | number | null)[][];
  sheetName: string;
  rowCountApprox: number;
} {
  const wb = XLSX.read(file, { type: "array" });
  const sheetName = wb.SheetNames[0] ?? "Sheet1";
  const sheet = wb.Sheets[sheetName];
  const rows = XLSX.utils.sheet_to_json<(string | number | boolean | null)[]>(sheet, {
    header: 1,
    defval: null,
    raw: true,
  }) as (string | number | boolean | null)[][];
  const headerRow = rows[0]?.map((c) => (c === null || c === undefined ? "" : String(c))) ?? [];
  const data: (string | number | null)[][] = rows.slice(1, 1 + maxRows).map((r) =>
    r.map((c) => {
      if (c === null || c === undefined) return null;
      if (typeof c === "boolean") return c ? 1 : 0;
      return c;
    }),
  );
  return {
    headers: headerRow,
    rows: data,
    sheetName,
    rowCountApprox: Math.max(0, rows.length - 1),
  };
}
