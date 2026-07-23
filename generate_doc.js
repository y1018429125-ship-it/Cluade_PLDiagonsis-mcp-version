const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
        BorderStyle, WidthType, ShadingType, PageNumber } = require('docx');
const fs = require('fs');
const path = require('path');

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

function cell(text, width, options = {}) {
  const { bold = false, shading = null, colSpan = 1 } = options;
  const children = [new Paragraph({
    children: [new TextRun({ text, bold, font: "Arial", size: 21 })]
  })];
  const cfg = {
    borders,
    width: { size: width, type: WidthType.DXA },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children,
    columnSpan: colSpan,
  };
  if (shading) {
    cfg.shading = { fill: shading, type: ShadingType.CLEAR };
  }
  return new TableCell(cfg);
}

function headerCell(text, width) {
  return cell(text, width, { bold: true, shading: "D5E8F0" });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, bold: true, font: "Arial", size: 32, color: "1F4E79" })],
    spacing: { before: 240, after: 120 },
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, bold: true, font: "Arial", size: 28, color: "2E75B6" })],
    spacing: { before: 200, after: 100 },
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text, bold: true, font: "Arial", size: 24, color: "2E75B6" })],
    spacing: { before: 160, after: 80 },
  });
}

function p(text, options = {}) {
  const { bold = false, size = 21 } = options;
  return new Paragraph({
    children: [new TextRun({ text, bold, font: "Arial", size })],
    spacing: { before: 60, after: 60 },
    alignment: AlignmentType.JUSTIFIED,
  });
}

function bullet(text, ref = "bullets") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    children: [new TextRun({ text, font: "Arial", size: 21 })],
    spacing: { before: 40, after: 40 },
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: "1F4E79" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        children: [new TextRun({ text: "PLDiagnosis 智能诊断平台", bold: true, font: "Arial", size: 18, color: "666666" })],
        alignment: AlignmentType.RIGHT,
      })] })
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        children: [
          new TextRun({ text: "第 ", font: "Arial", size: 18 }),
          new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 18 }),
          new TextRun({ text: " 页", font: "Arial", size: 18 }),
        ],
        alignment: AlignmentType.CENTER,
      })] })
    },
    children: [
      new Paragraph({
        children: [new TextRun({ text: "PLDiagnosis 输电线路故障智能诊断平台", bold: true, font: "Arial", size: 44, color: "1F4E79" })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 2400, after: 400 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "部署环境 · 应用功能 · 技术架构", font: "Arial", size: 28, color: "2E75B6" })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 2400 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "版本：v0.2.0-alpha    日期：2026年7月", font: "Arial", size: 21, color: "666666" })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 600 },
      }),

      h1("一、平台概述"),
      p("PLDiagnosis 是一款面向特高压及高压输电线路的智能化故障综合诊断平台。平台以大语言模型（LLM）为核心认知中枢，采用主-子智能体协同架构，由输电综合诊断主智能体负责任务理解、诊断规划与决策编排，协同雷电、覆冰、风偏、鸟害等多个领域子智能体，融合雷电定位、分布式监测、微气象、行波波形等多源异构数据，实现从自然语言故障描述到结构化诊断报告的全流程自动化生成。"),
      p("平台面向电网运维、故障分析、调度决策等场景，提供自然语言交互、多工具协同推理、加权置信度研判、人在回路优化、诊断策略固化等能力，显著提升输电线路故障研判的效率与可解释性。"),

      h2("1.1 核心价值"),
      bullet("多源数据融合：整合雷电、覆冰、风偏、鸟害、气象等多维度子智能体诊断能力。"),
      bullet("智能推理引擎：基于大语言模型实现意图理解、方案规划、报告生成与置信度计算。"),
      bullet("实时流式反馈：通过 Server-Sent Events（SSE）向前端实时推送诊断进度与中间结果。"),
      bullet("主-子智能体协同：输电综合诊断主智能体统一调度各领域子智能体，实现并行推理与综合研判。"),
      bullet("人在回路机制：支持子智能体排除、权重调整、报告修改、策略保存等交互式优化。"),
      bullet("全链路可观测：内置诊断全流程日志，记录阶段时延、SSE 事件、子智能体调用与前端输出。"),

      h1("二、软硬件部署环境"),
      h2("2.1 运行环境"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2800, 6560],
        rows: [
          new TableRow({ children: [headerCell("项目", 2800), headerCell("说明", 6560)] }),
          new TableRow({ children: [cell("操作系统", 2800), cell("macOS / Linux / Windows（兼容 Docker 部署）", 6560)] }),
          new TableRow({ children: [cell("Python 版本", 2800), cell("Python 3.10+", 6560)] }),
          new TableRow({ children: [cell("Node.js 版本", 2800), cell("Node.js 18+（前端构建）", 6560)] }),
          new TableRow({ children: [cell("部署方式", 2800), cell("本地开发模式 / Docker Compose 生产模式", 6560)] }),
          new TableRow({ children: [cell("浏览器", 2800), cell("Chrome / Edge / Safari / Firefox 现代浏览器", 6560)] }),
        ]
      }),

      h2("2.2 服务端依赖"),
      p("后端基于 Python 生态构建，主要依赖包括："),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 6960],
        rows: [
          new TableRow({ children: [headerCell("依赖", 2400), headerCell("用途", 6960)] }),
          new TableRow({ children: [cell("Flask", 2400), cell("Web 服务框架，提供 RESTful API 与 SSE 流式接口", 6960)] }),
          new TableRow({ children: [cell("Pydantic v2", 2400), cell("数据模型定义、配置校验与类型安全", 6960)] }),
          new TableRow({ children: [cell("httpx", 2400), cell("异步 HTTP 客户端，用于调用各子智能体服务", 6960)] }),
          new TableRow({ children: [cell("OpenAI SDK", 2400), cell("兼容 OpenAI API 的大语言模型调用", 6960)] }),
          new TableRow({ children: [cell("PyYAML / Jinja2", 2400), cell("配置文件解析与模板渲染", 6960)] }),
          new TableRow({ children: [cell("python-docx", 2400), cell("报告导出支持", 6960)] }),
        ]
      }),

      h2("2.3 前端依赖"),
      p("前端基于 Vue 3 生态构建，主要依赖包括："),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 6960],
        rows: [
          new TableRow({ children: [headerCell("依赖", 2400), headerCell("用途", 6960)] }),
          new TableRow({ children: [cell("Vue 3.5", 2400), cell("渐进式前端框架，组合式 API 开发", 6960)] }),
          new TableRow({ children: [cell("TypeScript", 2400), cell("类型安全的前端代码", 6960)] }),
          new TableRow({ children: [cell("Vite", 2400), cell("前端构建工具", 6960)] }),
          new TableRow({ children: [cell("Pinia", 2400), cell("状态管理", 6960)] }),
          new TableRow({ children: [cell("marked", 2400), cell("Markdown 渲染", 6960)] }),
          new TableRow({ children: [cell("KaTeX", 2400), cell("LaTeX 数学公式渲染", 6960)] }),
        ]
      }),

      h2("2.4 启动方式"),
      p("开发模式一键启动："),
      new Paragraph({
        children: [new TextRun({ text: "./start.sh dev", font: "Courier New", size: 20 })],
        shading: { fill: "F5F5F5", type: ShadingType.CLEAR },
        spacing: { before: 80, after: 80 },
      }),
      p("该命令依次启动 5 个专业子智能体服务、安装后端依赖、构建前端、启动 Flask 主服务。"),
      p("生产模式可通过 Docker Compose 一键部署："),
      new Paragraph({
        children: [new TextRun({ text: "./start.sh docker", font: "Courier New", size: 20 })],
        shading: { fill: "F5F5F5", type: ShadingType.CLEAR },
        spacing: { before: 80, after: 80 },
      }),

      h1("三、应用功能"),
      h2("3.1 智能诊断流程"),
      p("用户通过自然语言描述故障情况，平台自动完成以下流程："),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [1600, 7760],
        rows: [
          new TableRow({ children: [headerCell("阶段", 1600), headerCell("功能描述", 7760)] }),
          new TableRow({ children: [cell("意图识别", 1600), cell("识别用户意图类型：诊断、排除子智能体、恢复子智能体、调整权重、修改报告、完成诊断等", 7760)] }),
          new TableRow({ children: [cell("上下文解析", 1600), cell("从自然语言中提取线路名称、故障时间、电压等级等关键信息", 7760)] }),
          new TableRow({ children: [cell("会话管理", 1600), cell("同一线路+时间复用会话，支持多轮对话与状态持久化", 7760)] }),
          new TableRow({ children: [cell("诊断规划", 1600), cell("大模型根据技能策略与气象条件，决定调用哪些子智能体", 7760)] }),
          new TableRow({ children: [cell("子智能体调用", 1600), cell("并行调用多个领域子智能体，获取结构化证据与置信度", 7760)] }),
          new TableRow({ children: [cell("报告生成", 1600), cell("大模型综合各子智能体输出，生成标准化 Markdown 诊断报告", 7760)] }),
          new TableRow({ children: [cell("状态转换", 1600), cell("诊断完成后进入可修改状态，支持人在回路优化", 7760)] }),
        ]
      }),

      h2("3.2 人在回路交互"),
      bullet("子智能体排除与恢复：用户可动态排除或恢复某个领域子智能体，系统自动重新诊断。"),
      bullet("权重动态调整：支持调整各子智能体的权重系数，影响综合置信度计算。"),
      bullet("报告在线修改：用户可对生成的报告提出修改意见，系统重新生成。"),
      bullet("策略保存为技能：用户可将调整后的诊断策略保存为 Markdown 技能文件，后续复用。"),

      h2("3.3 领域子智能体矩阵"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2600, 1600, 1600, 3560],
        rows: [
          new TableRow({ children: [headerCell("子智能体名称", 2600), headerCell("协议", 1600), headerCell("权重", 1600), headerCell("能力说明", 3560)] }),
          new TableRow({ children: [cell("雷电子智能体", 2600), cell("MCP HTTP", 1600), cell("1.0", 1600), cell("基于真实雷电定位、波形、微气象数据判定雷击/绕击故障", 3560)] }),
          new TableRow({ children: [cell("覆冰子智能体", 2600), cell("MCP HTTP", 1600), cell("0.9", 1600), cell("分析线路覆冰风险与冰闪可能性", 3560)] }),
          new TableRow({ children: [cell("风偏子智能体", 2600), cell("MCP HTTP", 1600), cell("0.8", 1600), cell("评估风偏导致的绝缘距离不足风险", 3560)] }),
          new TableRow({ children: [cell("鸟害子智能体", 2600), cell("MCP HTTP", 1600), cell("0.6", 1600), cell("识别鸟粪闪络等鸟害相关故障", 3560)] }),
          new TableRow({ children: [cell("气象子智能体", 2600), cell("Web Scraper", 1600), cell("0.5", 1600), cell("抓取气象数据辅助环境因素分析", 3560)] }),
        ]
      }),

      h1("四、应用框架与技术架构"),
      h2("4.1 主-子智能体协同架构"),
      p("平台采用主-子智能体协同架构。输电综合诊断主智能体作为任务编排中枢，负责自然语言理解、诊断方案规划、子智能体调度、加权置信度研判与诊断报告生成。各子智能体则聚焦特定故障领域，独立完成证据采集与初步判定，并将结构化结果返回给主智能体进行综合。"),
      p("这种架构的优势在于：主智能体专注于通用推理与决策，子智能体专注于领域知识，二者解耦便于独立演进与扩展。"),

      h2("4.2 分层实现"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2200, 7160],
        rows: [
          new TableRow({ children: [headerCell("层级", 2200), headerCell("职责与组件", 7160)] }),
          new TableRow({ children: [cell("Interfaces 层", 2200), cell("Flask 路由、SSE 流、前端静态资源服务、依赖注入容器", 7160)] }),
          new TableRow({ children: [cell("Application 层", 2200), cell("命令模式封装：Diagnose、Exclude、Recheck、AdjustWeight、Complete 等", 7160)] }),
          new TableRow({ children: [cell("Domain 层", 2200), cell("状态机、会话管理、意图分类、诊断规划、子智能体调度、报告生成、提示构建", 7160)] }),
          new TableRow({ children: [cell("Core 层", 2200), cell("数据模型、配置管理、领域异常定义", 7160)] }),
          new TableRow({ children: [cell("Infrastructure 层", 2200), cell("LLM 服务、子智能体适配器、子智能体注册表、事件总线、会话仓库、诊断日志", 7160)] }),
        ]
      }),

      h2("4.3 关键技术特性"),
      bullet("主-子智能体协同：输电综合诊断主智能体统一调度各领域子智能体，实现并行推理与综合研判。"),
      bullet("命令模式：每个用户意图映射为独立 Command，统一接口 execute(ctx) -> AsyncIterator[Event]。"),
      bullet("依赖注入：Container 集中装配所有组件，避免手动传参与紧耦合。"),
      bullet("状态机：会话状态转换严格受控，非法转换被拒绝，保证流程完整性。"),
      bullet("事件总线：异步发布-订阅模式解耦状态变更与事件通知。"),
      bullet("MCP 适配器：统一 HTTP 协议调用各子智能体服务，支持调用记录与错误降级。"),
      bullet("Skill 驱动：诊断策略以 Markdown 技能文件形式管理，可动态加载、保存与复用。"),

      h2("4.4 三层记忆机制"),
      p("为支撑复杂诊断场景下的连续推理与经验复用，平台设计了三层记忆机制，覆盖单次会话、跨会话策略与历史知识三个维度："),
      bullet("工作记忆（Working Memory）：基于当前会话的 chat_history、current_summary、latest_report 等状态，支持多轮对话内的上下文连续推理与报告迭代。"),
      bullet("策略记忆（Strategy Memory）：通过 action_log 记录用户排除、恢复、调整权重等操作，并支持将优化后的诊断策略保存为 Markdown 技能文件，实现跨会话复用。"),
      bullet("知识记忆（Knowledge Memory）：基于 sessions.json 持久化的历史会话与诊断摘要，为后续引入案例检索、相似故障推荐与诊断经验沉淀提供数据基础。"),
      p("当前平台已实现工作记忆与策略记忆的闭环，知识记忆正在进一步演进中。"),

      h2("4.5 人在回路驱动的自演进机制"),
      p("平台已具备人在回路驱动的策略自演进雏形。运维人员在诊断过程中对子智能体的排除与恢复、权重调整、报告修改等操作，会被记录为反馈轨迹；经用户确认后，这些优化后的策略可固化为 Markdown 技能文件，供后续会话加载复用，实现经验的人工审核式沉淀。"),
      p("该机制将人的专业判断与系统的自动执行相结合，形成“人在回路决策、系统固化执行、策略跨会话复用”的闭环，是平台持续自我优化的重要基础。"),

      h2("4.6 数据流与可观测"),
      p("平台内置诊断全流程日志系统（DiagnosisLogger），按日期分目录、按会话写入 JSON 日志，记录内容包括："),
      bullet("前端完整输出（messages 列表）与时间线"),
      bullet("各阶段耗时（ai_planning、sub_agent_execution、compose_report 等）"),
      bullet("每个 SSE 事件的内容与时间戳"),
      bullet("各子智能体的调用耗时与成败状态"),
      p("该机制为系统调试、性能优化、审计追溯以及三层记忆机制中的知识记忆沉淀提供了完整的数据支撑。"),

      h1("五、持续演进方向"),
      p("平台当前已实现核心诊断能力，并在持续迭代中。后续将重点推进以下方向："),
      bullet("深化三层记忆机制，引入向量检索与历史案例推荐，提升复杂故障的研判效率。"),
      bullet("完善自演进机制，从人工保存技能升级为基于反馈轨迹的自动权重优化、案例库构建与策略推荐。"),
      bullet("扩展真实数据源接入，将覆冰、风偏、鸟害子智能体逐步从模拟数据迁移至真实业务系统。"),
      bullet("完善报告模板系统，支持 Word / PDF 等专业格式导出。"),
      bullet("引入前端组件测试与 Playwright 端到端测试，提升交付质量。"),
      bullet("加强配置外部化与安全加固，支持多用户隔离、认证授权与速率限制。"),
      bullet("优化报告生成阶段时延，通过提示工程与缓存策略进一步提升响应速度。"),

      new Paragraph({ children: [new TextRun("")] }),
      new Paragraph({
        children: [new TextRun({ text: "—— 本文档基于 PLDiagnosis 项目当前状态整理，具体实现以源码为准。", italics: true, font: "Arial", size: 18, color: "666666" })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 400 },
      }),
    ]
  }]
});

const outputPath = path.resolve('/Users/yfzx/Desktop/Cluade_PLDiagonsis-master/PLDiagnosis_部署与功能说明.docx');
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log('文档已生成:', outputPath);
});
