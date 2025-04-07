# The Atlantic Daily Brief RSS

## 项目简介

这是一个自动化工具，用于抓取 The Atlantic 的每日文章，使用 Google Gemini AI 生成中文综述，并将其转换为 RSS Feed 格式。项目支持自动同步到 GitHub 仓库，并提供服务保活功能。

## 主要功能

- 自动抓取 The Atlantic 每日文章
- 使用 Google Gemini AI 生成中文综述
- 生成 RSS Feed
- 自动同步到 GitHub 仓库
- 服务保活机制

## 项目结构

```
.
├── app.py                 # 主程序入口
├── atlantic_rss_reader.py # The Atlantic 文章抓取模块
├── gemini_summarizer.py   # Google Gemini AI 综述生成模块
├── rss_generator.py       # RSS Feed 生成模块
├── github_sync.py         # GitHub 自动同步模块
├── articles/              # 原文存储目录
├── dailybrief/           # 综述存储目录
└── feed.xml              # 生成的 RSS Feed 文件
```

## 部署指南

### 1. 环境准备

- Python 3.8 或更高版本
- Git
- Google Gemini API 密钥
- GitHub 个人访问令牌

### 2. 安装步骤

1. 克隆仓库：
```bash
git clone https://github.com/your-username/AtlanticBriefRSS.git
cd AtlanticBriefRSS
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

### 3. 环境变量配置

#### 必需的环境变量

| 环境变量 | 说明 | 示例 |
|----------|------|------|
| `GEMINI_API_KEY` | Google Gemini API 密钥，用于调用 AI 生成文章综述 | `your-api-key` |
| `GIT_TOKEN` | GitHub 个人访问令牌，用于自动同步更新到仓库 | `ghp_xxxxxxxxxxxx` |
| `GIT_REPO_URL` | GitHub 仓库地址，用于自动同步代码 | `https://github.com/username/AtlanticBriefRSS` |

#### 可选的环境变量

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `GEMINI_MODEL` | Gemini 模型名称 | `gemini-2.5-pro-exp-03-25` |
| `PING_URL` | 服务保活 URL，用于定期发送心跳请求 | 无 |

### 4. 运行服务

```bash
python app.py
```

## 使用说明

1. 服务启动后会自动执行以下任务：
   - 定时抓取 The Atlantic 最新文章
   - 使用 Gemini AI 生成中文综述
   - 更新 RSS Feed
   - 同步到 GitHub 仓库

2. RSS Feed 访问：
   - 订阅地址：`https://raw.githubusercontent.com/your-username/AtlanticBriefRSS/main/feed.xml`

## 注意事项

1. 确保所有必需的环境变量都已正确配置
2. GitHub 个人访问令牌需要有仓库读写权限
3. 建议将服务部署在稳定的环境中运行
4. 如果使用 `PING_URL`，确保 URL 可以正常访问

## 许可证

MIT License