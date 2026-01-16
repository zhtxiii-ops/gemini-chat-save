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
    
    async def scroll_to_load_all(self):
        '''向上滚动加载所有历史消息'''
        print('正在加载所有对话内容...')
        
        prev_count = 0
        stable_rounds = 0
        max_stable_rounds = 3  # 连续3次数量不变则认为加载完成
        
        while stable_rounds < max_stable_rounds:
            # 获取当前对话数量
            curr_count = await self.page.locator('.conversation-container').count()
            
            if curr_count == prev_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
                print(f'  已加载 {curr_count} 条对话...')
            
            prev_count = curr_count
            
            # 滚动到顶部
            await self.page.evaluate('''
                const scroller = document.querySelector('infinite-scroller.chat-history');
                if (scroller) scroller.scrollTop = 0;
            ''')
            await self.page.wait_for_timeout(1000)
        
        print(f'✓ 共加载 {prev_count} 条对话')
    
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
                        
                        // 移除不需要的 UI 元素
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
    
    
    async def get_markdown_content(self, url: str):
        '''
        保存对话到文件
        
        Args:
            url: Gemini 对话 URL
            output_path: 输出文件路径
        '''
        try:
            await self.start_browser()
            
            if not await self.navigate_to_chat(url):
                return
            
            await self.scroll_to_load_all()
            
            conversations = await self.extract_conversation()
            
            # 从 URL 提取对话 ID 作为标题的一部分
            chat_id = url.split('/')[-1]
            title = f'Gemini 对话 ({chat_id})'
            
            markdown_content = self.to_markdown(conversations, title)
            
            return markdown_content
        finally:
            await self.close_browser()

def save_gemini(url: str, output_path: str):
    saver = GeminiChatSaver()
    markdown_content = asyncio.run(saver.get_markdown_content(url))
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    print(f'✓ Markdown 已保存到: {output_path}')
