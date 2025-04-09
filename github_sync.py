import os
import base64
import requests
from git import Repo
from pathlib import Path
import xml.etree.ElementTree as ET
import shutil
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 配置
GIT_REPO_URL = os.getenv('GIT_REPO_URL', '')
GIT_TOKEN = os.getenv('GIT_TOKEN', '')

# 验证环境变量
if not GIT_REPO_URL.strip():
    raise ValueError("GIT_REPO_URL环境变量未设置或为空")
if not GIT_TOKEN.strip():
    raise ValueError("GIT_TOKEN环境变量未设置或为空")
if not GIT_REPO_URL.startswith('https://github.com/'):
    raise ValueError("GIT_REPO_URL必须是有效的GitHub仓库URL")

FEED_FILE = 'feed.xml'
REPO_PATH = Path.cwd()

def setup_git_config():
    """设置Git配置"""
    try:
        logging.info(f"正在初始化Git仓库：{REPO_PATH}")
        repo = Repo(REPO_PATH)
        
        # 验证远程仓库配置
        try:
            origin = repo.remote()
            logging.info(f"当前远程仓库URL：{origin.url}")
        except ValueError:
            logging.info("未找到远程仓库，正在添加...")
            origin = repo.create_remote('origin', GIT_REPO_URL)
        
        # 更新远程URL（如果需要）
        if origin.url != GIT_REPO_URL:
            logging.info(f"更新远程仓库URL：{GIT_REPO_URL}")
            origin.set_url(GIT_REPO_URL)
        
        # 设置Git配置
        config = repo.config_writer()
        config.set_value('user', 'name', 'AtlanticBriefBot')
        config.set_value('user', 'email', 'bot@example.com')
        config.set_value('credential.helper', 'store')
        config.release()  # 确保配置被保存
        
        return repo
    except Exception as e:
        logging.error(f"设置Git配置失败：{str(e)}")
        return None

def get_remote_feed():
    """从远程仓库获取feed.xml内容"""
    try:
        api_url = f"{GIT_REPO_URL.replace('github.com', 'api.github.com/repos')}/contents/{FEED_FILE}"
        headers = {
            'Authorization': f'token {GIT_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        logging.info(f"正在从API获取文件：{api_url}")
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        
        content = response.json().get('content', '')
        if not content:
            logging.error("API响应中没有找到content字段")
            return None
            
        # 解码Base64内容
        try:
            decoded_content = base64.b64decode(content).decode('utf-8')
            return decoded_content
        except Exception as decode_error:
            logging.error(f"Base64解码失败：{str(decode_error)}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"API请求失败：{str(e)}")
        if hasattr(e.response, 'status_code'):
            logging.error(f"HTTP状态码：{e.response.status_code}")
        if hasattr(e.response, 'text'):
            logging.error(f"响应内容：{e.response.text}")
        return None
    except Exception as e:
        logging.error(f"获取远程feed.xml时发生未知错误：{str(e)}")
        return None

def compare_feeds(local_feed, remote_feed):
    """比较本地和远程的feed.xml的lastBuildDate来决定使用哪个文件"""
    try:
        logging.info("开始比较本地和远程feed文件的lastBuildDate")
        
        # 解析本地文件
        try:
            local_tree = ET.parse(local_feed)
            local_build_date = local_tree.find('.//lastBuildDate')
            if local_build_date is None:
                logging.error("本地feed.xml中未找到lastBuildDate标签")
                return 'remote'
            logging.info(f"本地feed的lastBuildDate: {local_build_date.text}")
        except ET.ParseError as e:
            logging.error(f"解析本地feed.xml失败：{str(e)}")
            return 'remote'
        
        # 解析远程内容
        try:
            remote_tree = ET.fromstring(remote_feed)
            remote_build_date = remote_tree.find('.//lastBuildDate')
            if remote_build_date is None:
                logging.error("远程feed.xml中未找到lastBuildDate标签")
                return 'local'
            logging.info(f"远程feed的lastBuildDate: {remote_build_date.text}")
        except ET.ParseError as e:
            logging.error(f"解析远程feed.xml失败：{str(e)}")
            return 'local'
        
        # 比较lastBuildDate
        from datetime import datetime
        local_date = datetime.strptime(local_build_date.text, '%a, %d %b %Y %H:%M:%S %z')
        remote_date = datetime.strptime(remote_build_date.text, '%a, %d %b %Y %H:%M:%S %z')
        
        if local_date > remote_date:
            logging.info("本地feed更新，使用本地文件")
            return 'local'
        elif remote_date > local_date:
            logging.info("远程feed更新，使用远程文件")
            return 'remote'
        else:
            logging.info("feed的lastBuildDate相同，无需更改")
            return 'same'
    except Exception as e:
        logging.error(f"比较feed.xml时发生未知错误：{str(e)}")
        return 'local'  # 如果无法比较，默认使用本地文件

def sync_to_repo():
    """同步到Git仓库"""
    try:
        repo = setup_git_config()
        if not repo:
            logging.error("Git配置失败，无法继续同步")
            return
        
        # 检查文件状态
        status = repo.git.status(porcelain=True)
        if not status:
            logging.info("没有需要同步的更改")
            return
        
        logging.info(f"检测到以下更改：\n{status}")
        
        # 添加更改
        repo.index.add([FEED_FILE])
        logging.info(f"已添加文件到暂存区：{FEED_FILE}")
        
        # 提交更改
        commit = repo.index.commit("Update feed.xml")
        logging.info(f"已创建提交：{commit.hexsha}")
        
        # 推送到远程
        origin = repo.remote()
        try:
            push_info = origin.push()
            for info in push_info:
                if info.flags & info.ERROR:
                    logging.error(f"推送失败：{info.summary}")
                    return
            logging.info("成功同步到Git仓库")
        except Exception as push_error:
            logging.error(f"推送到远程仓库失败：{str(push_error)}")
            return
    except Exception as e:
        logging.error(f"同步到Git仓库失败：{str(e)}")
        if hasattr(e, 'stderr'):
            logging.error(f"Git错误信息：{e.stderr}")

def update_rss_url():
    """更新RSS URL"""
    try:
        logging.info("开始更新RSS URL")
        remote_feed = get_remote_feed()
        if not remote_feed:
            logging.error("无法获取远程feed内容，跳过RSS URL更新")
            return
        
        # 解析远程feed中的RSS URL
        try:
            tree = ET.fromstring(remote_feed)
            channel = tree.find('channel')
            if channel is None:
                logging.error("未找到channel标签")
                return
                
            link = channel.find('link')
            if link is None or not link.text:
                logging.error("未找到有效的link标签")
                return
                
            rss_url = link.text
            logging.info(f"从feed中获取到RSS URL：{rss_url}")
            
            # 更新atlantic_rss_reader.py中的RSS_URL
            reader_path = 'atlantic_rss_reader.py'
            if not os.path.exists(reader_path):
                logging.error(f"文件不存在：{reader_path}")
                return
                
            with open(reader_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import re
            new_content = re.sub(
                r'RSS_URL = ".*"',
                f'RSS_URL = "{rss_url}"',
                content
            )
            
            if new_content == content:
                logging.info("RSS URL无需更新")
                return
                
            with open(reader_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            logging.info(f"RSS URL已更新为：{rss_url}")
            
        except ET.ParseError as e:
            logging.error(f"解析远程feed失败：{str(e)}")
        except Exception as e:
            logging.error(f"更新RSS URL时发生错误：{str(e)}")
    except Exception as e:
        logging.error(f"更新RSS URL过程中发生未知错误：{str(e)}")

def main():
    """主函数"""
    try:
        logging.info("开始Git同步操作")
        
        # 检查本地feed.xml是否存在
        local_feed = Path(FEED_FILE)
        if not local_feed.exists():
            logging.warning("本地feed.xml不存在，跳过同步")
            return
            
        # 检查文件大小
        if local_feed.stat().st_size == 0:
            logging.error("本地feed.xml为空文件")
            return
        
        # 获取远程feed.xml
        remote_feed = get_remote_feed()
        if not remote_feed:
            logging.error("无法获取远程feed内容，同步操作终止")
            return
            
        # 比较文件并决定使用哪个
        result = compare_feeds(local_feed, remote_feed)
        if result == 'remote':
            logging.info("使用远程feed.xml更新本地文件")
            with open(local_feed, 'w', encoding='utf-8') as f:
                f.write(remote_feed)
        elif result == 'local':
            logging.info("使用本地feed.xml更新远程文件")
            sync_to_repo()
        else:
            logging.info("本地和远程feed.xml内容一致，无需更新")
        
        # 更新RSS URL
        update_rss_url()
        
        logging.info("Git同步操作完成")
    except Exception as e:
        logging.error(f"程序运行出错：{str(e)}")
        if hasattr(e, '__traceback__'):
            import traceback
            logging.error(f"错误详情：\n{traceback.format_exc()}")

if __name__ == "__main__":
    main()