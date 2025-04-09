#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import base64
import requests
from git import Repo
from pathlib import Path
import xml.etree.ElementTree as ET
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # 确保日志在Render平台上可见
    ]
)

# 配置模块日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 配置
GIT_REPO_URL = os.getenv('GIT_REPO_URL', '')
GIT_TOKEN = os.getenv('GIT_TOKEN', '')
FEED_FILE = 'feed.xml'
REPO_PATH = Path.cwd()

# 验证环境变量
if not GIT_REPO_URL.strip():
    raise ValueError("GIT_REPO_URL环境变量未设置或为空")
if not GIT_TOKEN.strip():
    raise ValueError("GIT_TOKEN环境变量未设置或为空")
if not GIT_REPO_URL.startswith('https://github.com/'):
    raise ValueError("GIT_REPO_URL必须是有效的GitHub仓库URL")

# 构建包含token的Git URL
GIT_AUTH_URL = GIT_REPO_URL.replace('https://', f'https://{GIT_TOKEN}@')

def setup_git_config():
    """设置Git配置"""
    try:
        logger.info(f"正在初始化Git仓库：{REPO_PATH}")
        repo = Repo(REPO_PATH)
        
        try:
            origin = repo.remote()
            logger.info(f"当前远程仓库URL：{origin.url}")
        except ValueError:
            logger.info("未找到远程仓库，正在添加...")
            origin = repo.create_remote('origin', GIT_AUTH_URL)
        
        if origin.url != GIT_AUTH_URL:
            logger.info("更新远程仓库URL")
            origin.set_url(GIT_AUTH_URL)
        
        config = repo.config_writer()
        config.set_value('user', 'name', 'AtlanticBriefBot')
        config.set_value('user', 'email', 'bot@example.com')
        config.release()
        
        return repo
    except Exception as e:
        logger.error(f"设置Git配置失败：{str(e)}")
        return None

def get_remote_feed():
    """从GitHub API获取feed.xml内容"""
    try:
        api_url = f"{GIT_REPO_URL.replace('github.com', 'api.github.com/repos')}/contents/{FEED_FILE}"
        headers = {
            'Authorization': f'Bearer {GIT_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        logger.info(f"正在从GitHub API获取文件内容")
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        
        content = response.json().get('content', '')
        if not content:
            logger.error("API响应中没有找到content字段")
            return None
        
        return base64.b64decode(content).decode('utf-8')
    except requests.exceptions.RequestException as e:
        logger.error(f"GitHub API请求失败：{str(e)}")
        return None
    except Exception as e:
        logger.error(f"获取远程feed.xml失败：{str(e)}")
        return None

def parse_build_date(xml_content, is_file=False):
    """解析XML中的lastBuildDate"""
    try:
        if is_file:
            tree = ET.parse(xml_content)
            root = tree.getroot()
        else:
            root = ET.fromstring(xml_content)
        
        build_date = root.find('.//lastBuildDate')
        if build_date is None or not build_date.text:
            return None
        
        return datetime.strptime(build_date.text, '%a, %d %b %Y %H:%M:%S %z')
    except (ET.ParseError, ValueError) as e:
        logger.error(f"解析lastBuildDate失败：{str(e)}")
        return None

def compare_feeds(local_feed, remote_feed):
    """比较本地和远程feed的lastBuildDate"""
    logger.info("开始比较本地和远程feed文件")
    
    local_date = parse_build_date(local_feed, is_file=True)
    remote_date = parse_build_date(remote_feed)
    
    if local_date is None and remote_date is None:
        logger.warning("无法解析两个文件的lastBuildDate")
        return 'local'
    elif local_date is None:
        logger.info("本地文件日期无法解析，使用远程文件")
        return 'remote'
    elif remote_date is None:
        logger.info("远程文件日期无法解析，使用本地文件")
        return 'local'
    
    if local_date > remote_date:
        logger.info("本地feed更新，使用本地文件")
        return 'local'
    elif remote_date > local_date:
        logger.info("远程feed更新，使用远程文件")
        return 'remote'
    else:
        logger.info("feed的lastBuildDate相同，无需更改")
        return 'same'

def sync_to_repo():
    """同步本地更改到Git仓库"""
    try:
        repo = setup_git_config()
        if not repo:
            return False
        
        if not repo.git.status(porcelain=True):
            logger.info("没有需要同步的更改")
            return True
        
        repo.index.add([FEED_FILE])
        commit = repo.index.commit("Update feed.xml")
        logger.info(f"创建提交：{commit.hexsha}")
        
        origin = repo.remote()
        push_info = origin.push()
        
        for info in push_info:
            if info.flags & info.ERROR:
                logger.error(f"推送失败：{info.summary}")
                return False
        
        logger.info("成功同步到Git仓库")
        return True
    except Exception as e:
        logger.error(f"同步到Git仓库失败：{str(e)}")
        return False

def main():
    """主函数"""
    try:
        logger.info("开始Git同步操作")
        local_feed = Path(FEED_FILE)
        
        # 处理本地文件不存在或为空的情况
        if not local_feed.exists() or local_feed.stat().st_size == 0:
            remote_feed = get_remote_feed()
            if remote_feed:
                with open(local_feed, 'w', encoding='utf-8') as f:
                    f.write(remote_feed)
                logger.info("已从远程仓库获取并创建本地文件")
            else:
                logger.error("无法获取远程feed内容，同步操作终止")
                return
        
        # 获取远程feed内容并比较
        remote_feed = get_remote_feed()
        if not remote_feed:
            logger.error("无法获取远程feed内容，同步操作终止")
            return
        
        result = compare_feeds(local_feed, remote_feed)
        if result == 'remote':
            with open(local_feed, 'w', encoding='utf-8') as f:
                f.write(remote_feed)
            logger.info("已更新本地文件")
        elif result == 'local':
            sync_to_repo()
        
        logger.info("Git同步操作完成")
    except Exception as e:
        logger.error(f"同步操作失败：{str(e)}")

if __name__ == "__main__":
    main()