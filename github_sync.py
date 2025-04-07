import os
import requests
from git import Repo
from pathlib import Path
import xml.etree.ElementTree as ET
import shutil

# 配置
GIT_REPO_URL = os.getenv('GIT_REPO_URL')
GIT_TOKEN = os.getenv('GIT_TOKEN')
if not GIT_REPO_URL or not GIT_TOKEN:
    raise ValueError("请设置GIT_REPO_URL和GIT_TOKEN环境变量")

FEED_FILE = 'feed.xml'
REPO_PATH = Path.cwd()

def setup_git_config():
    """设置Git配置"""
    try:
        repo = Repo(REPO_PATH)
        with repo.config_writer() as git_config:
            git_config.set_value("user", "name", "AtlanticBriefBot")
            git_config.set_value("user", "email", "bot@example.com")
        return repo
    except Exception as e:
        print(f"设置Git配置失败：{str(e)}")
        return None

def get_remote_feed():
    """从远程仓库获取feed.xml内容"""
    try:
        api_url = f"{GIT_REPO_URL.replace('github.com', 'api.github.com/repos')}/contents/{FEED_FILE}"
        headers = {'Authorization': f'token {GIT_TOKEN}'}
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        return response.json().get('content', '')
    except Exception as e:
        print(f"获取远程feed.xml失败：{str(e)}")
        return None

def compare_feeds(local_feed, remote_feed):
    """比较本地和远程的feed.xml"""
    try:
        local_tree = ET.parse(local_feed)
        remote_tree = ET.parse(remote_feed)
        
        local_items = local_tree.findall('.//item')
        remote_items = remote_tree.findall('.//item')
        
        return len(local_items) != len(remote_items)
    except Exception as e:
        print(f"比较feed.xml失败：{str(e)}")
        return True  # 如果无法比较，默认需要同步

def sync_to_repo():
    """同步到Git仓库"""
    try:
        repo = setup_git_config()
        if not repo:
            return
        
        # 添加更改
        repo.index.add([FEED_FILE])
        
        # 提交更改
        repo.index.commit("Update feed.xml")
        
        # 推送到远程
        origin = repo.remote()
        origin.push()
        
        print("成功同步到Git仓库")
    except Exception as e:
        print(f"同步到Git仓库失败：{str(e)}")

def update_rss_url():
    """更新RSS URL"""
    try:
        remote_feed = get_remote_feed()
        if not remote_feed:
            return
        
        # 解析远程feed中的RSS URL
        tree = ET.parse(remote_feed)
        channel = tree.find('channel')
        if channel is not None:
            link = channel.find('link')
            if link is not None and link.text:
                # 更新atlantic_rss_reader.py中的RSS_URL
                with open('atlantic_rss_reader.py', 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = re.sub(
                    r'RSS_URL = ".*"',
                    f'RSS_URL = "{link.text}"',
                    content
                )
                
                with open('atlantic_rss_reader.py', 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                print(f"RSS URL已更新为：{link.text}")
    except Exception as e:
        print(f"更新RSS URL失败：{str(e)}")

def main():
    """主函数"""
    try:
        print("开始Git同步操作")
        
        # 检查本地feed.xml是否存在
        local_feed = Path(FEED_FILE)
        if not local_feed.exists():
            print("本地feed.xml不存在，跳过同步")
            return
        
        # 获取远程feed.xml
        remote_feed = get_remote_feed()
        if remote_feed and compare_feeds(local_feed, remote_feed):
            sync_to_repo()
        
        # 更新RSS URL
        update_rss_url()
        
        print("Git同步操作完成")
    except Exception as e:
        print(f"程序运行出错：{str(e)}")

if __name__ == "__main__":
    main()