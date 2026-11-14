export type DiffPart = { type: "same" | "add" | "del"; text: string };

function tokenize(text: string, byLine: boolean): string[] {
  return byLine
    ? text.split(/(?<=\n)/)
    : text.split(/(\s+)/).filter((t) => t !== "");
}

/** Word-level diff (longest common subsequence); falls back to lines for very long texts. */
export function diffText(before: string, after: string): DiffPart[] {
  let byLine = false;
  let a = tokenize(before, false);
  let b = tokenize(after, false);
  if (a.length * b.length > 4_000_000) {
    byLine = true;
    a = tokenize(before, byLine);
    b = tokenize(after, byLine);
  }
  const n = a.length;
  const m = b.length;
  const lcs: Uint32Array[] = Array.from(
    { length: n + 1 },
    () => new Uint32Array(m + 1),
  );
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i][j] =
        a[i] === b[j]
          ? lcs[i + 1][j + 1] + 1
          : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const parts: DiffPart[] = [];
  const push = (type: DiffPart["type"], text: string) => {
    const last = parts[parts.length - 1];
    if (last && last.type === type) last.text += text;
    else parts.push({ type, text });
  };
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      push("same", a[i]);
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) push("del", a[i++]);
    else push("add", b[j++]);
  }
  while (i < n) push("del", a[i++]);
  while (j < m) push("add", b[j++]);
  return parts;
}
