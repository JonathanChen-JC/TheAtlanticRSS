# The Atlantic Daily Brief RSS

这是一个自动化工具，用于抓取 The Atlantic 每日文章，生成中文综述，并以 RSS Feed 形式发布。

## 主要功能

- **文章抓取**：通过 `atlantic_rss_reader.py` 自动抓取 The Atlantic 每日文章
- **AI 综述生成**：使用 `gemini_summarizer.py` 调用 Google Gemini API 生成中文综述
- **RSS Feed 生成**：通过 `rss_generator.py` 生成标准 RSS Feed
- **自动同步**：使用 `github_sync.py` 自动将更新推送到 GitHub 仓库
- **持续运行**：通过 `keep_alive.py` 确保服务持续运行

## 项目结构

```
.
├── app.py                 # 主程序入口
├── atlantic_rss_reader.py # The Atlantic 文章抓取模块
├── gemini_summarizer.py   # Google Gemini AI 综述生成模块
├── rss_generator.py       # RSS Feed 生成模块
├── github_sync.py         # GitHub 自动同步模块
├── keep_alive.py          # 服务保活模块
├── articles/              # 原文存储目录
├── dailybrief/            # 综述存储目录
└── feed.xml               # 生成的 RSS Feed 文件
```

## 部署指南

1. 克隆仓库：
```bash
git clone https://github.com/your-username/AtlanticBriefRSS.git
cd AtlanticBriefRSS
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
- `GEMINI_API_KEY`：Google Gemini API 密钥
- `GITHUB_TOKEN`：GitHub 个人访问令牌（用于自动同步）

4. 运行服务：
```bash
python app.py
```

## 技术架构

- **文章抓取**：使用 Python 网络爬虫技术，自动获取 The Atlantic 每日更新的文章
- **AI 综述生成**：利用 Google Gemini API 进行文章摘要和翻译
- **RSS Feed**：使用 Python feedgen 库生成标准 RSS 2.0 格式的 Feed
- **自动化部署**：通过 GitHub Actions 实现自动化部署和更新

## 贡献指南

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/AmazingFeature`
3. 提交更改：`git commit -m 'Add some AmazingFeature'`
4. 推送分支：`git push origin feature/AmazingFeature`
5. 提交 Pull Request

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 致谢

- [The Atlantic](https://www.theatlantic.com/)
- [Google Gemini API](https://ai.google.dev/)
- 所有项目贡献者