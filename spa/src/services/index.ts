// services/index.ts: 适配层注入点 (INJECTABLE transport)
// 组件经 useServices() 取适配层; 测试注入 mock, 生产注入 HTTP 实现 (main.ts)
import type { App, InjectionKey } from "vue";
import { inject } from "vue";
import type { ApiServices } from "./types";

export const SERVICES_KEY: InjectionKey<ApiServices> = Symbol("apic-services");

export function provideServices(app: App, services: ApiServices): void {
  app.provide(SERVICES_KEY, services);
}

export function useServices(): ApiServices {
  const services = inject(SERVICES_KEY);
  if (!services) throw new Error("services 未注入: 组件树外或测试未提供 mock");
  return services;
}

export type { ApiServices } from "./types";
