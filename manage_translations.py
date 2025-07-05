#!/usr/bin/env python3
"""
翻译管理脚本
用于管理Auto-Limit的多语言翻译文件
"""

import os
import sys
import subprocess
import argparse

def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"执行: {description}")
    print(f"命令: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✓ 成功")
        if result.stdout:
            print(result.stdout)
    else:
        print("✗ 失败")
        if result.stderr:
            print(result.stderr)
        sys.exit(1)
    print("-" * 50)

def extract_messages():
    """提取需要翻译的消息"""
    cmd = "pybabel extract -F babel.cfg -k _ -o messages.pot ."
    run_command(cmd, "提取翻译字符串")

def update_translations():
    """更新翻译文件"""
    cmd = "pybabel update -i messages.pot -d app/translations"
    run_command(cmd, "更新翻译文件")

def compile_translations():
    """编译翻译文件"""
    cmd = "pybabel compile -d app/translations"
    run_command(cmd, "编译翻译文件")

def init_language(language):
    """初始化新语言"""
    cmd = f"pybabel init -i messages.pot -d app/translations -l {language}"
    run_command(cmd, f"初始化{language}语言")

def main():
    parser = argparse.ArgumentParser(description="Auto-Limit翻译管理工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 提取命令
    subparsers.add_parser('extract', help='提取需要翻译的字符串')
    
    # 更新命令
    subparsers.add_parser('update', help='更新现有翻译文件')
    
    # 编译命令
    subparsers.add_parser('compile', help='编译翻译文件')
    
    # 初始化命令
    init_parser = subparsers.add_parser('init', help='初始化新语言')
    init_parser.add_argument('language', help='语言代码 (如: en, zh, fr)')
    
    # 完整流程命令
    subparsers.add_parser('all', help='执行完整的翻译流程 (extract -> update -> compile)')
    
    args = parser.parse_args()
    
    if args.command == 'extract':
        extract_messages()
    elif args.command == 'update':
        update_translations()
    elif args.command == 'compile':
        compile_translations()
    elif args.command == 'init':
        init_language(args.language)
    elif args.command == 'all':
        extract_messages()
        update_translations()
        compile_translations()
        print("🎉 翻译管理完成！")
    else:
        parser.print_help()

if __name__ == '__main__':
    main() 