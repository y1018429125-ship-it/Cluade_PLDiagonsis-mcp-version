# 输电线路故障综合诊断智能体 — 前端界面设计文档

> **视觉方向**：智慧电网指挥中心 (Smart Grid Command Center)
> **氛围**：深色工业科技风，模拟电力调度中心的专业监控环境
> **核心记忆点**：顶部流光标题栏 + 状态呼吸灯 + 精确到毫秒的数据仪表盘

---

## 0. 设计系统 (Design System)

### 0.1 色彩令牌

```css
:root {
  /* 背景层 */
  --bg-base: #060b14;           /* 极深蓝黑，主背景 */
  --bg-panel: #0f172a;          /* 面板背景 */
  --bg-panel-glass: rgba(15, 23, 42, 0.85); /* 毛玻璃面板 */
  --bg-elevated: #1e293b;       /* 悬浮/选中背景 */
  --bg-input: #0a0f1a;          /* 输入框背景 */

  /* 功能色 */
  --color-primary: #3b82f6;     /* 工业蓝：主品牌、信息 */
  --color-success: #10b981;     /* 翠绿：正常、完成 */
  --color-warning: #f59e0b;     /* 琥珀：警告、注意 */
  --color-danger: #ef4444;      /* 红色：故障、错误 */
  --color-accent: #06b6d4;      /* 青色：科技强调 */

  /* 文字色 */
  --text-primary: #e2e8f0;      /* 主文字 */
  --text-secondary: #94a3b8;    /* 次要文字 */
  --text-muted: #64748b;        /* 禁用/占位 */
  --text-inverse: #0f172a;      /* 深色背景上的文字 */

  /* 边框 */
  --border-subtle: rgba(148, 163, 184, 0.1);
  --border-medium: rgba(148, 163, 184, 0.2);
  --border-glow: rgba(59, 130, 246, 0.3);   /* 主色光晕 */

  /* 状态色映射 */
  --status-pending: #64748b;
  --status-diagnosing: #3b82f6;
  --status-modifying: #f59e0b;
  --status-completed: #10b981;
}
```

### 0.2 字体系统

```css
:root {
  /* 标题：系统中文 + 无衬线 fallback */
  --font-display: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif;
  /* 数据/时间：等宽字体确保对齐 */
  --font-mono: "JetBrains Mono", "SF Mono", "Fira Code", "Courier New", monospace;
  /* 正文 */
  --font-body: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;

  /* 字号 */
  --text-xs: 0.6875rem;   /* 11px */
  --text-sm: 0.75rem;     /* 12px */
  --text-base: 0.8125rem; /* 13px */
  --text-md: 0.9375rem;   /* 15px */
  --text-lg: 1.125rem;    /* 18px */
  --text-xl: 1.5rem;      /* 24px */
  --text-2xl: 2rem;       /* 32px */
}
```

### 0.3 间距与圆角

```css
:root {
  --radius-sm: 0.375rem;   /* 6px */
  --radius-md: 0.5rem;     /* 8px */
  --radius-lg: 0.75rem;    /* 12px */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
}
```

### 0.4 动效令牌

```css
:root {
  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
  --duration-fast: 150ms;
  --duration-normal: 250ms;
  --duration-slow: 400ms;
}
```

### 0.5 全局背景效果

```css
.app-container {
  background: var(--bg-base);
  /* 极淡的网格纹理，模拟监控屏 */
  background-image:
    radial-gradient(ellipse at 50% 0%, rgba(59, 130, 246, 0.04) 0%, transparent 60%),
    linear-gradient(rgba(148, 163, 184, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.03) 1px, transparent 1px);
  background-size: 100% 100%, 40px 40px, 40px 40px;
  min-height: 100vh;
  color: var(--text-primary);
  font-family: var(--font-body);
  font-size: var(--text-base);
}
```

---

## 1. 整体布局

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ╔══════════════════════════════════════════════════════════════════════════╗ │
│ ║  ⚡ 输电线路故障综合诊断智能体                              [状态指示器] ║ │ ← 顶部标题栏
│ ╚══════════════════════════════════════════════════════════════════════════╝ │
│                                                                               │
│  ┌──────────────┐  ┌─────────────────────────────────────────────────────┐  │
│  │              │  │                                                     │  │
│  │ Session      │  │  ChatPanel / TemplateManager / ReportHistory        │  │
│  │ Sidebar      │  │                                                     │  │
│  │ (260px)      │  │  ┌─────────────────────────────────────────────┐   │  │
│  │              │  │  │ Message List                                   │   │  │
│  │ ● 京西线     │  │  │                                                │   │  │
│  │   220kV      │  │  │  [User] 220kV京西线#15跳闸...                  │   │  │
│  │   08:30:15.013│  │  │  [AI]   诊断完成卡片                            │   │  │
│  │              │  │  │  [ActionPanel] 快捷操作按钮                     │   │  │
│  │ ● 京南线     │  │  │                                                │   │  │
│  │   修改中     │  │  └─────────────────────────────────────────────┘   │  │
│  │              │  │                                                     │  │
│  │              │  │  ┌──────────────────┬────────────────────────────┐  │  │
│  │              │  │  │ InputArea        │ ChatToolbar               │  │  │
│  │              │  │  └──────────────────┴────────────────────────────┘  │  │
│  └──────────────┘  └─────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌────────────┬─────────────────────────────────────────────────────────┐    │
│  │ ToolList   │ StrategyManager                                         │    │
│  │ (240px)    │ (260px)                                                 │    │
│  └────────────┴─────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────┘
```

**布局规则：**
- 顶部固定标题栏（高度 56px）
- 左侧 SessionSidebar（固定 260px）
- 主内容区：flex-1，内部上下分区
  - 上区：MessageArea（flex-1，滚动）
  - 下区：InputArea（固定高度）
- 底部右侧：ToolList + StrategyManager（固定高度，可折叠）

**响应式断点：**

| 断点 | 布局调整 |
|------|---------|
| >= 1440px | 完整布局 |
| 1280px ~ 1439px | ToolList + StrategyManager 合并为可折叠面板 |
| 1024px ~ 1279px | 隐藏底部工具区，通过悬浮按钮展开 |
| < 1024px | SessionSidebar 变为抽屉，底部工具区隐藏 |

---

## 2. 顶部标题栏 (AppHeader.vue)

### 2.1 视觉设计

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ⚡  输电线路故障综合诊断智能体                                   [● 运行中]  │
│      Power Line Fault Comprehensive Diagnosis Agent                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

**样式规范：**

```css
.app-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1.5rem;
  background: rgba(6, 11, 20, 0.95);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-subtle);
  position: sticky;
  top: 0;
  z-index: 100;
}

.app-header::after {
  /* 底部流光效果 */
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg,
    transparent 0%,
    var(--color-primary) 20%,
    var(--color-accent) 50%,
    var(--color-primary) 80%,
    transparent 100%
  );
  opacity: 0.6;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-icon {
  font-size: 1.25rem;
  /* 闪电图标微动画 */
  animation: pulse-glow 3s ease-in-out infinite;
}

.header-title {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--text-primary);
}

.header-subtitle {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-left: 2.25rem; /* 与标题对齐 */
  margin-top: -0.25rem;
}

@keyframes pulse-glow {
  0%, 100% { filter: drop-shadow(0 0 2px var(--color-primary)); opacity: 0.8; }
  50% { filter: drop-shadow(0 0 6px var(--color-primary)); opacity: 1; }
}
```

### 2.2 状态指示器

```css
.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-success);
  box-shadow: 0 0 4px var(--color-success);
}

.status-dot.breathing {
  animation: breathing 2s ease-in-out infinite;
}

@keyframes breathing {
  0%, 100% { opacity: 1; box-shadow: 0 0 4px currentColor; }
  50% { opacity: 0.4; box-shadow: 0 0 2px currentColor; }
}
```

状态映射：
- `PENDING` → 灰色点，静态
- `DIAGNOSING` → 蓝色点，呼吸动画
- `MODIFYING` → 琥珀点，呼吸动画
- `COMPLETED` → 绿色点，静态

---

## 3. SessionSidebar.vue 改造设计

### 3.1 视觉设计

```
┌─────────────────────┐
│ 诊断会话              │
├─────────────────────┤
│                     │
│ ● 京西线              │ ← active 状态
│   220kV │ 诊断中      │
│   08:30:15.013      │ ← 等宽字体，毫秒级
│                     │
│ ○ 京南线              │
│   500kV │ 修改中      │
│   09:15:42.007      │
│                     │
│ ○ 京北线              │
│   220kV │ 已完成      │
│   07:20:11.105      │
│                     │
└─────────────────────┘
```

**样式规范：**

```css
.session-sidebar {
  width: 260px;
  background: var(--bg-panel);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 1rem;
  font-weight: 600;
  font-size: var(--text-sm);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.session-item {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background var(--duration-fast);
}

.session-item:hover {
  background: var(--bg-elevated);
}

.session-item.active {
  background: rgba(59, 130, 246, 0.08);
  border-left: 3px solid var(--color-primary);
}

.session-name {
  font-weight: 600;
  font-size: var(--text-md);
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

/* 状态小圆点 */
.session-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.session-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.25rem;
  font-size: var(--text-xs);
}

.meta-tag {
  padding: 0.125rem 0.375rem;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
}

.meta-tag.voltage {
  background: rgba(59, 130, 246, 0.12);
  color: var(--color-primary);
  font-family: var(--font-mono);
}

.meta-tag.status-diagnosing {
  background: rgba(59, 130, 246, 0.12);
  color: var(--color-primary);
}

.meta-tag.status-modifying {
  background: rgba(245, 158, 11, 0.12);
  color: var(--color-warning);
}

.meta-tag.status-completed {
  background: rgba(16, 185, 129, 0.12);
  color: var(--color-success);
}

.meta-tag.fault-time {
  font-family: var(--font-mono);
  color: var(--text-secondary);
  background: transparent;
  padding: 0;
  letter-spacing: 0.02em;
}
```

---

## 4. ChatPanel.vue 改造设计

### 4.1 消息气泡设计

**用户消息：**
```css
.message-user {
  align-self: flex-end;
  max-width: 70%;
  background: linear-gradient(135deg, var(--color-primary), #2563eb);
  color: #fff;
  padding: 0.75rem 1rem;
  border-radius: var(--radius-lg) var(--radius-lg) 4px var(--radius-lg);
  font-size: var(--text-base);
  line-height: 1.6;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.2);
}
```

**AI 消息：**
```css
.message-ai {
  align-self: flex-start;
  max-width: 80%;
  background: var(--bg-panel-glass);
  border: 1px solid var(--border-medium);
  padding: 0;
  border-radius: 4px var(--radius-lg) var(--radius-lg) var(--radius-lg);
  overflow: hidden;
}
```

### 4.2 诊断完成卡片（SummaryCard）

```
┌──────────────────────────────────────────┐
│ 诊断完成 ✓                                  │
├──────────────────────────────────────────┤
│                                          │
│  电压等级      220kV                     │
│  ─────────────────────────────────────   │
│  线路名称      京西线                     │
│  ─────────────────────────────────────   │
│  故障时间      2026-05-21 08:30:15.013   │ ← 等宽
│  ─────────────────────────────────────   │
│  故障类型      雷击                       │
│  ─────────────────────────────────────   │
│  置信度        ████████████░░ 85%        │ ← 进度条
│                                          │
├──────────────────────────────────────────┤
│ 操作记录: [排除鸟害] [权重调整]           │
│                                          │
│  [查看报告]  [完成诊断]                   │
└──────────────────────────────────────────┘
```

**样式规范：**

```css
.summary-card {
  background: var(--bg-panel-glass);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-lg);
  overflow: hidden;
  backdrop-filter: blur(8px);
}

.summary-header {
  padding: 0.75rem 1rem;
  background: rgba(16, 185, 129, 0.08);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  color: var(--color-success);
}

.summary-body {
  padding: 1rem;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border-subtle);
}

.summary-row:last-child {
  border-bottom: none;
}

.summary-label {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.summary-value {
  color: var(--text-primary);
  font-weight: 500;
  font-family: var(--font-body);
}

.summary-value.time {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--color-accent);
  letter-spacing: 0.02em;
}

/* 置信度进度条 */
.confidence-bar {
  width: 120px;
  height: 6px;
  background: var(--bg-elevated);
  border-radius: 3px;
  overflow: hidden;
}

.confidence-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width var(--duration-slow) var(--ease-out-expo);
}

.confidence-bar-fill.high { background: var(--color-success); }
.confidence-bar-fill.medium { background: var(--color-warning); }
.confidence-bar-fill.low { background: var(--color-danger); }
```

### 4.3 交互动作面板（ActionPanel）

```
┌──────────────────────────────────────────┐
│ 快捷操作                                   │
├──────────────────────────────────────────┤
│                                          │
│  [排除工具]  [恢复工具]  [重新检查]       │
│                                          │
│  [调权重]    [切换模板]  [修改报告]       │
│                                          │
└──────────────────────────────────────────┘
```

**样式规范：**

```css
.action-panel {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}

.action-panel-title {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-bottom: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.action-btn {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-sm);
  padding: 0.375rem 0.75rem;
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast);
  font-family: var(--font-body);
}

.action-btn:hover {
  background: rgba(59, 130, 246, 0.1);
  border-color: var(--color-primary);
  color: var(--color-primary);
  transform: translateY(-1px);
}

.action-btn:active {
  transform: translateY(0);
}
```

### 4.4 修改报告输入面板

```css
.modify-input-panel {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: var(--bg-input);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
}

.modify-input-panel textarea {
  width: 100%;
  resize: none;
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 0.625rem;
  font-size: var(--text-base);
  font-family: var(--font-body);
  color: var(--text-primary);
  line-height: 1.6;
}

.modify-input-panel textarea:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.modify-input-panel textarea::placeholder {
  color: var(--text-muted);
}
```

### 4.5 诊断状态指示器

```
┌──────────────────────────────────────────┐
│ 诊断中... ●●●                              │
├──────────────────────────────────────────┤
│ ● 信息提取              ✓                  │
│ ● 天气判断              ✓                  │
│ ● 工具调用              ●●● 进行中        │
│   ├─ Lightning   ████████░░ 80%          │
│   ├─ Wind        ██████████ 100% ✓       │
│   └─ Icing       ████░░░░░░ 40% ...      │
│ ● 报告生成              ○ 等待            │
└──────────────────────────────────────────┘
```

**样式规范：**

```css
.status-indicator-panel {
  background: var(--bg-panel-glass);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-lg);
  padding: 1rem;
}

.status-indicator-panel .panel-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.status-indicator-panel .dots {
  display: flex;
  gap: 0.25rem;
}

.status-indicator-panel .dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: dot-bounce 1.4s ease-in-out infinite;
}

.status-indicator-panel .dots span:nth-child(2) { animation-delay: 0.2s; }
.status-indicator-panel .dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.progress-step {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.375rem 0;
  font-size: var(--text-sm);
}

.step-icon {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  flex-shrink: 0;
}

.step-icon.done {
  background: rgba(16, 185, 129, 0.15);
  color: var(--color-success);
}

.step-icon.pending {
  background: var(--bg-elevated);
  color: var(--text-muted);
}

.step-icon.running {
  background: rgba(59, 130, 246, 0.15);
  color: var(--color-primary);
}
```

---

## 5. 新增：TemplateManager.vue（模板管理）

### 5.1 界面布局

```
┌─────────────────────────────────────────────────────────────────┐
│ 模板管理                                        [+ 上传模板]    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 当前激活模板                                             │   │
│  │ ┌─────────────────────────────────────────────────────┐ │   │
│  │ │ 📄 国网标准模板 (docx)                    [更换]    │ │   │
│  │ │ 章节: 概述 / 故障分析 / 诊断证据 / 结论 / 建议      │ │   │
│  │ └─────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  模板列表                                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 📄 国网标准模板    docx    ✅已解析    [激活][预览][×]  │   │
│  │ 📄 省公司模板      pdf     ⏳解析中    [激活][预览][×]  │   │
│  │ 📝 自定义模板      md      ✅已解析    [激活][预览][×]  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**样式规范：**

```css
.template-manager {
  padding: 1.5rem;
  max-width: 900px;
}

.tm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.tm-header h2 {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: 700;
  font-family: var(--font-display);
}

.tm-upload-btn {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.5rem 1rem;
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast);
  font-weight: 500;
}

.tm-upload-btn:hover {
  background: #2563eb;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

.tm-active-card {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08), rgba(6, 182, 212, 0.05));
  border: 1px solid var(--border-glow);
  border-radius: var(--radius-lg);
  padding: 1rem;
  margin-bottom: 1.5rem;
}

.tm-active-card .card-title {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 0.5rem;
}

.tm-drop-zone {
  border: 2px dashed var(--border-medium);
  border-radius: var(--radius-lg);
  padding: 2.5rem;
  text-align: center;
  color: var(--text-secondary);
  margin-bottom: 1.5rem;
  transition: all var(--duration-fast);
  background: var(--bg-panel);
}

.tm-drop-zone.active {
  border-color: var(--color-primary);
  background: rgba(59, 130, 246, 0.05);
}

.tm-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.tm-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.875rem 1rem;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background: var(--bg-panel);
  transition: all var(--duration-fast);
}

.tm-item:hover {
  border-color: var(--border-medium);
  background: var(--bg-elevated);
}

.tm-item.active {
  border-color: var(--color-success);
  background: rgba(16, 185, 129, 0.05);
}

.tm-item-status.parsed {
  background: rgba(16, 185, 129, 0.12);
  color: var(--color-success);
}

.tm-item-status.parsing {
  background: rgba(245, 158, 11, 0.12);
  color: var(--color-warning);
}

.tm-action-btn {
  font-size: var(--text-xs);
  padding: 0.25rem 0.625rem;
  border-radius: var(--radius-sm);
  border: 1px solid;
  cursor: pointer;
  background: transparent;
  transition: all var(--duration-fast);
}

.tm-action-btn.activate {
  color: var(--color-success);
  border-color: rgba(16, 185, 129, 0.3);
}

.tm-action-btn.activate:hover {
  background: rgba(16, 185, 129, 0.1);
}

.tm-action-btn.delete {
  color: var(--color-danger);
  border-color: rgba(239, 68, 68, 0.3);
}

.tm-action-btn.delete:hover {
  background: rgba(239, 68, 68, 0.1);
}
```

---

## 6. ToolList.vue 改造设计

```
┌─────────────────────────────────┐
│ 诊断工具              [⟳]       │
├─────────────────────────────────┤
│                                 │
│ ⚡ 雷击诊断                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ 权重: 1.2  [████████●██]        │ ← 可视化滑轨
│ 状态: ● 正常                     │
│ [排除] [复查]                   │
│                                 │
│ ❄️ 覆冰诊断                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ 权重: 0.5  [██●██████]          │
│ 状态: ⏸ 已排除                   │
│ [恢复] [调权重]                 │
│                                 │
└─────────────────────────────────┘
```

**样式规范：**

```css
.tool-list {
  width: 240px;
  background: var(--bg-panel);
  border-top: 1px solid var(--border-subtle);
  border-right: 1px solid var(--border-subtle);
  padding: 1rem;
}

.tool-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 0.75rem;
  margin-bottom: 0.625rem;
  transition: all var(--duration-fast);
}

.tool-card:hover {
  border-color: var(--border-medium);
}

.tool-card.excluded {
  opacity: 0.5;
  border-color: var(--border-subtle);
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  font-size: var(--text-sm);
  margin-bottom: 0.5rem;
}

.weight-track {
  height: 4px;
  background: var(--bg-elevated);
  border-radius: 2px;
  margin: 0.375rem 0;
  position: relative;
}

.weight-track-fill {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--color-primary), var(--color-accent));
  transition: width var(--duration-slow) var(--ease-out-expo);
}

.weight-value {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}
```

---

## 7. StrategyManager.vue 改造设计

```
┌─────────────────────────────────┐
│ 技能策略              [⟳][↺]    │
├─────────────────────────────────┤
│                                 │
│ ● comprehensive_diagnosis       │
│   [已激活] 系统默认              │
│   触发: 输电线路故障诊断          │
│   [👁 预览]                     │
│                                 │
│ ○ lightning_priority            │
│   [激活] 用户保存                │
│   触发: 雷击优先场景             │
│   [👁 预览] [🗑 删除]           │
│                                 │
│ ○ icing_winter                  │
│   [激活] 用户保存                │
│   触发: 冬季覆冰场景             │
│   [👁 预览] [🗑 删除]           │
│                                 │
└─────────────────────────────────┘
```

**样式规范：**

```css
.strategy-manager {
  width: 260px;
  background: var(--bg-panel);
  border-top: 1px solid var(--border-subtle);
  padding: 1rem;
}

.skill-item {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 0.875rem;
  margin-bottom: 0.625rem;
  transition: all var(--duration-fast);
}

.skill-item:hover {
  border-color: var(--border-medium);
}

.skill-item.active {
  border-color: var(--color-success);
  background: rgba(16, 185, 129, 0.03);
}

.skill-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: var(--text-xs);
  padding: 0.125rem 0.5rem;
  border-radius: 999px;
}

.skill-badge.active {
  background: rgba(16, 185, 129, 0.12);
  color: var(--color-success);
}

.skill-badge.user {
  background: rgba(59, 130, 246, 0.12);
  color: var(--color-primary);
}
```

---

## 8. ReportHistory.vue 改造设计

表格样式规范：

```css
.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.report-table th {
  text-align: left;
  padding: 0.75rem 1rem;
  font-weight: 600;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-medium);
  text-transform: uppercase;
  font-size: var(--text-xs);
  letter-spacing: 0.05em;
}

.report-table td {
  padding: 0.875rem 1rem;
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-primary);
}

.report-table tr:hover td {
  background: rgba(148, 163, 184, 0.04);
}

.report-table .time-cell {
  font-family: var(--font-mono);
  color: var(--text-secondary);
  font-size: var(--text-xs);
}
```

---

## 9. 输入区域（InputArea）

```
┌────────────────────────────────────────────────────────────────────┐
│ ┌──────────────────────────────────────────────────────────────┐  │
│ │ 请输入故障描述，如：220kV京西线#15杆塔附近跳闸...           │  │
│ └──────────────────────────────────────────────────────────────┘  │
│ [📎]  [📄 模板: 国网标准]                    [发送 →]            │
└────────────────────────────────────────────────────────────────────┘
```

**样式规范：**

```css
.input-area {
  padding: 0.75rem 1rem;
  background: var(--bg-panel);
  border-top: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.input-textarea {
  width: 100%;
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 0.75rem 1rem;
  font-size: var(--text-base);
  font-family: var(--font-body);
  color: var(--text-primary);
  line-height: 1.6;
  resize: none;
  min-height: 48px;
  max-height: 160px;
}

.input-textarea:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.send-btn {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.5rem 1.25rem;
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast);
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.send-btn:hover {
  background: #2563eb;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.template-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  background: rgba(59, 130, 246, 0.1);
  color: var(--color-primary);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 999px;
  padding: 0.25rem 0.625rem;
  font-size: var(--text-xs);
}
```

---

## 10. 全局组件

### 10.1 模态弹窗（Modal）

```css
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(6, 11, 20, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.modal-content {
  background: var(--bg-panel);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-lg);
  max-width: 600px;
  width: 90%;
  max-height: 80vh;
  overflow: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-header {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-body {
  padding: 1.25rem;
}

.modal-close {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 1.25rem;
  transition: color var(--duration-fast);
}

.modal-close:hover {
  color: var(--text-primary);
}
```

### 10.2 按钮变体

```css
/* 主按钮 */
.btn-primary {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.5rem 1rem;
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast);
}

.btn-primary:hover {
  background: #2563eb;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

/* 次级按钮 */
.btn-secondary {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
  padding: 0.5rem 1rem;
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast);
}

.btn-secondary:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

/* 危险按钮 */
.btn-danger {
  background: transparent;
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md);
  padding: 0.5rem 1rem;
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast);
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.1);
}
```

### 10.3 Toast 通知

```css
.toast {
  position: fixed;
  top: 72px;
  right: 1.5rem;
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  animation: toast-in var(--duration-normal) var(--ease-out-expo);
  z-index: 300;
}

.toast.success {
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: var(--color-success);
}

.toast.error {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--color-danger);
}

@keyframes toast-in {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
```

---

## 11. 交互状态机（前端视角）

```
用户打开页面
    │
    ▼
┌─────────────┐
│  PENDING    │ ← 显示欢迎语 + 故障输入引导
│  待处理      │
└─────────────┘
    │ 用户发送诊断请求
    ▼
┌─────────────┐
│  DIAGNOSING │ ← 状态指示器 + 工具进度卡片
│  诊断中      │     标题栏状态灯变蓝呼吸
└─────────────┘
    │ 诊断完成
    ▼
┌─────────────┐
│  MODIFYING  │ ← SummaryCard + ActionPanel
│  可修改      │     标题栏状态灯变黄呼吸
│              │     用户可以:
│              │     - 排除/恢复工具
│              │     - 调整权重
│              │     - 重新检查
│              │     - 修改报告
│              │     - 切换模板
│              │     - 保存技能
│              │     - 完成诊断
└─────────────┘
    │ 点击"完成诊断"
    ▼
┌─────────────┐
│  COMPLETED  │ ← 完成回顾面板 + 保存技能提示
│  已完成      │     标题栏状态灯变绿静态
└─────────────┘
```

---

## 12. 新增 API 接口（前端调用）

与 v1.0 保持一致，详见原设计文档第 8 节。

---

*前端设计文档版本：v2.0*
*日期：2026-05-21*
*状态：待审核*
*视觉方向：智慧电网指挥中心 (Smart Grid Command Center)*
