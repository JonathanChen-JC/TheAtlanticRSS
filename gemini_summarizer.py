#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import datetime
import pytz
import requests
import logging
import sys
import argparse

# 设置日志
log_format = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
log_datefmt = '%Y-%m-%d %H:%M:%S %z'

# 配置根日志记录器
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt=log_datefmt,
    handlers=[
        # 标准输出处理器，确保日志在Render平台上可见
        logging.StreamHandler(sys.stdout)
    ]
)

# 设置模块日志记录器
logger = logging.getLogger("gemini_summarizer")
logger.setLevel(logging.INFO)

# 常量定义
ARTICLES_DIR = "articles"
DAILYBRIEF_DIR = "dailybrief"

# 从环境变量获取Gemini模型名称，如果未设置则使用默认值
DEFAULT_MODEL = "gemini-2.5-pro-exp-03-25"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


def ensure_dir_exists(directory):
    """确保目录存在，如果不存在则创建"""
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"创建目录: {directory}")


def get_beijing_time():
    """获取当前北京时间"""
    beijing = pytz.timezone('Asia/Shanghai')
    return datetime.datetime.now(beijing)


# 默认提示词模板
DEFAULT_PROMPT = """你是一位资深新闻编辑，请对这份The Atlantic的文章进行专业的综述。请遵循以下要求：

# 综述格式
1. 使用Markdown格式输出
2. 以'# The Atlantic 每日综述 - {日期}'作为标题
3. 每篇文章的综述使用二级标题(##)，保留原文标题
4. 在每篇文章综述下注明原文发布时间

# 内容要求
1. 准确提炼每篇文章的核心论点和关键信息
2. 突出重要的数据、引用和具体事实
3. 保持客观中立的叙述语气
4. 按照文章在原文中的顺序进行综述
5. 确保对每篇文章都进行完整的总结

# 注意事项
1. 直接输出综述内容，不要加入任何与综述无关的回应性语句
2. 保持专业的编辑视角，注重新闻价值的提炼
3. 适当保留原文的叙事结构和重要细节"""


def load_articles(date_str=None):
    """加载指定日期的文章，如果未指定日期则加载最新的文章"""
    try:
        # 如果未指定日期，使用当前美东时间的日期
        if not date_str:
            now = get_beijing_time()
            date_str = now.strftime("%Y%m%d")
        
        # 构建文件路径
        filepath = os.path.join(ARTICLES_DIR, f"{date_str}.md")
        
        # 检查文件是否存在
        if not os.path.exists(filepath):
            logger.error(f"文件不存在: {filepath}")
            return None
        
        # 加载并解析markdown文件
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        # 解析文章内容
        articles = []
        current_article = {}
        lines = content.split('\n')
        
        for line in lines:
            if line.startswith('## '):
                # 如果已有文章，保存它
                if current_article:
                    articles.append(current_article)
                # 开始新文章
                current_article = {'title': line[3:].strip()}
            elif line.startswith('*发布时间:'):
                current_article['publish_time'] = line[6:].strip()
            elif line.startswith('[原文链接]'):
                current_article['url'] = line[line.find('(')+1:line.find(')')]
            elif line.startswith('### 正文'):
                current_article['content'] = ''
            elif 'content' in current_article and line:
                current_article['content'] += line + '\n'
        
        # 添加最后一篇文章
        if current_article:
            articles.append(current_article)
            
        logger.info(f"从 {filepath} 加载了 {len(articles)} 篇文章")
        return articles
    except Exception as e:
        logger.error(f"加载文章失败: {str(e)}")
        return None


def call_gemini_api(api_key=None, prompt=None, articles=None):
    """调用Gemini API生成摘要"""
    try:
        # 如果未提供API密钥，从环境变量获取
        if api_key is None:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                logger.error("未提供API密钥且环境变量GEMINI_API_KEY未设置")
                return None
        
        # 构建请求数据
        # 修改API请求参数
        request_data = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"text": json.dumps(articles, ensure_ascii=False)}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,  # 降低温度以获得更稳定的输出
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 100000
            }
        }
        
        # 发送请求
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }
        
        # 获取当前的API URL（可能已被环境变量更新）
        current_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{os.environ.get('GEMINI_MODEL', GEMINI_MODEL)}:generateContent"
        
        response = requests.post(
            current_api_url,
            headers=headers,
            json=request_data
        )
        
        # 检查响应
        if response.status_code == 200:
            result = response.json()
            if "candidates" in result and len(result["candidates"]) > 0:
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                logger.info("成功生成摘要")
                return text
            else:
                logger.error(f"API响应中没有找到候选结果: {result}")
        else:
            logger.error(f"API请求失败，状态码: {response.status_code}, 响应: {response.text}")
        
        return None
    except Exception as e:
        logger.error(f"调用Gemini API失败: {str(e)}")
        return None


def save_daily_brief(content, date_str=None):
    """保存每日简报"""
    try:
        # 如果未指定日期，使用当前美东时间的日期
        if not date_str:
            now = get_beijing_time()
            date_str = now.strftime("%Y%m%d")
        
        # 确保目录存在
        ensure_dir_exists(DAILYBRIEF_DIR)
        
        # 构建文件路径
        filepath = os.path.join(DAILYBRIEF_DIR, f"{date_str}.md")
        
        # 保存简报
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info(f"简报已保存到 {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"保存简报失败: {str(e)}")
        return None


def generate_daily_brief(api_key=None, date_str=None):
    """生成每日简报"""
    # 使用默认提示词
    prompt = DEFAULT_PROMPT
    logger.info("使用默认提示词模板")
    
    # 如果未提供API密钥，尝试从环境变量获取
    if api_key is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("未提供API密钥且环境变量GEMINI_API_KEY未设置，无法生成简报")
            return False
        logger.info("使用环境变量中的GEMINI_API_KEY")
    
    # 加载文章
    logger.info(f"开始加载文章，日期: {date_str if date_str else '今天'}")
    articles = load_articles(date_str)
    if not articles:
        logger.error(f"文章加载失败，无法继续生成简报")
        return False
    logger.info(f"成功加载{len(articles)}篇文章")
    
    # 调用Gemini API
    logger.info(f"开始调用Gemini API生成摘要")
    summary = call_gemini_api(api_key, prompt, articles)
    if not summary:
        logger.error("Gemini API调用失败，无法生成摘要")
        return False
    logger.info("Gemini API调用成功，已获取摘要")
    
    # 保存简报
    logger.info(f"开始保存简报")
    filepath = save_daily_brief(summary, date_str)
    if not filepath:
        logger.error("简报保存失败")
        return False
    logger.info(f"简报已成功保存到: {filepath}")
    
    return True


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="使用Gemini API生成每日新闻简报")
    parser.add_argument("--api-key", help="Gemini API密钥，如果未提供则使用环境变量GEMINI_API_KEY")
    parser.add_argument("--date", help="指定日期 (YYYYMMDD格式)，默认为当天")
    parser.add_argument("--model", help="指定Gemini模型名称，如果未提供则使用环境变量GEMINI_MODEL或默认值")
    args = parser.parse_args()
    
    # 如果提供了模型名称，设置环境变量
    if args.model:
        os.environ["GEMINI_MODEL"] = args.model
        logger.info(f"使用命令行指定的模型: {args.model}")
    
    # 如果提供了API密钥，设置环境变量
    if args.api_key:
        os.environ["GEMINI_API_KEY"] = args.api_key
        logger.info("使用命令行提供的API密钥")
    
    # 确保目录存在
    ensure_dir_exists(DAILYBRIEF_DIR)
    
    # 生成每日简报
    success = generate_daily_brief(date_str=args.date)
    
    if success:
        logger.info("每日简报生成成功")
    else:
        logger.error("每日简报生成失败")


if __name__ == "__main__":
    main()