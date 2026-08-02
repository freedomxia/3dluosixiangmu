---
name: 皓月 3D 需求解析
description: 像建模检验台一样直接、清楚、可追踪的单任务工具
colors:
  primary: "#1f5eff"
  primary-deep: "#1748c7"
  primary-soft: "#edf3ff"
  ink: "#171a1f"
  ink-soft: "#5c6572"
  surface: "#ffffff"
  surface-subtle: "#f5f7fa"
  page: "#e9edf2"
  line: "#d5dbe4"
  line-strong: "#b9c2ce"
  success: "#087a55"
  danger: "#a8342a"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "clamp(27px, 3.1vw, 40px)"
    fontWeight: 720
    lineHeight: 1.05
    letterSpacing: "-0.035em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: 1.4
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "22px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
    height: "42px"
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
  work-surface:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
---

# Design System: 皓月 3D 需求解析

## Overview

**Creative North Star: "建模检验台"**

界面是一条安静但精密的数字生产线。它不模仿聊天窗口，也不把功能分散成仪表盘卡片；一张需求图进入，经过可见的固定工序，在同一条纵向工作流中先变成可审查提示词，再由用户确认是否生成结果图。

视觉表达服务于“输入—解析—验收”这条最短路径。中性灰白工作面提供长时间阅读所需的稳定性，皓月蓝只标识操作、当前工序和已通过结果；细线、编号、对位标记和紧凑的状态条来自建模打样与质量检查语言。

**Key Characteristics:**

- 单任务、单向生产线、明确的输入与输出关系
- 克制的中性工作面与稀缺的皓月蓝
- 结构性分隔代替漂浮卡片堆叠
- 状态变化清楚；普通任务不暴露模型参数，部署连接集中在独立配置工位
- 提示词审查、人工确认与结果图共享一个任务上下文
- 历史记录是同页辅助轨道，不是独立页面或仪表盘
- 任务可转入后台继续执行，上传工位立即恢复；历史轨道同时承担任务切换和状态回看
- 完成结果可进入修改态：沿用原图或替换新版图1，编辑补充要求后生成新的历史任务

## Colors

采用“中性工作台 + 单一品牌操作色”的克制策略。

### Primary

- **皓月工艺蓝**：只用于主操作、焦点、当前工序和通过状态；悬停时加深，不扩张使用面积。

### Neutral

- **冷白工作面**：页面主背景，保持图片和长文本判断不受色偏影响。
- **雾灰工位**：输入、空态和次级区域。
- **石墨文字**：正文与核心数据。
- **标尺灰**：边界、分隔、序号和非当前状态。

**The Blue Means Action Rule.** 蓝色只表示可操作或已确认状态，不作为大面积装饰背景。

## Typography

**Display Font:** 系统中文无衬线字体
**Body Font:** 系统中文无衬线字体
**Label/Mono Font:** 系统等宽字体

**Character:** 中文信息必须清楚、紧凑、没有品牌字体加载依赖。等宽字体只用于步骤编号、状态和技术性小标签，正文保持自然阅读。

### Hierarchy

- **Display**（720，`clamp(27px, 3.1vw, 40px)`，1.05）：只用于初始任务标题，不承担营销口号。
- **Headline**（700，18px，1.35）：区域名称和当前动作。
- **Title**（700，14–18px）：结果模块与折叠项。
- **Body**（400，14px，1.6）：说明、提示词和错误信息。
- **Label**（700，11px，等宽）：步骤号、文件信息、校验状态。

**The Task Language Rule.** 标题描述用户正在做的事，不使用抽象概念或模型术语。

## Layout

桌面端采用 16:9 居中单屏工作台：最左侧固定历史任务轨道，中间需求图、补充要求和主按钮构成持续可见的输入工位，右侧是提示词与结果工位。提交后不得切换为独立处理页，也不得折叠或隐藏需求图；五步工序只以紧凑状态条出现在右侧输出区上方，通过审查的提示词直接替换右侧占位内容。正向提示词、负面提示词、解析详情和结果图在同一结果工位切换，确认提示词后才进入结果图生成。“服务配置”进入同一工作面上的独立配置工位。

移动端沿用同一顺序，只压缩间距与操作尺寸，不改变信息结构，也不使用横向滚动。移动端允许必要的纵向滚动，不通过压小字号换取伪单屏。间距遵循少量稳定步长，密度由区域用途决定，不把每个信息块都包成独立卡片。

## Elevation & Depth

系统以边界、色阶和局部内嵌层次表达深度。默认不使用漂浮大阴影；只有拖拽上传、弹出复制反馈或移动端底部操作条进入交互状态时出现短促、克制的抬升。

**The Work Surface Rule.** 默认区域属于同一张工作面，阴影不能把流程切割成互不相关的卡片集合。

## Shapes

大容器采用克制的小圆角，上传区与结果图保留更明显但仍精确的圆角。按钮与标签不使用胶囊造型；边界保持连续，关键角点可加入小型对位标记。

## Components

### Primary Button

- **Shape:** 精确小圆角（8px），桌面高度 42px。
- **Color:** 皓月工艺蓝底、白字；禁用态降低整体不透明度，不更换含义色。
- **State:** 悬停只做一次轻微上移与颜色加深；焦点使用清楚的蓝色外环。

### Upload Surface

- **Shape:** 12px 圆角和 1px 虚线边界。
- **State:** 拖入时边界转蓝、工作面变为浅蓝并短暂抬升；选图后改为实线并展示真实预览。

### Result Tabs

- **Structure:** 正向提示词、负面提示词、解析详情和结果图共用一个结果工位；正向提示词为默认页签。
- **State:** 当前页签只使用蓝色文字与 2px 下划线；支持键盘左右方向键切换。

### Prompt Viewer

- **Structure:** 正向与负向提示词各自拥有固定标题、复制操作和内部滚动文本面。
- **State:** 复制成功通过短暂文字反馈和状态提示确认，不移动内容。
- **Approval:** 正向提示词下方保留独立确认区；只有提示词已通过审查且 PixPark 可用时显示“确认提示词，开始生图”。

### Status Rail

- **Structure:** 识别需求、组装规则、审查提示词、人工确认、生成结果图五个固定阶段。
- **State:** 当前阶段使用蓝色，完成阶段使用绿色，同时保留文字标签。

### History Rail

- **Structure:** 桌面端固定在工作台左侧，不提供收起或关闭开关；小屏幕上始终显示并排在主工作台上方。按更新时间列出临时保留期内任务，可回看需求图、提示词与结果图。
- **Privacy:** 原图与任务元数据只保存于服务器私有运行目录，任务取消或 TTL 到期时清理，不构成永久项目库。
- **State:** 当前记录清楚标记“待确认”“生图中”“已完成”或“未完成”，不能伪装成永久项目库。
- **Concurrency:** 处理中选择“另起一个任务”只解除当前工位绑定，不取消后台任务；点击任一进行中记录可回到其当前阶段。

### Revision Context

- **Entry:** 结果工位的“修改需求”是明确入口，不与“重新生成提示词”或“重新生成结果图”混为一谈。
- **Editing:** 输入工位恢复补充要求编辑；原图默认沿用，重新选择图片时明确替换为新版图1。
- **History:** 提交修改时创建新的任务编号，来源任务及其提示词、结果图继续保留；取消修改返回来源任务。

### Service Configuration Station

- **Structure:** 模型连接和 PixPark 分成两个连续字段组，状态条同时显示模型、固定图2和 PixPark 是否就绪。
- **Secrets:** 密钥输入永远为空；已存在时只显示“已配置”，留空表示保留，清除必须通过独立勾选显式执行。
- **Scope:** 只允许部署级连接配置，不出现温度、Token 上限、重试次数等普通任务参数。

## Do's and Don'ts

### Do:

- **Do** 让上传动作在首屏成为唯一视觉主动作。
- **Do** 保持需求图、结果图和提示词之间的来源关系可见。
- **Do** 让解析进度留在输出工位内，处理期间始终保留左侧需求图和补充要求。
- **Do** 用明确文字同时表达状态，不能只改变颜色。
- **Do** 为长提示词提供舒适阅读、一键复制和收起详情。
- **Do** 让生图成为提示词审查之后的显式人工动作。

### Don't:

- **Don't** 把页面做成聊天机器人、营销落地页或多卡片仪表盘。
- **Don't** 在上传任务里展示模型、温度、Token 上限或重试参数；部署连接只能进入独立配置工位。
- **Don't** 用渐变光晕、玻璃拟态或无功能装饰代替真实结果内容。
- **Don't** 伪造结果图、处理时间、客户数据或模型能力。
- **Don't** 在解析完成后自动消耗 PixPark 配额。
- **Don't** 点击“开始解析”后跳转、替换或伪装成独立进度页面。
