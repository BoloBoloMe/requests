// 入口: 生产接线 — services 走 HTTP 适配层 (同源托管, token 页面注入), store 首屏装载
import "./style.css";
import { createApp } from "vue";
import App from "./App.vue";
import { SERVICES_KEY } from "./services";
import { createHttpServices } from "./services/http";
import { createAppStore, STORE_KEY } from "./stores/app";

const services = createHttpServices();
const store = createAppStore(services);

const app = createApp(App);
app.provide(SERVICES_KEY, services);
app.provide(STORE_KEY, store);
app.mount("#app");

// 首屏数据装载失败不阻塞挂载 (token 缺失等降级场景由具体请求报错呈现)
void store.init().catch((exc: unknown) => {
  console.error("首屏装载失败:", exc);
});
