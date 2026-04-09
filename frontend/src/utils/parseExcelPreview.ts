import * as XLSX from "xlsx";

export type ExcelPreviewOptions = {
  /** @deprecated Preview auto-detects EUROPE Sheet1 layout when row 2 looks like Sr. No. + Customer Name */
  europeWeeklyCommercial?: boolean;
};

/** Excel 1900 date serials used for ~1980–2040 in raw cells. */
function isLikelyExcelDateSerial(n: number): boolean {
  return Number.isFinite(n) && n > 29500 && n < 65000;
}

function excelSerialToUTCDate(serial: number): Date {
  const epoch = Date.UTC(1899, 11, 30);
  return new Date(epoch + serial * 86400000);
}

function formatMonYy(d: Date): string {
  return new Intl.DateTimeFormat("en-US", { month: "short", year: "2-digit" }).format(d);
}

function formatCellForPreview(c: unknown): string {
  if (c === null || c === undefined) return "";
  if (c instanceof Date) return formatMonYy(c);
  if (typeof c === "number") {
    if (isLikelyExcelDateSerial(c)) {
      return formatMonYy(excelSerialToUTCDate(c));
    }
    return String(c);
  }
  if (typeof c === "boolean") return c ? "TRUE" : "FALSE";
  return String(c);
}

function formatDataCellForPreview(c: unknown): string | number | null {
  if (c === null || c === undefined) return null;
  if (typeof c === "number") {
    if (isLikelyExcelDateSerial(c)) {
      return formatMonYy(excelSerialToUTCDate(c));
    }
    return c;
  }
  if (typeof c === "boolean") return c ? 1 : 0;
  return String(c);
}

/** Read sheet as a dense grid so row indices match Excel (fixes sparse sheet_to_json skipping blank rows). */
function sheetToDenseMatrix(sheet: XLSX.WorkSheet): unknown[][] {
  const ref = sheet["!ref"];
  if (!ref) return [];
  const range = XLSX.utils.decode_range(ref);
  const grid: unknown[][] = [];
  for (let R = range.s.r; R <= range.e.r; R++) {
    const row: unknown[] = [];
    for (let C = range.s.c; C <= range.e.c; C++) {
      const addr = XLSX.utils.encode_cell({ r: R, c: C });
      const cell = sheet[addr];
      let v: unknown = cell?.v;
      if (cell?.t === "d" && v instanceof Date) {
        v = v;
      } else if (typeof v === "number" && cell?.t === "n" && isLikelyExcelDateSerial(v)) {
        v = v;
      }
      row.push(v ?? null);
    }
    grid.push(row);
  }
  return grid;
}

function rowLooksLikeEuropeHeaderRow(row: unknown[]): boolean {
  if (!row || row.length < 4) return false;
  const joined = row
    .slice(0, 12)
    .map((c) => (c == null || c === "" ? "" : String(c)).toLowerCase())
    .join(" ");
  if (!joined.includes("customer")) return false;
  const compact = joined.replace(/[\s._]/g, "");
  return compact.includes("sr") && compact.includes("no");
}

function findEuropeHeaderRowIndex(grid: unknown[][]): number | null {
  const max = Math.min(6, grid.length);
  for (let i = 0; i < max; i++) {
    if (rowLooksLikeEuropeHeaderRow(grid[i] ?? [])) return i;
  }
  return null;
}

function padRowToLength(row: unknown[], len: number): unknown[] {
  const out = row.slice(0, len);
  while (out.length < len) out.push(null);
  return out;
}

export function parseFirstSheetPreview(
  file: ArrayBuffer,
  maxRows = 5,
  _options?: ExcelPreviewOptions,
): {
  headers: string[];
  rows: (string | number | null)[][];
  sheetName: string;
  rowCountApprox: number;
} {
  const wb = XLSX.read(file, { type: "array", cellDates: true });
  const sheetName = wb.SheetNames.includes("Sheet1") ? "Sheet1" : wb.SheetNames[0] ?? "Sheet1";
  const sheet = wb.Sheets[sheetName];
  const grid = sheetToDenseMatrix(sheet);

  if (grid.length === 0) {
    return { headers: [], rows: [], sheetName, rowCountApprox: 0 };
  }

  const europeIdx = findEuropeHeaderRowIndex(grid);
  if (europeIdx !== null) {
    const headerRow = grid[europeIdx] ?? [];
    const width = Math.max(
      headerRow.length,
      ...grid.slice(europeIdx, europeIdx + 1 + maxRows).map((r) => r.length),
    );
    const headers = padRowToLength(headerRow, width).map((c) => formatCellForPreview(c));
    const data: (string | number | null)[][] = grid
      .slice(europeIdx + 1, europeIdx + 1 + maxRows)
      .map((r) => padRowToLength(r, width).map((c) => formatDataCellForPreview(c)));
    return {
      headers,
      rows: data,
      sheetName,
      rowCountApprox: Math.max(0, grid.length - europeIdx - 1),
    };
  }

  const headerRow = grid[0] ?? [];
  const width = Math.max(headerRow.length, ...grid.slice(0, 1 + maxRows).map((r) => r.length));
  const headers = padRowToLength(headerRow, width).map((c) => formatCellForPreview(c));
  const data: (string | number | null)[][] = grid.slice(1, 1 + maxRows).map((r) =>
    padRowToLength(r, width).map((c) => {
      if (c === null || c === undefined) return null;
      if (typeof c === "boolean") return c ? 1 : 0;
      if (typeof c === "number") return c;
      return String(c);
    }),
  );
  return {
    headers,
    rows: data,
    sheetName,
    rowCountApprox: Math.max(0, grid.length - 1),
  };
}
