#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import base64
import requests
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

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

# 从GIT_REPO_URL中提取仓库所有者和名称
repo_parts = GIT_REPO_URL.replace('https://github.com/', '').split('/')
if len(repo_parts) >= 2:
    REPO_OWNER = repo_parts[0]
    REPO_NAME = repo_parts[1].replace('.git', '')
else:
    raise ValueError("无法从GIT_REPO_URL解析仓库所有者和名称")


def get_remote_feed():
    """从GitHub API获取feed.xml内容"""
    try:
        # 构建API URL
        api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FEED_FILE}"
        
        # 设置请求头
        headers = {
            'Authorization': f'Bearer {GIT_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        logger.info(f"正在从GitHub API获取文件内容")
        response = requests.get(api_url, headers=headers)
        
        # 检查响应
        if response.status_code == 200:
            content_data = response.json()
            encoding = content_data.get("encoding")
            file_content_raw = content_data.get("content", "")

            if encoding == "base64":
                content = base64.b64decode(file_content_raw).decode("utf-8")
                logger.info(f"成功从GitHub获取文件: {FEED_FILE}")
                return content
            elif encoding == "none":
                # 如果编码是 'none'，通常意味着文件是空的。
                # GitHub API 在文件为空时，content 字段是空字符串 ""
                if file_content_raw == "":
                    logger.info(f"GitHub上的文件 {FEED_FILE} 为空 (编码: none, 内容: 空).")
                    return ""  # 返回空字符串代表空文件
                else:
                    # 这种情况理论上不常见，如果encoding是none但content非空
                    logger.error(f"文件 {FEED_FILE} 编码为 'none' 但内容非空，无法处理: {file_content_raw[:100]}...")
                    return None # 或者抛出异常，根据业务逻辑决定
            else:
                logger.error(f"不支持的编码: {encoding}")
                return None
        elif response.status_code == 404:
            logger.warning(f"GitHub上未找到文件: {FEED_FILE}")
            return None
        else:
            logger.error(f"获取GitHub文件失败，状态码: {response.status_code}, 响应: {response.text}")
        
        return None
    except Exception as e:
        logger.error(f"从GitHub获取文件时出错: {str(e)}")
        return None


def update_github_file(content, commit_message="Update feed.xml"):
    """更新GitHub上的文件"""
    try:
        # 构建API URL
        api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FEED_FILE}"
        
        # 设置请求头
        headers = {
            'Authorization': f'Bearer {GIT_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # 获取当前文件信息以获取SHA
        response = requests.get(api_url, headers=headers)
        
        # 准备更新数据
        update_data = {
            "message": commit_message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "branch": "main"  # 默认使用main分支
        }
        
        # 如果文件已存在，添加SHA
        if response.status_code == 200:
            file_sha = response.json()["sha"]
            update_data["sha"] = file_sha
        elif response.status_code != 404:
            logger.error(f"获取文件信息失败，状态码: {response.status_code}, 响应: {response.text}")
            return False
        
        # 发送更新请求
        response = requests.put(api_url, headers=headers, json=update_data)
        
        # 检查响应
        if response.status_code in [200, 201]:
            logger.info(f"成功更新GitHub文件: {FEED_FILE}")
            return True
        else:
            logger.error(f"更新GitHub文件失败，状态码: {response.status_code}, 响应: {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"更新GitHub文件时出错: {str(e)}")
        return False


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
    """同步本地更改到GitHub仓库"""
    try:
        # 读取本地文件内容
        local_feed = Path(FEED_FILE)
        if not local_feed.exists():
            logger.error(f"本地文件不存在: {FEED_FILE}")
            return False
            
        with open(local_feed, 'r', encoding='utf-8') as f:
            local_content = f.read()
        
        # 更新GitHub文件
        success = update_github_file(local_content, "Update feed.xml")
        
        if success:
            logger.info("成功同步到GitHub仓库")
        else:
            logger.error("同步到GitHub仓库失败")
        
        return success
    except Exception as e:
        logger.error(f"同步到GitHub仓库失败：{str(e)}")
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