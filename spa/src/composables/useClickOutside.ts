import { onMounted, onUnmounted, unref, type Ref } from "vue";

export interface UseClickOutsideOptions {
  /** 点击这些元素/节点时不触发回调（典型用于下拉触发按钮） */
  ignore?: Array<Ref<HTMLElement | null> | HTMLElement | null>;
}

/**
 * 监听 document click：点击 el 外部时触发 callback。
 * 注册推迟到下一个微任务，避免打开弹层的同一 click 被误捕。
 */
export function useClickOutside(
  elRef: Ref<HTMLElement | null>,
  callback: () => void,
  options?: UseClickOutsideOptions,
): void {
  let timer: number | undefined;

  function handler(event: MouseEvent): void {
    const el = unref(elRef);
    if (!el || !event.target) return;
    if (el.contains(event.target as Node)) return;

    const ignores = options?.ignore
      ?.map(unref)
      .filter((node): node is HTMLElement => node instanceof HTMLElement);
    if (ignores?.some((node) => node.contains(event.target as Node))) return;

    callback();
  }

  onMounted(() => {
    // 宏任务注册: 微任务会在真浏览器事件派发中途执行 (监听器之间穿插微任务检查点),
    // 若用微任务, 「打开弹层的同一 click」冒泡到 document 时监听器已就位 → 弹层被秒关;
    // 宏任务在整个事件派发结束后才运行, 天然躲开开启点击.
    timer = setTimeout(() => {
      document.addEventListener("click", handler);
    }, 0);
  });

  onUnmounted(() => {
    clearTimeout(timer);
    document.removeEventListener("click", handler);
  });
}
