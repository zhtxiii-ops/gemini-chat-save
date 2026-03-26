#!/usr/bin/env python3
'''
Gemini to PDF - 直接从 Gemini 网页保存对话为 PDF

将 Gemini 对话页面一键转换为 PDF 文件，自动：
1. 从网页提取对话内容
2. 下载生成的图像到本地（在浏览器中完成，确保登录状态）
3. 转换为 Markdown
4. 生成 PDF

无需指定输出文件名，自动使用对话 ID 命名。
'''

import sys
import os
import argparse
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# 导入本地模块
from gemini_saver import GeminiChatSaver

# 导入 md2pdf 模块
sys.path.insert(0, '/Users/yhm/Documents/md2pdf')
from md2pdf import convert_md_to_pdf


def extract_title_from_url(url: str) -> str:
    '''从 URL 提取对话 ID 作为文件名'''
    chat_id = url.split('?')[0].rstrip('/').split('/')[-1]
    # 清理不能作为文件名的字符
    safe_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in chat_id)
    return safe_name


async def gemini_to_pdf(
    url: str,
    output_dir: str = None,
    include_thinking: bool = False,
    keep_md: bool = False
) -> str:
    '''
    从 Gemini 网页直接转换为 PDF
    
    Args:
        url: Gemini 对话 URL
        output_dir: 输出目录（默认为当前目录）
        include_thinking: 是否包含思考过程
        keep_md: 是否保留中间 Markdown 文件
    
    Returns:
        生成的 PDF 文件路径
    '''
    if output_dir is None:
        output_dir = os.getcwd()
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # URL 提取的名称仅作初始临时后备名称
    initial_base_name = extract_title_from_url(url)
    if len(initial_base_name) < 3:
        initial_base_name = f"gemini_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f'📥 正在从 Gemini 获取对话...')
    
    # 先使用临时目录存放图片
    temp_images_dir = Path(tempfile.gettempdir()) / f'{initial_base_name}_images'
    
    # 使用 GeminiChatSaver 获取 Markdown 内容（同时下载图片）
    saver = GeminiChatSaver(include_thinking=include_thinking)
    result = await saver.get_markdown_content(url, images_dir=str(temp_images_dir))
    
    if not result:
        print('✗ 无法获取对话内容')
        return None
        
    markdown_content, chat_title = result
    
    # 根据获取到的网页标题生成最终文件名
    base_name = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in chat_title).strip()
    base_name = base_name.replace(' ', '_')
    if len(base_name) < 3:
        base_name = initial_base_name
        
    print(f'📝 获取到对话标题: {chat_title}')
    
    # 确定最终图片目录和 markdown 文件路径
    if keep_md:
        final_images_dir = output_dir / f'{base_name}_images'
        
        # 将临时图片目录移动或覆盖到最终目录
        if temp_images_dir.exists():
            if final_images_dir.exists():
                shutil.rmtree(final_images_dir)
            shutil.move(str(temp_images_dir), str(final_images_dir))
            
        # 替换 markdown 内容中的临时图片路径为最终路径
        markdown_content = markdown_content.replace(str(temp_images_dir), str(final_images_dir))
        
        md_path = output_dir / f'{base_name}.md'
        images_dir_for_cleanup = None # 保留，不清理
    else:
        # 如果不保留 md，图片留在临时目录，转码完统一清理
        final_images_dir = temp_images_dir
        md_path = Path(tempfile.gettempdir()) / f'{base_name}.md'
        images_dir_for_cleanup = temp_images_dir
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    if keep_md:
        print(f'📝 Markdown 已保存: {md_path}')
    
    # 转换为 PDF
    pdf_path = output_dir / f'{base_name}.pdf'
    
    print(f'📄 正在生成 PDF...')
    
    try:
        result_pdf = convert_md_to_pdf(
            str(md_path),
            str(pdf_path)
        )
        print(f'✓ PDF 已保存: {result_pdf}')
        
        # 清理临时文件
        if not keep_md:
            os.unlink(md_path)
            if images_dir_for_cleanup and images_dir_for_cleanup.exists():
                shutil.rmtree(images_dir_for_cleanup)
        
        return result_pdf
    
    except Exception as e:
        print(f'✗ PDF 生成失败: {e}')
        return None


def main():
    base_url = 'https://gemini.google.com'
    
    parser = argparse.ArgumentParser(
        description='直接从 Gemini 网页保存对话为 PDF',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''
示例:
  %(prog)s {base_url}/app/xxx
  %(prog)s {base_url}/app/xxx -d ~/Documents
  %(prog)s {base_url}/app/xxx --keep-md
  %(prog)s {base_url}/app/xxx --include-thinking
        '''
    )
    
    parser.add_argument('url', help='Gemini 对话 URL')
    parser.add_argument('-d', '--dir', help='输出目录（默认为当前目录）')
    parser.add_argument('--keep-md', action='store_true', 
                        help='保留中间的 Markdown 文件和图片')
    parser.add_argument('--include-thinking', action='store_true', 
                        help='包含思考过程（默认过滤）')
    
    args = parser.parse_args()
    
    # 验证 URL
    if not args.url.startswith(base_url):
        print(f'错误: URL 必须起始为 {base_url}')
        sys.exit(1)
    
    # 运行异步任务
    result = asyncio.run(gemini_to_pdf(
        url=args.url,
        output_dir=args.dir,
        include_thinking=args.include_thinking,
        keep_md=args.keep_md
    ))
    
    if result:
        print(f'\n✅ 完成！')
        sys.exit(0)
    else:
        print(f'\n❌ 转换失败')
        sys.exit(1)


if __name__ == '__main__':
    main()
