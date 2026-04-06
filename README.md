# Rio Toolbox 1.0

Rio Toolbox 是一个**多功能个人工具箱 Web 应用**，集成了日常任务管理、AI 对话助手、随机数生成、美食选择、运势签语、日历管理、OCR 文字识别等多种实用功能。本项目旨在提供轻量、快速体验的个人日常助理解决方案。

## 🌟 核心特性

- ✅ **任务管理系统** - 区分每日任务与临时任务，支持智能 AI 分析优先级
- 🤖 **AI 对话助手** - 接入 SiliconFlow API，支持多角色预设、记忆处理及自定义角色卡设定
- 🎲 **随机小工具** - 随机数生成器与午餐吃什么（美食推荐）
- 🔮 **运势签语** - 每日限定一次的抽签系统与温馨文案
- 📅 **日历与提醒** - 支持重复循环的事件记录，精准计算重要日期倒数
- 📄 **OCR 识别翻译** - 支持多格式图片甚至 PDF 识别（依赖 Tesseract），无缝连接 AI 翻译
- 🎨 **毛玻璃渐变 UI** - 现代化界面，支持四套渐变主题无缝切换

## 🛠️ 技术栈

**后端：**
- **Python 3.13+**
- **FastAPI** + **Uvicorn** - 高性能异步 Web 架构
- **httpx** - 高效的异步 HTTP 请求
- **Pillow** & **pytesseract** & **pypdfium2** - 核心图像及 PDF 处理与 OCR 识别功能

**前端：**
- **原生 HTML/CSS/JavaScript** - 极致轻量化，无框架依赖
- **Marked.js** - AI Markdown 对话渲染
- 动态毛玻璃和高斯模糊设计，原生深色模式及主题支持

## 🚀 部署与运行

### 1. 环境准备
- 确保已安装 **Python 3.13+**。
- 如果需要使用 OCR 功能，必须在系统内安装并配置好 **Tesseract OCR** 并将其添加至系统环境变量 `PATH` 中：[Tesseract 下载](https://github.com/UB-Mannheim/tesseract/wiki)

### 2. 下载及安装依赖
克隆本项目到本地，然后运行依赖安装：

```bash
git clone https://github.com/yourusername/rio-toolbox.git
cd rio-toolbox
pip install -r requirements.txt
```

### 3. 一键启动
在 Windows 平台上，您可以直接双击运行：
```bash
start_toolbox.bat
```
或者在终端中手动启动 FastAPI 服务：
```bash
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8888
```
随后请在浏览器中打开：[http://127.0.0.1:8888](http://127.0.0.1:8888)

### 4. AI 助手配置
在首次使用对话及 AI 分析功能时：
1. 请先前往工作台的 `/ai-chat`（AI 对话页面）。
2. 点击右上角的齿轮设置。
3. 填入您的 `SiliconFlow API` 信息：
   - **API URL Base**: `https://api.siliconflow.cn/v1`
   - **API Key**: 你的专属密钥
   - **Model**: `deepseek-ai/DeepSeek-V3` （或其他兼容模型）

## 📁 目录结构

```text
rio-toolbox/
├── backend/                  # FastAPI 核心处理层、数据库驱动（JSON）
│   ├── server.py             # 核心路由入口
│   ├── storage.py            # 数据状态及配置存储逻辑
│   ├── ocr_utils.py          # 图像及文件解析工具
│   └── data/                 # 自动生成，存储所有日程、对话记录和任务
├── frontend/                 # 纯原生前台 UI 页面
│   ├── index.html            # 主页导航
│   └── assets/               # CSS、JS 以及相关静态图片及角色立绘
├── requirements.txt          # Python 依赖清单
├── start_toolbox.bat         # Windows 版一键启动脚本
└── README.md                 # 项目介绍
```

## ⚠️ 注意事项
1. **数据存储模式**：本项目奉行极简主义，无需额外部署 MySQL / Redis，所有数据和配置均写入 `backend/data/toolbox.json` 中，请妥善备份该文件。
2. **多模态文件清理**：所有上传的识别图片以及 AI 角色卡将存储在 `backend/uploads/` 中。

## 📜 许可证

[MIT License](LICENSE)
