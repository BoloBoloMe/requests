// util/vars.ts: {{var}} 变量工具 (插值语法与后端 resolve.py 一致: {{ name }} 允许空白)
// SPA 仅做高亮与预览, 求值权威在后端 Resolve (M3 D008)

export interface VarSegment {
  text: string;
  isVar: boolean;
}

const VAR_RE = /\{\{\s*([^{}]+?)\s*\}\}/g;

/** 文本切段: 变量段 (含原始 {{}} 形态) 与普通段交替 */
export function splitVars(text: string): VarSegment[] {
  const segments: VarSegment[] = [];
  let last = 0;
  for (const match of text.matchAll(VAR_RE)) {
    if (match.index > last) segments.push({ text: text.slice(last, match.index), isVar: false });
    segments.push({ text: match[0], isVar: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last), isVar: false });
  return segments;
}

/** 解析预览: 已知变量替换, 未知变量原样保留 (后端 UNRESOLVED_VARIABLES 硬失败, M4 D006) */
export function resolvePreview(text: string, vars: Record<string, string>): string {
  return text.replace(VAR_RE, (raw, name: string) => {
    const key = name.trim();
    return key in vars ? vars[key] : raw;
  });
}
