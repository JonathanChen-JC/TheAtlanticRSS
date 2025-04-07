import os
import datetime
from pathlib import Path
from feedgen.feed import FeedGenerator
import markdown
import re
from xml.etree import ElementTree as ET

# 配置
DAILYBRIEF_DIR = Path('dailybrief')
FEED_FILE = 'feed.xml'
MAX_ENTRIES = 50

def setup_feed_generator():
    """初始化FeedGenerator"""
    fg = FeedGenerator()
    fg.id('https://www.theatlantic.com/')
    fg.title('The Atlantic Daily Brief')
    fg.author({'name': 'The Atlantic Brief Generator'})
    fg.link(href='https://www.theatlantic.com/', rel='alternate')
    fg.description('Daily summaries of The Atlantic articles')
    fg.language('zh')
    return fg

def get_brief_files():
    """获取所有综述文件，按日期排序"""
    if not DAILYBRIEF_DIR.exists():
        return []
    
    files = [f for f in DAILYBRIEF_DIR.glob('*.md') if f.stem.isdigit()]
    return sorted(files, reverse=True)  # 最新的文件排在前面

def parse_brief_content(file_path):
    """解析综述文件内容"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取标题和日期
    title_match = re.search(r'# The Atlantic 每日综述 - (.*?)\n', content)
    title = title_match.group(1) if title_match else '未知日期'
    
    # 将Markdown转换为HTML
    html_content = markdown.markdown(content)
    
    # 创建带时区的datetime对象
    date = datetime.datetime.strptime(file_path.stem, '%Y%m%d')
    date = date.replace(hour=0, minute=0, second=0)
    date = date.replace(tzinfo=datetime.timezone.utc)  # 设置为UTC时区
    
    return {
        'title': f'The Atlantic 每日综述 - {title}',
        'content': html_content,
        'date': date
    }

def load_existing_feed():
    """加载已存在的feed文件"""
    if not os.path.exists(FEED_FILE):
        return None
    try:
        tree = ET.parse(FEED_FILE)
        root = tree.getroot()
        # 获取所有item元素并按发布时间排序
        items = root.findall('.//item')
        items.sort(key=lambda x: x.find('pubDate').text if x.find('pubDate') is not None else '', reverse=True)
        return items
    except Exception as e:
        print(f"读取现有feed文件失败：{str(e)}")
        return None

def get_entry_date(entry):
    """从feed entry中获取发布日期"""
    return entry.find('pubDate').text if entry.find('pubDate') is not None else ''

def generate_feed():
    """生成RSS feed"""
    fg = setup_feed_generator()
    existing_items = load_existing_feed()
    existing_dates = set()
    
    # 如果存在现有条目，先添加它们
    if existing_items:
        for item in existing_items:
            guid = item.find('guid')
            if guid is not None:
                existing_dates.add(guid.text.split('/')[-1])
    
    brief_files = get_brief_files()
    if not brief_files:
        if not existing_items:
            print("没有找到任何综述文件")
        return fg
    
    # 添加新的条目
    for file_path in brief_files:
        try:
            # 如果文件已经在feed中，跳过
            if file_path.stem in existing_dates:
                continue
                
            brief = parse_brief_content(file_path)
            fe = fg.add_entry()
            fe.id(f'https://www.theatlantic.com/daily-brief/{file_path.stem}')
            fe.title(brief['title'])
            fe.link(href=f'https://www.theatlantic.com/daily-brief/{file_path.stem}')
            fe.content(brief['content'], type='html')
            fe.published(brief['date'])
            fe.updated(brief['date'])
            print(f"已添加新文章：{brief['title']}")
        except Exception as e:
            print(f"处理文件 {file_path} 时出错：{str(e)}")
            continue
    
    # 如果条目总数超过限制，删除最早的条目
    entries = fg.entry()
    if len(entries) > MAX_ENTRIES:
        entries.sort(key=lambda x: x.published(), reverse=True)
        fg._FeedGenerator__feed['entries'] = entries[:MAX_ENTRIES]
        print(f"已限制feed条目数量为{MAX_ENTRIES}条")
    
    return fg

def save_feed(fg):
    """保存RSS feed到文件"""
    try:
        fg.rss_file(FEED_FILE, pretty=True)
        print(f"RSS feed已保存到：{FEED_FILE}")
    except Exception as e:
        print(f"保存RSS feed失败：{str(e)}")

def main():
    """主函数"""
    try:
        print("开始生成RSS feed")
        fg = generate_feed()
        save_feed(fg)
        print("RSS feed生成完成")
    except Exception as e:
        print(f"程序运行出错：{str(e)}")

if __name__ == "__main__":
    main()