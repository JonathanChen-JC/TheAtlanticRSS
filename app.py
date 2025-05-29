import os
import datetime
import pytz
from flask import Flask, Response
from flask_apscheduler import APScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import atlantic_rss_reader
import gemini_summarizer
import rss_generator
import github_sync
import httpx

# 创建Flask应用
app = Flask(__name__)

# 创建调度器
scheduler = APScheduler()
scheduler.init_app(app)

# 获取北京时间
def get_beijing_time():
    beijing = pytz.timezone('Asia/Shanghai')
    return datetime.datetime.now(beijing)

# 主要任务流程
def process_articles():
    try:
        # 1. 抓取文章
        rss_content = atlantic_rss_reader.fetch_rss_feed()
        if not rss_content:
            print("获取RSS内容失败")
            return
        
        entries = atlantic_rss_reader.parse_rss(rss_content)
        if not entries:
            print("解析RSS内容失败")
            return
        
        # 确保目录存在
        atlantic_rss_reader.setup_directory()
        
        # 获取今天的文件名
        today_file = atlantic_rss_reader.get_today_filename()
        
        # 保存文章
        articles_content = ""
        for entry in entries:
            # 获取文章内容
            article_content = atlantic_rss_reader.fetch_article_content(entry['link'])
            if article_content:
                articles_content += atlantic_rss_reader.format_article(entry) + "\n\n"
        
        # 保存到文件
        if articles_content:
            articles_path = os.path.join(atlantic_rss_reader.ARTICLES_DIR, today_file)
            with open(articles_path, 'w', encoding='utf-8') as f:
                f.write(articles_content)
            print(f"文章已保存到: {articles_path}")
            
            # 2. 生成综述
            articles = gemini_summarizer.load_articles()
            if articles:
                summary = gemini_summarizer.call_gemini_api(prompt=gemini_summarizer.DEFAULT_PROMPT, articles=articles)
                if summary:
                    gemini_summarizer.save_daily_brief(summary)
                    
                    # 3. 更新RSS feed
                    fg = rss_generator.generate_feed()
                    rss_generator.save_feed(fg)
                    
                    # 4. 同步到Git仓库
                    github_sync.sync_feed_to_github() # <--- 修改这里
    except Exception as e:
        print(f"处理文章时出错: {str(e)}")

# Flask路由
@app.route("/feed.xml")
def get_feed():
    try:
        with open(rss_generator.FEED_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content, mimetype="application/xml")
    except Exception as e:
        print(f"读取feed.xml失败: {str(e)}")
        return Response("Feed not found", status=404)

@app.route("/health")
def health_check():
    return {"status": "ok"}

# 初始化函数
def init_app():
    # 1. 初始化时同步feed.xml
    github_sync.sync_feed_to_github() # <--- 修改这里
    
    # 2. 设置定时任务 - 每天北京时间中午12点执行
    scheduler.add_job(
        id='process_articles',
        func=process_articles,
        trigger=CronTrigger(hour=12, minute=0, timezone=pytz.timezone('Asia/Shanghai'))
    )
    
    # 3. 设置保活任务 - 如果设置了URL，每5分钟ping一次
    ping_url = os.environ.get('PING_URL')
    if ping_url:
        def ping_self():
            try:
                with httpx.Client() as client:
                    client.get(ping_url)
                    print(f"Successfully pinged {ping_url}")
            except Exception as e:
                print(f"Ping failed: {str(e)}")
        
        scheduler.add_job(
            id='ping_self',
            func=ping_self,
            trigger=IntervalTrigger(minutes=5)
        )

# 初始化应用
init_app()
# 启动调度器
scheduler.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)