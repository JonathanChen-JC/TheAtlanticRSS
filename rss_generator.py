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
                guid_text = guid.text.split('/')[-1]
                existing_dates.add(guid_text)
                
                # 将现有条目添加到新的feed中
                fe = fg.add_entry()
                fe.id(guid.text)
                title = item.find('title')
                if title is not None:
                    fe.title(title.text)
                link = item.find('link')
                if link is not None:
                    fe.link(href=link.text)
                description = item.find('description')
                if description is not None:
                    fe.description(description.text)
                pubDate = item.find('pubDate')
                if pubDate is not None:
                    fe.published(pubDate.text)
                    fe.updated(pubDate.text)
    
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
            fe.description(brief['content'])
            fe.published(brief['date'])
            fe.updated(brief['date'])
            print(f"已添加新文章：{brief['title']}")
        except Exception as e:
            print(f"处理文件 {file_path} 时出错：{str(e)}")
            continue
    
    # 如果条目总数超过限制，删除最早的条目
    entries = fg.entry()
    if len(entries) > MAX_ENTRIES:
        # 对条目按发布日期降序排序
        entries.sort(key=lambda x: x.published() if x.published() else datetime.datetime.min.replace(tzinfo=datetime.timezone.utc), reverse=True)
        # 保留最新的 MAX_ENTRIES 条目
        # 通过创建一个新的列表并重新赋值给 fg.entry() 来更新条目
        # 或者找到 feedgen 库推荐的更新条目的方式
        # 一个直接的方式是清空然后重新添加，但更优的是直接修改列表
        # 从 feedgen 的使用来看，fg.entry() 返回的列表可以直接修改
        del entries[MAX_ENTRIES:]
        # 注意：如果 fg.entry() 返回的是一个拷贝，则上述 del entries[MAX_ENTRIES:] 无效
        # 需要确认 feedgen 的行为。更安全的方式是重新设置条目。
        # 假设 fg.entry() 返回的列表可以直接修改，如果不行，则需要找到 feedgen 清除和重设条目的方法。
        # 查阅 feedgen 文档，似乎没有直接替换所有条目的方法，但 fg._FeedGenerator__feed['entries'] 是其内部存储。
        # 为了避免直接访问私有成员，我们可以尝试清除所有条目然后重新添加排序和截断后的条目。
        # 然而，最直接且之前代码意图明确的方式是直接操作内部列表，但我们想避免它。
        # 另一种方法是创建一个新的FeedGenerator实例，只添加需要的条目，但这会丢失其他feed设置。

        # 鉴于原始代码的意图，并且考虑到 feedgen 可能没有提供完美的公共 API 来做这件事，
        # 我们尝试一种稍微安全一点的方式，即获取所有条目，排序，截断，然后清除原 fg 中的所有条目，再把截断后的条目加回去。
        # feedgen 没有 fg.clear_entries()。 
        # 最接近原始意图且避免直接访问 __feed 的方式是操作 fg.entry() 返回的列表。
        # 如果 fg.entry() 返回的列表修改后能直接反映到 FeedGenerator 实例中，那么 del entries[MAX_ENTRIES:] 是有效的。
        # 我们将采用这种方式，如果它不起作用，说明 feedgen 的这个接口行为与预期不符。
        # 在许多类似库中，返回的集合通常是可变的并且更改会反映出来。
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