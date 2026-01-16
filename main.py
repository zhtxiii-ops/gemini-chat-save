#!/usr/bin/env python3
'''
主程序
'''

from gemini_saver import save_gemini
import argparse

def main():
    base_url = 'https://gemini.google.com'

    parser = argparse.ArgumentParser(
        description='保存 Google Gemini 对话到本地文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''
示例:
  %(prog)s {base_url}/app/xxx -o chat.md
  %(prog)s {base_url}/app/xxx --include-thinking -o chat.md
        '''
    )
    
    parser.add_argument('url', help='Gemini 对话 URL')
    parser.add_argument('-o', '--output', required=True, help='输出文件路径 (.md)')
    parser.add_argument('--include-thinking', action='store_true', 
                        help='包含思考过程（默认过滤）')
    
    args = parser.parse_args()
    
    # 验证 URL
    if not args.url.startswith(base_url):
        print(f'错误: URL 必须起始为 {base_url}')
        exit(1)
    
    save_gemini(args.url, args.output)

if __name__ == '__main__':
    main()
