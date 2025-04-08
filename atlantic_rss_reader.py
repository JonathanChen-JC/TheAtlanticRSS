import os
import datetime
import time
import requests
import xml.etree.ElementTree as ET
import html
import re
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from datetime import timezone
from zoneinfo import ZoneInfo

# RSS源URL
RSS_URL = "https://www.theatlantic.com/feed/all/"

# 文章保存目录
ARTICLES_DIR = "articles"

def setup_directory():
    """确保articles目录存在"""
    if not os.path.exists(ARTICLES_DIR):
        os.makedirs(ARTICLES_DIR)
        print(f"创建目录: {ARTICLES_DIR}")

def get_today_filename():
    """生成当天的文件名，格式为YYYYMMDD"""
    today = datetime.datetime.now()
    return today.strftime("%Y%m%d") + ".md"

def fetch_rss_feed():
    """获取RSS源内容"""
    try:
        print(f"正在获取RSS源: {RSS_URL}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, application/atom+xml, text/xml, */*'
        }
        response = requests.get(RSS_URL, headers=headers, timeout=10, verify=True)
        response.raise_for_status()
        print(f"RSS源响应状态码: {response.status_code}")
        print(f"RSS源响应头: {dict(response.headers)}")
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"获取RSS源失败: {str(e)}")
        print(f"详细错误信息: {repr(e)}")
        return None
    except Exception as e:
        print(f"获取RSS源时发生未知错误: {str(e)}")
        print(f"详细错误信息: {repr(e)}")
        return None

def get_last_build_date():
    """从feed.xml获取上次构建时间(GMT+0)"""
    try:
        if not os.path.exists('feed.xml'):
            return None
        tree = ET.parse('feed.xml')
        root = tree.getroot()
        last_build_date = root.find('.//lastBuildDate')
        if last_build_date is not None and last_build_date.text:
            return parsedate_to_datetime(last_build_date.text)
        return None
    except Exception as e:
        print(f"获取lastBuildDate失败: {str(e)}")
        return None

def parse_rss(xml_content):
    """解析RSS XML内容"""
    try:
        # 获取上次构建时间
        last_build_date = get_last_build_date()
        print(f"上次构建时间: {last_build_date}")
        
        # 解析XML
        root = ET.fromstring(xml_content)
        
        # 获取Atom命名空间
        namespaces = {'atom': 'http://www.w3.org/2005/Atom'}
        
        # 查找所有entry元素
        entries = []
        items = root.findall('.//atom:entry', namespaces)
        
        print(f"找到 {len(items)} 个文章条目")
        
        for item in items:
            entry = {}
            
            # 提取标题
            title_elem = item.find('atom:title', namespaces)
            if title_elem is not None:
                entry['title'] = title_elem.get('type') == 'html' and html.unescape(title_elem.text) or title_elem.text
            else:
                entry['title'] = '无标题'
            
            # 提取链接
            link_elem = item.find("atom:link[@rel='alternate']", namespaces)
            if link_elem is not None:
                entry['link'] = link_elem.get('href')
            else:
                entry['link'] = '#'
            
            # 提取发布日期
            published_elem = item.find('atom:published', namespaces)
            if published_elem is not None and published_elem.text:
                # 将ET时间转换为GMT+0时间进行比较
                et_time = datetime.datetime.fromisoformat(published_elem.text.replace('Z', '+00:00'))
                et_time = et_time.astimezone(ZoneInfo('America/New_York'))
                gmt_time = et_time.astimezone(timezone.utc)
                
                # 只保留比lastBuildDate新的文章
                if last_build_date is None or gmt_time > last_build_date:
                    entry['published'] = published_elem.text
                else:
                    continue
            else:
                entry['published'] = '未知日期'
            
            # 提取摘要
            summary_elem = item.find('atom:summary', namespaces)
            if summary_elem is not None:
                entry['summary'] = summary_elem.get('type') == 'html' and html.unescape(summary_elem.text) or summary_elem.text
            else:
                entry['summary'] = '无摘要'
            
            entries.append(entry)
        
        print(f"解析到 {len(entries)} 篇文章")
        return entries
    except Exception as e:
        print(f"解析RSS内容失败: {str(e)}")
        print(f"详细错误信息: {repr(e)}")
        return []

def clean_html(html_text):
    """清理HTML标签"""
    # 简单的HTML标签清理
    clean_text = re.sub(r'<[^>]+>', '', html_text)
    # 解码HTML实体
    clean_text = html.unescape(clean_text)
    return clean_text

def fetch_article_content(url):
    """从文章URL获取正文内容"""
    try:
        # 添加延迟以避免请求过于频繁
        time.sleep(3)
        
        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # 发送请求获取页面内容
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 查找文章正文容器 - 尝试多个可能的选择器
        article_container = None
        selectors = [
            ('div', {'class_': 'article-body'}),
            ('div', {'class_': 'article-content'}),
            ('article', {}),
            ('div', {'class_': 'article'})
        ]
        
        for tag, attrs in selectors:
            article_container = soup.find(tag, attrs)
            if article_container:
                break
        
        if not article_container:
            print(f"无法找到文章容器: {url}")
            return None
        
        # 提取文章标题
        title = soup.find('h1')
        title_text = title.get_text().strip() if title else ''
        
        # 提取作者信息
        author = soup.find('a', class_='byline')
        author_text = author.get_text().strip() if author else ''
        
        # 提取发布日期
        date = soup.find('time')
        date_text = date.get_text().strip() if date else ''
        
        # 提取文章内容，包括更多的HTML元素
        content_elements = article_container.find_all(['p', 'h2', 'h3', 'h4', 'blockquote', 'ul', 'ol'])
        
        # 处理列表元素
        processed_elements = []
        for element in content_elements:
            if element.name in ['ul', 'ol']:
                list_items = element.find_all('li')
                list_text = '\n'.join(f"- {item.get_text().strip()}" for item in list_items)
                processed_elements.append(list_text)
            else:
                text = element.get_text().strip()
                if text:  # 只添加非空文本
                    processed_elements.append(text)
        
        # 组合所有内容
        full_content = []
        if title_text:
            full_content.append(f"# {title_text}\n")
        if author_text or date_text:
            full_content.append(f"作者: {author_text} | 发布时间: {date_text}\n")
        full_content.extend(processed_elements)
        
        return '\n\n'.join(full_content)
        
    except requests.exceptions.RequestException as e:
        print(f"请求文章失败 {url}: {str(e)}")
        return None
    except Exception as e:
        print(f"获取文章内容失败 {url}: {str(e)}")
        print(f"详细错误信息: {repr(e)}")
        return None

def format_article(entry):
    """将RSS条目格式化为Markdown"""
    title = entry.get('title', '无标题')
    link = entry.get('link', '#')
    published = entry.get('published', '未知日期')
    summary = entry.get('summary', '无摘要')
    
    # 清理HTML标签
    clean_summary = clean_html(summary)
    
    # 获取文章正文
    content = fetch_article_content(link)
    if content:
        article_body = f"### 正文\n\n{content}"
    else:
        article_body = ""
    
    # 格式化为Markdown
    markdown = f"## {title}\n\n"
    markdown += f"*发布时间: {published}*\n\n"
    markdown += f"[原文链接]({link})\n\n"
    markdown += f"{clean_summary}\n\n"
    markdown += f"{article_body}\n\n"
    markdown += "---\n\n"
    
    return markdown

def save_articles_to_file(articles_markdown):
    """将文章保存到当天的Markdown文件"""
    if not articles_markdown:
        print("没有文章需要保存")
        return
    
    filename = os.path.join(ARTICLES_DIR, get_today_filename())
    today_date = datetime.datetime.now().strftime("%Y年%m月%d日")
    
    header = f"# The Atlantic 每日文章 - {today_date}\n\n"
    content = header + articles_markdown
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"文章已保存到: {filename}")
    except Exception as e:
        print(f"保存文件失败: {str(e)}")

def process_feed():
    """处理RSS源并保存文章"""
    setup_directory()
    xml_content = fetch_rss_feed()
    
    if not xml_content:
        return
    
    entries = parse_rss(xml_content)
    
    all_articles = ""
    for entry in entries:
        article_markdown = format_article(entry)
        all_articles += article_markdown
    
    save_articles_to_file(all_articles)

def main():
    try:
        print("开始运行 Atlantic RSS 阅读器")
        process_feed()
        print("运行完成")
    except Exception as e:
        print(f"程序运行出错: {str(e)}")

if __name__ == "__main__":
    main()