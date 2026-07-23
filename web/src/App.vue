<script setup lang="ts">
import { ref } from 'vue'
import '@/styles/design-system.css'
import AppHeader from '@/components/AppHeader.vue'
import SessionSidebar from '@/components/SessionSidebar.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import ToolList from '@/components/ToolList.vue'
import StrategyManager from '@/components/StrategyManager.vue'
import ReportHistory from '@/components/ReportHistory.vue'
import TemplateManager from '@/components/TemplateManager.vue'

const currentView = ref<'chat' | 'reports' | 'templates'>('chat')

function switchView(view: 'chat' | 'reports' | 'templates') {
  currentView.value = view
}
</script>

<template>
  <div class="app-container">
    <AppHeader />
    <div class="app-layout">
      <SessionSidebar :current-view="currentView" @switch-view="switchView" />
      <template v-if="currentView === 'chat'">
        <ChatPanel />
        <ToolList />
        <StrategyManager />
      </template>
      <ReportHistory v-else-if="currentView === 'reports'" />
      <TemplateManager v-else-if="currentView === 'templates'" />
    </div>
  </div>
</template>

<style>
html,
body,
#app {
  margin: 0;
  padding: 0;
  height: 100%;
}

* {
  box-sizing: border-box;
}

.app-layout {
  display: flex;
  height: calc(100vh - 56px);
  overflow: hidden;
}
</style>
