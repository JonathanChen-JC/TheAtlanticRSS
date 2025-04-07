import os
import datetime
import pytz
from fastapi import FastAPI, Response
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import atlantic_rss_reader
import gemini_summarizer
import rss_generator
import github_sync
from contextlib import asynccontextmanager

# 创建FastAPI应用
app = FastAPI()

# 创建调度器
scheduler = AsyncIOScheduler()

# 获取北京时间
def get_beijing_time():
    beijing = pytz.timezone('Asia/Shanghai')
    return datetime.datetime.now(beijing)

# 主要任务流程
async def process_articles():
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
                    github_sync.main()
    except Exception as e:
        print(f"处理文章时出错: {str(e)}")

# FastAPI路由
@app.get("/feed.xml")
async def get_feed():
    try:
        with open(rss_generator.FEED_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content=content, media_type="application/xml")
    except Exception as e:
        print(f"读取feed.xml失败: {str(e)}")
        return Response(content="Feed not found", status_code=404)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 创建lifespan上下文管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行的初始化函数
    # 1. 初始化时同步feed.xml
    github_sync.main()
    
    # 2. 设置定时任务 - 每天北京时间中午12点执行
    scheduler.add_job(
        process_articles,
        CronTrigger(hour=12, minute=0, timezone=pytz.timezone('Asia/Shanghai'))
    )
    
    # 3. 设置保活任务 - 如果设置了URL，每5分钟ping一次
    ping_url = os.environ.get('PING_URL')
    if ping_url:
        import httpx
        async def ping_self():
            try:
                async with httpx.AsyncClient() as client:
                    await client.get(ping_url)
                    print(f"Successfully pinged {ping_url}")
            except Exception as e:
                print(f"Ping failed: {str(e)}")
        
        scheduler.add_job(
            ping_self,
            IntervalTrigger(minutes=5)
        )
    
    # 启动调度器
    scheduler.start()
    
    yield
    
    # 关闭时执行的清理函数
    scheduler.shutdown()

# 创建FastAPI应用并注册lifespan
app = FastAPI(lifespan=lifespan)

# 删除原有的@app.on_event装饰器函数