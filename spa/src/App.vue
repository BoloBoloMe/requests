<script setup lang="ts">
// App 骨架 (ISSUE-01): 双栏纵向流布局 (M5 决策 1, 原型变体 B)
// 左侧栏 (集合树/环境/git) + 右主区上下分割 (上请求构建器, 下响应查看器)
import Sidebar from "./components/sidebar/Sidebar.vue";
import RequestBuilder from "./components/builder/RequestBuilder.vue";
import ResponsePane from "./components/response/ResponsePane.vue";
</script>

<template>
  <div class="vb">
    <Sidebar />
    <div class="main">
      <RequestBuilder />
      <ResponsePane />
    </div>
  </div>
</template>
