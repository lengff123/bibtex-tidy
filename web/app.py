from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import tempfile
import os
import traceback
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bib_tidy.main import BibTidy
from typing import Dict, Any
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from functools import wraps

app = Flask(__name__)




def validate_options(options: Dict[str, Any]) -> Dict[str, Any]:
    """验证和处理用户提交的选项"""
    validated = {}
    
    # 布尔选项
    bool_options = [
        'sort_fields', 'encode_urls', 'use_tabs', 
        'auto_keys', 'merge_duplicates', 'validate_urls',
        'double_braces', 'header', 'use_spaces'
    ]
    for opt in bool_options:
        if opt in options:
            # 处理多种可能的真值情况：'true', 'on', True, 1
            value = options.get(opt)
            validated[opt] = value in [True, 'true', 'on', '1', 1]
    
    # 字符串选项
    str_options = [
        'sort_entries', 'key_format', 'merge_strategy',
        'duplicate_check', 'field_order'
    ]
    for opt in str_options:
        if opt in options and options[opt]:
            validated[opt] = str(options[opt])
    
    # 列表选项（逗号分隔的字符串）
    list_options = ['omit']
    for opt in list_options:
        if opt in options and options[opt]:
            items = [x.strip() for x in str(options[opt]).split(',')]
            validated['omit_fields'] = [x for x in items if x]

    if 'replace_fields' in options and options['replace_fields']:
        field_replacements = {}
        for replacement in options['replace_fields'].split(','):
            if ':' in replacement:
                old_field, new_field = replacement.split(':', 1)
                field_replacements[old_field.strip()] = new_field.strip()
        validated['field_replacements'] = field_replacements
    
    # 数值选项
    int_options = ['max_authors', 'align']
    for opt in int_options:
        if opt in options and options[opt]:
            try:
                validated[opt] = int(options[opt])
            except (ValueError, TypeError):
                pass
    
    print("Validated options:", validated)  # 添加调试输出
    return validated

@app.route('/')
def index():
    """渲染主页，带有语言支持"""
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    """提供静态文件"""
    return send_from_directory('static', path)

@app.route('/process', methods=['POST'])
def process_bib():
    """处理BibTeX内容"""
    try:
        # 获取用户输入
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({
                'success': False,
                'error': 'No content provided'
            }), 400
        
        bib_content = data['content']
        if not bib_content.strip():
            return jsonify({
                'success': False,
                'error': 'Empty content'
            }), 400
        
        # 验证和处理选项
        options = validate_options(data.get('options', {}))
        print(data.get('options', {}))
        # 创建临时文件，确保使用UTF-8编码
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False, encoding='utf-8') as temp_in:
            temp_in.write(bib_content)
            input_file = temp_in.name
        
        try:
            # 处理文件
            processor = BibTidy(options)
            output_file = input_file + '_processed.bib'
            
            # 1. 文件读取和基本清理
            with open(input_file, 'r', encoding='utf-8') as bibtex_file:
                bib_database = bibtexparser.load(bibtex_file)
            
            # 移除条目类型中的额外大括号
            for entry in bib_database.entries:
                if 'ENTRYTYPE' in entry:
                    entry['ENTRYTYPE'] = entry['ENTRYTYPE'].strip('{}')
            
            # 2. ���行处理条目
            processed_entries = processor.process_entries_parallel(bib_database.entries)
            
            # 3. 字段排序（如果启用）
            if options.get('sort_fields'):
                processed_entries = [processor.sort_fields(entry) for entry in processed_entries]
            
            # 4. 重复条目处理
            if options.get('merge_duplicates'):
                processed_entries = processor.merge_entries(processed_entries)
            
            # 5. 引用键处理
            if options.get('auto_generate_keys'):
                processed_entries = processor.resolve_key_conflicts(processed_entries)
            
            # 6. 条目排序
            if options.get('sort_entries'):
                sort_by = options['sort_entries']
                if sort_by == 'key':
                    processed_entries.sort(key=lambda x: x['ID'].lower())
                elif sort_by == 'year':
                    processed_entries.sort(key=lambda x: x.get('year', ''))
                elif sort_by == 'author':
                    processed_entries.sort(key=lambda x: x.get('author', '').lower())
            
            # 7. 配置输出格式
            writer = BibTexWriter()
            writer.indent = '\t' if options.get('use_tabs', True) else '  '
            if 'align_values' in options:
                writer.align_values = options['align_values']
            if 'field_order' in options:
                writer.display_order = options['field_order'].split(',')
            writer.order_entries_by = None
            
            # 8. 准备数据库对象
            db = BibDatabase()
            db.entries = processed_entries
            
            # 9. 生成输出内容
            output_content = ''
            if options.get('header'):
                header = (
                    f"% Bibliography File\n"
                    f"% Processed by BibTidy on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"% Total entries: {len(processed_entries)}\n"
                )
                # 添加选项信息
                header_options = [f"{key}: {value}" for key, value in options.items() if value is not None]
                if header_options:
                    header += "% Options used:\n"
                    for option in header_options:
                        header += f"%   - {option}\n"
                header += f"% {'='*76}\n\n"
                output_content = header + writer.write(db)
                print(header)
                # 返回处理结果
                return jsonify({
                    'success': True,
                    'content': output_content,
                    'options': options
                })
            else:
                return jsonify({
                    'success': True,
                    'content': writer.write(db),
                    'options': options
                })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'details': traceback.format_exc()
            }), 500
            
        finally:
            # 清理临时文件
            try:
                os.unlink(input_file)
                if os.path.exists(output_file):
                    os.unlink(output_file)
            except Exception:
                pass
                
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}',
            'details': traceback.format_exc()
        }), 500

if __name__ == '__main__':
    #app.config['JSON_AS_ASCII'] = False
    app.run(debug=True, host='0.0.0.0', port=5000)  # Changed host to 0.0.0.0 to allow external connections