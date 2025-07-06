#!/usr/bin/env python3
"""
翻译管理脚本
用于管理Auto-Limit的多语言翻译文件
"""

import os
import sys
import subprocess
import argparse
import re
from pathlib import Path

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

def parse_po_file(po_file_path):
    """解析po文件，返回已翻译和未翻译的条目"""
    if not os.path.exists(po_file_path):
        print(f"警告: po文件不存在: {po_file_path}")
        return [], []
    
    with open(po_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    translated = []
    untranslated = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 查找msgid行
        if line.startswith('msgid '):
            # 提取msgid内容
            msgid_content = ""
            msgid_line = line[6:].strip()  # 去掉"msgid "
            
            # 处理msgid（可能跨多行）
            if msgid_line.startswith('"') and msgid_line.endswith('"'):
                msgid_content = msgid_line[1:-1]  # 去掉首尾双引号
                # 处理转义字符
                msgid_content = msgid_content.replace('\\"', '"').replace('\\\\', '\\')
            
            # 检查下一行是否是msgid的继续
            i += 1
            while i < len(lines) and lines[i].strip().startswith('"'):
                continuation = lines[i].strip()
                if continuation.startswith('"') and continuation.endswith('"'):
                    cont_content = continuation[1:-1]
                    # 处理转义字符
                    cont_content = cont_content.replace('\\"', '"').replace('\\\\', '\\')
                    msgid_content += cont_content
                i += 1
            
            # 查找对应的msgstr
            msgstr_content = ""
            while i < len(lines) and not lines[i].strip().startswith('msgstr '):
                i += 1
            
            if i < len(lines) and lines[i].strip().startswith('msgstr '):
                msgstr_line = lines[i].strip()[7:].strip()  # 去掉"msgstr "
                
                # 处理msgstr（可能跨多行）
                if msgstr_line.startswith('"') and msgstr_line.endswith('"'):
                    msgstr_content = msgstr_line[1:-1]  # 去掉首尾双引号
                    # 处理转义字符
                    msgstr_content = msgstr_content.replace('\\"', '"').replace('\\\\', '\\')
                
                # 检查下一行是否是msgstr的继续
                i += 1
                while i < len(lines) and lines[i].strip().startswith('"'):
                    continuation = lines[i].strip()
                    if continuation.startswith('"') and continuation.endswith('"'):
                        cont_content = continuation[1:-1]
                        # 处理转义字符
                        cont_content = cont_content.replace('\\"', '"').replace('\\\\', '\\')
                        msgstr_content += cont_content
                    i += 1
            
            # 跳过空的msgid
            if msgid_content.strip():
                if msgstr_content.strip():  # 如果msgstr不为空，说明已翻译
                    translated.append((msgid_content, msgstr_content))
                else:  # 如果msgstr为空，说明未翻译
                    untranslated.append(msgid_content)
        else:
            i += 1
    
    return translated, untranslated

def parse_pot_file(pot_file_path):
    """解析pot模板文件，提取所有需要翻译的字符串"""
    if not os.path.exists(pot_file_path):
        print(f"警告: pot文件不存在: {pot_file_path}")
        return []
    
    with open(pot_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    msgids = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 查找msgid行
        if line.startswith('msgid '):
            # 提取msgid内容
            msgid_content = ""
            msgid_line = line[6:].strip()  # 去掉"msgid "
            
            # 处理msgid（可能跨多行）
            if msgid_line.startswith('"') and msgid_line.endswith('"'):
                msgid_content = msgid_line[1:-1]  # 去掉首尾双引号
                # 处理转义字符
                msgid_content = msgid_content.replace('\\"', '"').replace('\\\\', '\\')
            
            # 检查下一行是否是msgid的继续
            i += 1
            while i < len(lines) and lines[i].strip().startswith('"'):
                continuation = lines[i].strip()
                if continuation.startswith('"') and continuation.endswith('"'):
                    cont_content = continuation[1:-1]
                    # 处理转义字符
                    cont_content = cont_content.replace('\\"', '"').replace('\\\\', '\\')
                    msgid_content += cont_content
                i += 1
            
            # 跳过空的msgid
            if msgid_content.strip():
                msgids.append(msgid_content)
        else:
            i += 1
    
    return msgids

def add_untranslated_entries(po_file_path, untranslated_entries):
    """将未翻译的条目添加到po文件末尾"""
    if not untranslated_entries:
        print("没有未翻译的条目需要添加")
        return
    
    # 读取现有po文件内容
    with open(po_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 在文件末尾添加未翻译条目
    with open(po_file_path, 'w', encoding='utf-8') as f:
        f.write(content.rstrip())
        f.write('\n\n# 新增待翻译条目\n')
        for msgid in untranslated_entries:
            # 正确转义双引号和反斜杠（先转义反斜杠，再转义双引号）
            escaped_msgid = msgid.replace('\\', '\\\\').replace('"', '\\"')
            f.write(f'\nmsgid "{escaped_msgid}"\nmsgstr ""\n')
    
    print(f"已添加 {len(untranslated_entries)} 个未翻译条目到 {po_file_path}")

def clean_invalid_entries(po_file_path, valid_msgids):
    """清理po文件中的无效条目"""
    if not os.path.exists(po_file_path):
        return
    
    with open(po_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    cleaned_lines = []
    removed_count = 0
    skip_next = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if skip_next:
            skip_next = False
            i += 1
            continue
            
        # 检查是否是可疑的msgid行
        if line.strip().startswith('msgid '):
            msgid_line = line.strip()[6:].strip()  # 去掉"msgid "
            
            # 检查是否是以反斜杠+双引号结尾的不完整条目
            if msgid_line.endswith('\\"') and not msgid_line.startswith('"'):
                # 这是一个可疑的不完整条目
                msgid_content = msgid_line[1:-2] if msgid_line.startswith('"') else msgid_line[:-2]
                
                # 检查这个msgid是否在有效列表中
                if msgid_content not in valid_msgids:
                    # 跳过这个条目和下一行的msgstr
                    removed_count += 1
                    # 查找并跳过对应的msgstr行
                    j = i + 1
                    while j < len(lines) and not lines[j].strip().startswith('msgstr '):
                        j += 1
                    if j < len(lines):
                        i = j + 1  # 跳过msgstr行
                    else:
                        i += 1
                    continue
            
            # 检查是否是其他类型的可疑条目（比如只有反斜杠结尾）
            elif msgid_line.endswith('\\"') or msgid_line.endswith('\\'):
                # 提取内容进行检查
                if msgid_line.startswith('"') and msgid_line.endswith('"'):
                    msgid_content = msgid_line[1:-1]
                elif msgid_line.startswith('"'):
                    msgid_content = msgid_line[1:]
                else:
                    msgid_content = msgid_line
                
                # 检查是否在有效列表中
                if msgid_content not in valid_msgids:
                    # 跳过这个条目
                    removed_count += 1
                    # 查找并跳过对应的msgstr行
                    j = i + 1
                    while j < len(lines) and not lines[j].strip().startswith('msgstr '):
                        j += 1
                    if j < len(lines):
                        i = j + 1  # 跳过msgstr行
                    else:
                        i += 1
                    continue
        
        cleaned_lines.append(line)
        i += 1
    
    # 如果有清理操作，重写文件
    if removed_count > 0:
        with open(po_file_path, 'w', encoding='utf-8') as f:
            f.writelines(cleaned_lines)
        print(f"已清理 {removed_count} 个无效条目")

def process_untranslated():
    """处理未翻译的条目"""
    print("🔍 正在分析未翻译的条目...")
    
    # 确保先有最新的pot文件
    extract_messages()
    
    # 解析pot文件获取所有需要翻译的字符串
    pot_file = "messages.pot"
    all_msgids = set(parse_pot_file(pot_file))
    
    if not all_msgids:
        print("没有找到需要翻译的字符串")
        return
    
    print(f"在pot文件中找到 {len(all_msgids)} 个需要翻译的字符串")
    
    # 处理每个语言的po文件
    translations_dir = Path("app/translations")
    if not translations_dir.exists():
        print("翻译目录不存在")
        return
    
    for lang_dir in translations_dir.iterdir():
        if lang_dir.is_dir():
            po_file = lang_dir / "LC_MESSAGES" / "messages.po"
            if po_file.exists():
                print(f"\n📝 处理语言: {lang_dir.name}")
                
                # 清理无效条目
                clean_invalid_entries(str(po_file), all_msgids)
                
                # 解析po文件
                translated, untranslated_in_po = parse_po_file(str(po_file))
                translated_msgids = set(msgid for msgid, _ in translated)
                
                # 找出在pot中但不在po文件中的字符串（需要添加）
                missing_msgids = all_msgids - translated_msgids
                
                if missing_msgids:
                    print(f"发现 {len(missing_msgids)} 个新的未翻译条目")
                    add_untranslated_entries(str(po_file), sorted(missing_msgids))
                else:
                    print("没有新的未翻译条目需要添加")
                
                # 统计信息
                total_in_po = len(translated) + len(untranslated_in_po)
                if total_in_po > 0:
                    progress = len(translated) / (len(translated) + len(untranslated_in_po) + len(missing_msgids)) * 100
                    print(f"翻译进度: {len(translated)}/{len(translated) + len(untranslated_in_po) + len(missing_msgids)} ({progress:.1f}%)")
    
    print("\n🎉 未翻译条目处理完成！")

def clean_only():
    """仅清理无效条目"""
    print("🧹 正在清理无效条目...")
    
    # 确保先有最新的pot文件
    extract_messages()
    
    # 解析pot文件获取所有有效的msgid
    pot_file = "messages.pot"
    all_msgids = set(parse_pot_file(pot_file))
    
    if not all_msgids:
        print("没有找到有效的翻译字符串")
        return
    
    # 处理每个语言的po文件
    translations_dir = Path("app/translations")
    if not translations_dir.exists():
        print("翻译目录不存在")
        return
    
    for lang_dir in translations_dir.iterdir():
        if lang_dir.is_dir():
            po_file = lang_dir / "LC_MESSAGES" / "messages.po"
            if po_file.exists():
                print(f"\n🧹 清理语言: {lang_dir.name}")
                clean_invalid_entries(str(po_file), all_msgids)
    
    print("\n🎉 清理完成！")

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
    
    # 处理未翻译条目命令
    subparsers.add_parser('untranslated', help='处理未翻译的条目，添加到po文件末尾')
    
    # 清理无效条目命令
    subparsers.add_parser('clean', help='清理po文件中的无效条目')
    
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
    elif args.command == 'untranslated':
        process_untranslated()
    elif args.command == 'clean':
        clean_only()
    else:
        # 如果没有指定命令，默认处理未翻译条目
        print("🚀 自动处理未翻译条目...")
        process_untranslated()

if __name__ == '__main__':
    main() 