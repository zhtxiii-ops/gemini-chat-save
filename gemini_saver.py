'''
Gemini Chat Saver - 保存 Google Gemini 对话到本地文件

支持 Markdown 格式，可过滤思考过程。
'''

from playwright.async_api import async_playwright
from markdownify import markdownify as md
import asyncio
import os
import re

__all__ = ['GeminiChatSaver', 'save_gemini']

class GeminiChatSaver:
    '''Google Gemini 对话保存器'''
    
    def __init__(self, include_thinking: bool = False):
        '''
        初始化保存器
        
        Args:
            include_thinking: 是否包含思考过程，默认不包含
        '''
        self.include_thinking = include_thinking
        self.browser = None
        self.context = None
        self.page = None
    
    async def start_browser(self):
        '''启动浏览器，使用用户数据目录以复用登录状态'''
        playwright = await async_playwright().start()
        
        # 使用用户的 Chrome 配置目录来复用登录状态
        user_data_dir = os.path.expanduser('~/Library/Application Support/Google/Chrome')
        
        # 检查是否存在 Chrome 用户数据
        if os.path.exists(user_data_dir):
            print('检测到 Chrome 用户数据，尝试复用登录状态...')
            try:
                self.context = await playwright.chromium.launch_persistent_context(
                    user_data_dir=os.path.expanduser('~/.gemini-saver-profile'),
                    headless=False,
                    channel='chrome',
                    args=['--disable-blink-features=AutomationControlled']
                )
                self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
            except Exception as e:
                print(f'复用 Chrome 配置失败: {e}')
                print('使用独立浏览器窗口，请手动登录...')
                self.browser = await playwright.chromium.launch(headless=False)
                self.context = await self.browser.new_context()
                self.page = await self.context.new_page()
        else:
            print('未检测到 Chrome 用户数据，使用独立浏览器窗口...')
            self.browser = await playwright.chromium.launch(headless=False)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
    
    async def close_browser(self):
        '''关闭浏览器'''
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
    
    async def navigate_to_chat(self, url: str) -> bool:
        '''
        导航到对话页面
        
        Args:
            url: Gemini 对话 URL
            
        Returns:
            是否成功加载对话
        '''
        print(f'正在打开: {url}')
        try:
            # 使用更宽松的等待策略，增加超时时间
            await self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await self.page.wait_for_timeout(3000)
        except Exception as e:
            print(f'页面加载出现问题: {e}')
            print('尝试继续...')
        
        # 检查是否需要登录
        login_required = await self.page.locator('text=\'登录\'').count() > 0 or \
                        await self.page.locator('text=\'Sign in\'').count() > 0
        
        if login_required:
            print('\n⚠️ 需要登录 Google 账号')
            print('请在浏览器中完成登录，登录后按 Enter 继续...')
            await asyncio.get_event_loop().run_in_executor(None, input)
            await self.page.wait_for_timeout(2000)
        
        # 等待对话内容加载
        try:
            await self.page.wait_for_selector('.conversation-container', timeout=60000)
            print('✓ 对话内容已加载')
            return True
        except Exception:
            print('✗ 未能加载对话内容，请检查 URL 是否正确')
            return False
    
    async def scroll_to_load_all(self) -> set:
        '''
        向上滚动加载所有历史消息，同时收集图片 URL
        
        Returns:
            收集到的所有图片 URL 集合
        '''
        print('正在加载所有对话内容...')
        
        prev_count = 0
        stable_rounds = 0
        max_stable_rounds = 3  # 连续3次数量不变则认为加载完成
        
        # 收集所有图片 URL
        all_image_urls = set()
        
        while stable_rounds < max_stable_rounds:
            # 获取当前对话数量
            curr_count = await self.page.locator('.conversation-container').count()
            
            # 收集当前可见的图片 URL
            current_urls = await self.page.evaluate('''
                () => {
                    const images = document.querySelectorAll('img[src*="googleusercontent.com/gg/"]');
                    return Array.from(images).map(img => img.src);
                }
            ''')
            for url in current_urls:
                all_image_urls.add(url)
            
            if curr_count == prev_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
                print(f'  已加载 {curr_count} 条对话...（已发现 {len(all_image_urls)} 张图片）')
            
            prev_count = curr_count
            
            # 滚动到顶部
            await self.page.evaluate('''
                const scroller = document.querySelector('infinite-scroller.chat-history');
                if (scroller) scroller.scrollTop = 0;
            ''')
            await self.page.wait_for_timeout(1000)
        
        # 滚动回底部，再收集一次可能遗漏的图片
        await self.page.evaluate('''
            const scroller = document.querySelector('infinite-scroller.chat-history');
            if (scroller) scroller.scrollTop = scroller.scrollHeight;
        ''')
        await self.page.wait_for_timeout(2000)
        
        # 再次收集图片
        final_urls = await self.page.evaluate('''
            () => {
                const images = document.querySelectorAll('img[src*="googleusercontent.com/gg/"]');
                return Array.from(images).map(img => img.src);
            }
        ''')
        for url in final_urls:
            all_image_urls.add(url)
        
        print(f'✓ 共加载 {prev_count} 条对话，发现 {len(all_image_urls)} 张图片')
        
        return all_image_urls
    
    async def download_images_via_playwright(self, image_urls: set, images_dir: str = None) -> dict:
        '''
        使用 Playwright 的请求上下文下载图片（会携带浏览器的 cookies）
        
        Args:
            image_urls: 图片 URL 集合
            images_dir: 图片保存目录
            
        Returns:
            图片 URL 到本地路径的映射字典
        '''
        if not image_urls:
            return {}
        
        import hashlib
        from pathlib import Path
        
        print(f'🖼️  正在下载 {len(image_urls)} 张图片...')
        
        image_map = {}
        images_path = Path(images_dir) if images_dir else None
        if images_path:
            images_path.mkdir(parents=True, exist_ok=True)
        
        for i, url in enumerate(image_urls):
            try:
                # 使用 Playwright 的 context.request 发送请求（携带 cookies）
                response = await self.context.request.get(url)
                
                if response.ok:
                    image_data = await response.body()
                    
                    # 确定文件扩展名
                    content_type = response.headers.get('content-type', 'image/jpeg')
                    ext = '.jpg'
                    if 'png' in content_type:
                        ext = '.png'
                    elif 'gif' in content_type:
                        ext = '.gif'
                    elif 'webp' in content_type:
                        ext = '.webp'
                    
                    # 生成文件名
                    url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
                    filename = f'gemini_img_{i+1:02d}_{url_hash}{ext}'
                    
                    if images_path:
                        filepath = images_path / filename
                        with open(filepath, 'wb') as f:
                            f.write(image_data)
                        image_map[url] = str(filepath)
                        print(f'  ✓ 已保存: {filename}')
                    else:
                        # 转换为 base64 data URL
                        import base64
                        b64 = base64.b64encode(image_data).decode('utf-8')
                        image_map[url] = f'data:{content_type};base64,{b64}'
                else:
                    print(f'  ⚠️ 下载失败 (HTTP {response.status}): {url[:50]}...')
            except Exception as e:
                print(f'  ⚠️ 下载出错: {e}')
        
        print(f'✓ 已下载 {len(image_map)} 张图片')
        
        return image_map
    
    async def extract_conversation(self) -> list:
        '''
        提取对话内容
        
        Returns:
            对话列表，每项包含 role (user/assistant) 和 content
        '''
        print('正在提取对话内容...')
        
        # 如果不包含思考过程，先移除思考内容
        if not self.include_thinking:
            await self.page.evaluate('''
                document.querySelectorAll('.thoughts-header, .thoughts-content, thought-response')
                    .forEach(el => el.style.display = 'none');
            ''')
        
        # 提取所有对话（获取 HTML 以保留格式）
        conversations = await self.page.evaluate('''
            () => {
                const result = [];
                const containers = document.querySelectorAll('.conversation-container');
                
                containers.forEach(container => {
                    // 提取用户问题
                    const userQuery = container.querySelector('user-query');
                    if (userQuery) {
                        const queryText = userQuery.innerText.trim();
                        if (queryText) {
                            result.push({ role: 'user', content: queryText });
                        }
                    }
                    
                    // 提取 AI 回复（使用 innerHTML 保留格式）
                    const modelResponse = container.querySelector('model-response');
                    if (modelResponse) {
                        // 克隆节点以避免修改原始 DOM
                        const clone = modelResponse.cloneNode(true);
                        
                        // 移除思考过程（如果需要）
                        clone.querySelectorAll('.thoughts-header, .thoughts-content, thought-response, .thoughts-container')
                            .forEach(el => el.remove());
                        
                        // 保留生成图像：将 image-button 内的 img 移动到其父级
                        clone.querySelectorAll('button.image-button').forEach(btn => {
                            const img = btn.querySelector('img');
                            if (img && img.src && img.src.includes('googleusercontent.com')) {
                                // 创建一个新的 img 元素放在 button 外面
                                const newImg = document.createElement('img');
                                newImg.src = img.src;
                                newImg.alt = img.alt || '生成的图像';
                                btn.parentNode.insertBefore(newImg, btn);
                            }
                        });
                        
                        // 移除不需要的 UI 元素（包括已处理的 image-button）
                        clone.querySelectorAll('button, .feedback-buttons, .response-actions, .copy-button, .code-block-actions')
                            .forEach(el => el.remove());
                        
                        // 获取 innerHTML 以保留格式
                        const responseHtml = clone.innerHTML.trim();
                        if (responseHtml) {
                            result.push({ role: 'assistant', content: responseHtml, isHtml: true });
                        }
                    }
                });
                
                return result;
            }
        ''')
        
        print(f'✓ 提取了 {len(conversations)} 条消息')
        return conversations
    
    def _html_to_markdown(self, html: str) -> str:
        '''
        将 HTML 转换为 Markdown 格式
        
        Args:
            html: HTML 内容
            
        Returns:
            Markdown 格式字符串
        '''
        # 使用 markdownify 转换
        markdown = md(
            html,
            heading_style='ATX',
            bullets='-',
            code_language='',
            strip=['script', 'style', 'svg']
        )
        
        # 清理多余的空行
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        
        return markdown.strip()
    
    def to_markdown(self, conversations: list, title: str = 'Gemini 对话') -> str:
        '''
        将对话转换为 Markdown 格式
        
        Args:
            conversations: 对话列表
            title: 文档标题
            
        Returns:
            Markdown 格式字符串
        '''
        lines = [f'# {title}\n']
        
        for conv in conversations:
            if conv['role'] == 'user':
                lines.append(f"## 🧑 用户\n\n{conv['content']}\n")
            else:
                # AI 回复需要从 HTML 转换为 Markdown
                content = conv['content']
                if conv.get('isHtml'):
                    content = self._html_to_markdown(content)
                lines.append(f"## 🤖 Gemini\n\n{content}\n")
        
        return '\n'.join(lines)
    
    
    async def get_markdown_content(self, url: str, images_dir: str = None):
        '''
        获取对话的 Markdown 内容
        
        Args:
            url: Gemini 对话 URL
            images_dir: 图片保存目录，如果提供则下载图片到本地
            
        Returns:
            Markdown 格式的对话内容
        '''
        try:
            await self.start_browser()
            
            if not await self.navigate_to_chat(url):
                return
            
            # 滚动加载所有对话，同时收集图片 URL
            collected_image_urls = await self.scroll_to_load_all()  # set of URLs
            
            # 使用 Playwright 下载图片
            image_map = {}
            if collected_image_urls:
                image_map = await self.download_images_via_playwright(collected_image_urls, images_dir)
            
            conversations = await self.extract_conversation()
            
            # 从页面 DOM 提取对话标题（比直接拿 `title` 更准确）
            chat_title = await self.page.evaluate('''
                () => {
                    // Gemini 的活动对话标题在顶部的 .conversation-title-container 中
                    const titleEl = document.querySelector('.conversation-title-container, .top-bar-actions .gds-title-m, [data-test-id="chat-title"]');
                    if (titleEl && titleEl.innerText) {
                        return titleEl.innerText.trim();
                    }
                    return document.title.replace(' - Google Gemini', '').replace(' - Gemini', '').trim();
                }
            ''')
            
            if not chat_title or chat_title in ('Gemini', 'Google Gemini', 'New chat'):
                chat_id = url.split('?')[0].rstrip('/').split('/')[-1]
                chat_title = f'Gemini_对话_{chat_id}'
            
            markdown_content = self.to_markdown(conversations, chat_title)
            
            # 替换 Markdown 中的图片链接
            if image_map:
                import re
                for original_url, new_path in image_map.items():
                    # 处理 Markdown 中的图片语法 ![alt](url)
                    # 匹配并替换 URL
                    pattern = re.escape(original_url)
                    markdown_content = re.sub(pattern, new_path, markdown_content)
            
            return markdown_content, chat_title
        finally:
            await self.close_browser()

def save_gemini(url: str, output_path: str):
    saver = GeminiChatSaver()
    markdown_content, title = asyncio.run(saver.get_markdown_content(url))
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    print(f'✓ Markdown 已保存到: {output_path}')
